"""Tests for services/bedrock_agent_service.py"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from botocore.exceptions import ClientError
from models.chat_models import ChatSession, ToolExecutionStatus


class TestBedrockAgentService:
    def _make_service(self, agent_id="agent-1", alias_id="alias-1"):
        with patch("services.bedrock_agent_service.get_config") as mock_gc:
            mock_gc.side_effect = lambda key, default=None: {
                "AWS_DEFAULT_REGION": "us-east-1",
                "ENHANCED_SECURITY_AGENT_ID": agent_id,
                "ENHANCED_SECURITY_AGENT_ALIAS_ID": alias_id,
            }.get(key, default)
            from services.bedrock_agent_service import BedrockAgentService
            svc = BedrockAgentService()
        return svc

    def _make_session(self):
        return ChatSession(
            session_id="test-session",
            created_at=datetime.utcnow(),
            messages=[],
            context={},
        )

    def test_init_with_config(self):
        svc = self._make_service()
        assert svc.agent_id == "agent-1"
        assert svc.agent_alias_id == "alias-1"
        assert svc.region == "us-east-1"

    def test_init_without_config(self):
        svc = self._make_service(agent_id=None, alias_id=None)
        assert svc.agent_id is None
        assert svc.agent_alias_id is None

    def test_bedrock_agent_runtime_lazy(self):
        svc = self._make_service()
        client = svc.bedrock_agent_runtime
        assert client is not None
        assert svc.bedrock_agent_runtime is client

    def test_bedrock_agent_lazy(self):
        svc = self._make_service()
        client = svc.bedrock_agent
        assert client is not None

    def test_bedrock_runtime_lazy(self):
        svc = self._make_service()
        client = svc.bedrock_runtime
        assert client is not None

    def test_bedrock_agent_runtime_failure(self):
        svc = self._make_service()
        with patch("boto3.client", side_effect=Exception("fail")):
            svc._bedrock_agent_runtime = None
            client = svc.bedrock_agent_runtime
            assert client is None

    def test_bedrock_agent_failure(self):
        svc = self._make_service()
        with patch("boto3.client", side_effect=Exception("fail")):
            svc._bedrock_agent = None
            client = svc.bedrock_agent
            assert client is None

    def test_bedrock_runtime_failure(self):
        svc = self._make_service()
        with patch("boto3.client", side_effect=Exception("fail")):
            svc._bedrock_runtime = None
            client = svc.bedrock_runtime
            assert client is None

    def test_get_agent_info_configured(self):
        svc = self._make_service()
        info = svc.get_agent_info()
        assert info["configured"] is True
        assert info["agent_id"] == "agent-1"

    def test_get_agent_info_not_configured(self):
        svc = self._make_service(agent_id=None, alias_id=None)
        info = svc.get_agent_info()
        assert info["configured"] is False

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        svc = self._make_service()
        mock_agent = MagicMock()
        mock_agent.get_agent.return_value = {"agent": {"agentStatus": "PREPARED"}}
        svc._bedrock_agent = mock_agent
        result = await svc.health_check()
        assert result == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        svc = self._make_service()
        mock_agent = MagicMock()
        mock_agent.get_agent.return_value = {"agent": {"agentStatus": "FAILED"}}
        svc._bedrock_agent = mock_agent
        result = await svc.health_check()
        assert result == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_degraded_no_config(self):
        svc = self._make_service(agent_id=None, alias_id=None)
        result = await svc.health_check()
        assert result == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        svc = self._make_service()
        mock_agent = MagicMock()
        mock_agent.get_agent.side_effect = Exception("fail")
        svc._bedrock_agent = mock_agent
        result = await svc.health_check()
        assert result == "degraded"

    @pytest.mark.asyncio
    async def test_process_message_not_configured(self):
        svc = self._make_service(agent_id=None, alias_id=None)
        session = self._make_session()
        resp = await svc.process_message("hello", session)
        assert "not configured" in resp.response

    @pytest.mark.asyncio
    async def test_process_message_success(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        mock_runtime.invoke_agent.return_value = {
            "completion": [
                {"chunk": {"bytes": b"Security analysis complete."}},
            ],
            "sessionId": "sess-1",
        }
        svc._bedrock_agent_runtime = mock_runtime
        session = self._make_session()
        resp = await svc.process_message("check security", session)
        assert "Security analysis complete" in resp.response

    @pytest.mark.asyncio
    async def test_process_message_client_error(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        mock_runtime.invoke_agent.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "bad input"}},
            "InvokeAgent",
        )
        svc._bedrock_agent_runtime = mock_runtime
        session = self._make_session()
        resp = await svc.process_message("test", session)
        assert "error" in resp.response.lower()

    @pytest.mark.asyncio
    async def test_process_message_unexpected_error(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        mock_runtime.invoke_agent.side_effect = RuntimeError("boom")
        svc._bedrock_agent_runtime = mock_runtime
        session = self._make_session()
        resp = await svc.process_message("test", session)
        assert "unexpected error" in resp.response.lower()

    @pytest.mark.asyncio
    async def test_process_message_with_json_in_response(self):
        svc = self._make_service()
        json_text = '```json\n{"findings": [{"id": "f1"}]}\n```'
        mock_runtime = MagicMock()
        mock_runtime.invoke_agent.return_value = {
            "completion": [{"chunk": {"bytes": json_text.encode()}}],
            "sessionId": "sess-1",
        }
        svc._bedrock_agent_runtime = mock_runtime
        session = self._make_session()
        resp = await svc.process_message("check", session)
        assert resp.structured_data is not None
        assert "findings" in resp.structured_data

    @pytest.mark.asyncio
    async def test_execute_security_mcp_check_services(self):
        svc = self._make_service()
        result = await svc._execute_security_mcp_function(
            "CheckSecurityServices", {"region": "us-east-1"}
        )
        assert "service_statuses" in result
        assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_execute_security_mcp_get_findings(self):
        svc = self._make_service()
        result = await svc._execute_security_mcp_function(
            "GetSecurityFindings", {"service": "guardduty"}
        )
        assert "findings" in result
        assert result["findings_count"] == 3

    @pytest.mark.asyncio
    async def test_execute_security_mcp_check_storage(self):
        svc = self._make_service()
        result = await svc._execute_security_mcp_function(
            "CheckStorageEncryption", {"services": ["s3"]}
        )
        assert "compliance_by_service" in result

    @pytest.mark.asyncio
    async def test_execute_security_mcp_unknown_function(self):
        svc = self._make_service()
        result = await svc._execute_security_mcp_function("UnknownFunc", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_aws_api_mcp_function(self):
        svc = self._make_service()
        result = await svc._execute_aws_api_mcp_function("DescribeInstances", {"region": "us-east-1"})
        assert "DescribeInstances" in result

    def test_generate_basic_summary_security_services(self):
        svc = self._make_service()
        data = {
            "services_checked": ["GuardDuty"],
            "all_enabled": True,
            "service_statuses": {"GuardDuty": {"enabled": True, "status": "healthy"}},
            "recommendations": ["Enable SecurityHub"],
        }
        summary = svc._generate_basic_summary(data, "CheckSecurityServices")
        assert "Security Services" in summary
        assert "GuardDuty" in summary

    def test_generate_basic_summary_findings(self):
        svc = self._make_service()
        data = {
            "service": "guardduty",
            "findings_count": 2,
            "findings": [
                {"severity": "HIGH", "title": "Issue 1"},
                {"severity": "LOW", "title": "Issue 2"},
            ],
        }
        summary = svc._generate_basic_summary(data, "GetSecurityFindings")
        assert "Security Findings" in summary

    def test_generate_basic_summary_storage(self):
        svc = self._make_service()
        data = {
            "compliant_resources": 5,
            "non_compliant_resources": 2,
            "compliance_by_service": {
                "s3": {"total": 4, "encrypted": 3, "unencrypted": 1}
            },
        }
        summary = svc._generate_basic_summary(data, "CheckStorageEncryption")
        assert "Storage Encryption" in summary

    def test_generate_basic_summary_unknown(self):
        svc = self._make_service()
        data = {"key1": "val1", "key2": "val2"}
        summary = svc._generate_basic_summary(data, "SomeOtherFunc")
        assert "SomeOtherFunc" in summary

    def test_generate_basic_summary_all_compliant(self):
        svc = self._make_service()
        data = {
            "compliant_resources": 5,
            "non_compliant_resources": 0,
            "compliance_by_service": {},
        }
        summary = svc._generate_basic_summary(data, "CheckStorageEncryption")
        assert "All resources properly encrypted" in summary

    def test_generate_basic_summary_exception(self):
        svc = self._make_service()
        # Pass non-dict that will cause error in iteration
        summary = svc._generate_basic_summary(None, "CheckSecurityServices")
        assert "completed successfully" in summary

    @pytest.mark.asyncio
    async def test_handle_return_control_empty(self):
        svc = self._make_service()
        session = self._make_session()
        result = await svc._handle_return_control({}, session)
        assert "No tools to execute" in result

    @pytest.mark.asyncio
    async def test_handle_return_control_with_security_function(self):
        svc = self._make_service()
        session = self._make_session()
        payload = {
            "invocationInputs": [
                {
                    "functionInvocationInput": {
                        "actionGroup": "security-mcp-server",
                        "function": "CheckSecurityServices",
                        "parameters": [
                            {"name": "region", "value": "us-east-1", "type": "string"}
                        ],
                    }
                }
            ]
        }
        result = await svc._handle_return_control(payload, session)
        assert "CheckSecurityServices" in result

    @pytest.mark.asyncio
    async def test_handle_return_control_with_aws_api(self):
        svc = self._make_service()
        session = self._make_session()
        payload = {
            "invocationInputs": [
                {
                    "functionInvocationInput": {
                        "actionGroup": "aws-api-mcp-server-public",
                        "function": "ListInstances",
                        "parameters": [],
                    }
                }
            ]
        }
        result = await svc._handle_return_control(payload, session)
        assert "ListInstances" in result

    @pytest.mark.asyncio
    async def test_handle_return_control_unknown_action_group(self):
        svc = self._make_service()
        session = self._make_session()
        payload = {
            "invocationInputs": [
                {
                    "functionInvocationInput": {
                        "actionGroup": "unknown-group",
                        "function": "Func",
                        "parameters": [],
                    }
                }
            ]
        }
        result = await svc._handle_return_control(payload, session)
        assert "Unknown action group" in result

    @pytest.mark.asyncio
    async def test_handle_return_control_array_parameter(self):
        svc = self._make_service()
        session = self._make_session()
        payload = {
            "invocationInputs": [
                {
                    "functionInvocationInput": {
                        "actionGroup": "security-mcp-server",
                        "function": "CheckSecurityServices",
                        "parameters": [
                            {"name": "services", "value": "[GuardDuty, SecurityHub]", "type": "array"}
                        ],
                    }
                }
            ]
        }
        result = await svc._handle_return_control(payload, session)
        assert "CheckSecurityServices" in result

    @pytest.mark.asyncio
    async def test_handle_return_control_exception(self):
        svc = self._make_service()
        session = self._make_session()
        # Trigger the except branch by making invocationInputs iteration raise
        payload = MagicMock()
        payload.get.side_effect = RuntimeError("forced error")
        result = await svc._handle_return_control(payload, session)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_generate_human_readable_summary_success(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps({
                "content": [{"text": "## Summary\nAll good!"}]
            }).encode())
        }
        svc._bedrock_runtime = mock_runtime
        data = {"findings": []}
        summary = await svc._generate_human_readable_summary(data, "TestFunc")
        assert "Summary" in summary

    @pytest.mark.asyncio
    async def test_generate_human_readable_summary_fallback(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.side_effect = Exception("bedrock down")
        svc._bedrock_runtime = mock_runtime
        data = {"service": "guardduty", "findings_count": 1, "findings": [{"severity": "HIGH", "title": "test"}]}
        summary = await svc._generate_human_readable_summary(data, "GetSecurityFindings")
        assert "Security Findings" in summary
