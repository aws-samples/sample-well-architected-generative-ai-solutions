"""Tests for services/llm_orchestrator_service.py"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models.chat_models import ChatSession, ToolExecutionStatus


class TestLLMOrchestratorService:
    def _make_service(self):
        with patch("services.llm_orchestrator_service.get_config") as mock_gc:
            mock_gc.side_effect = lambda key, default=None: {
                "AWS_DEFAULT_REGION": "us-east-1",
            }.get(key, default)
            with patch("services.llm_orchestrator_service.MCPClientService") as mock_mcp:
                mock_mcp_inst = MagicMock()
                mock_mcp_inst.health_check = AsyncMock(return_value="healthy")
                mock_mcp_inst.get_available_tools = AsyncMock(return_value=[
                    {"name": "CheckSecurityServices", "description": "Check security services"}
                ])
                mock_mcp_inst.call_tool = AsyncMock(return_value={"status": "ok"})
                mock_mcp.return_value = mock_mcp_inst
                from services.llm_orchestrator_service import LLMOrchestratorService
                svc = LLMOrchestratorService()
        return svc

    def _make_session(self):
        return ChatSession(
            session_id="test-session",
            created_at=datetime.utcnow(),
            messages=[],
            context={},
        )

    def test_init(self):
        svc = self._make_service()
        assert svc.region == "us-east-1"
        assert svc.tools_discovered is False
        assert svc.available_tools == []

    def test_bedrock_runtime_lazy_init(self):
        svc = self._make_service()
        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            client = svc.bedrock_runtime
            assert client is mock_client

    def test_bedrock_runtime_init_failure(self):
        svc = self._make_service()
        with patch("boto3.client", side_effect=Exception("fail")):
            from services.llm_orchestrator_service import BedrockInitializationError
            with pytest.raises(BedrockInitializationError):
                _ = svc.bedrock_runtime

    def test_bedrock_runtime_caches_error(self):
        svc = self._make_service()
        with patch("boto3.client", side_effect=Exception("fail")):
            from services.llm_orchestrator_service import BedrockInitializationError
            with pytest.raises(BedrockInitializationError):
                _ = svc.bedrock_runtime
            # Second call should raise same error without re-trying
            with pytest.raises(BedrockInitializationError):
                _ = svc.bedrock_runtime

    def test_is_bedrock_available_true(self):
        svc = self._make_service()
        svc._bedrock_runtime = MagicMock()
        assert svc._is_bedrock_available() is True

    def test_is_bedrock_available_false(self):
        svc = self._make_service()
        from services.llm_orchestrator_service import BedrockInitializationError
        svc._bedrock_initialization_error = BedrockInitializationError("fail")
        assert svc._is_bedrock_available() is False

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        svc = self._make_service()
        svc._bedrock_runtime = MagicMock()
        result = await svc.health_check()
        assert result == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        svc = self._make_service()
        from services.llm_orchestrator_service import BedrockInitializationError
        svc._bedrock_initialization_error = BedrockInitializationError("fail")
        result = await svc.health_check()
        assert result == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        svc = self._make_service()
        svc.mcp_service.health_check = AsyncMock(return_value="unhealthy")
        result = await svc.health_check()
        assert result == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        svc = self._make_service()
        svc.mcp_service.health_check = AsyncMock(side_effect=Exception("fail"))
        result = await svc.health_check()
        assert result == "unhealthy"

    @pytest.mark.asyncio
    async def test_initialize_session(self):
        svc = self._make_service()
        session = self._make_session()
        result = await svc.initialize_session(session)
        assert result["status"] == "initialized"
        assert result["tools_count"] == 1
        assert session.context["orchestrator_initialized"] is True

    @pytest.mark.asyncio
    async def test_initialize_session_error(self):
        svc = self._make_service()
        svc.mcp_service.get_available_tools = AsyncMock(side_effect=Exception("fail"))
        session = self._make_session()
        result = await svc.initialize_session(session)
        # Should still succeed (tools discovery failure is non-fatal)
        assert result["status"] == "initialized"

    @pytest.mark.asyncio
    async def test_discover_tools(self):
        svc = self._make_service()
        await svc._discover_tools()
        assert svc.tools_discovered is True
        assert len(svc.available_tools) == 1

    @pytest.mark.asyncio
    async def test_discover_tools_failure(self):
        svc = self._make_service()
        svc.mcp_service.get_available_tools = AsyncMock(side_effect=Exception("fail"))
        await svc._discover_tools()
        assert svc.available_tools == []

    def test_generate_system_prompt(self):
        svc = self._make_service()
        svc.available_tools = [
            {"name": "TestTool", "description": "A test tool", "inputSchema": {"properties": {"param1": {}}}}
        ]
        prompt = svc._generate_system_prompt()
        assert "TestTool" in prompt
        assert "param1" in prompt

    def test_generate_system_prompt_no_tools(self):
        svc = self._make_service()
        svc.available_tools = []
        prompt = svc._generate_system_prompt()
        assert "No tools currently available" in prompt

    @pytest.mark.asyncio
    async def test_process_message_without_bedrock(self):
        svc = self._make_service()
        from services.llm_orchestrator_service import BedrockInitializationError
        svc._bedrock_initialization_error = BedrockInitializationError("fail")
        session = self._make_session()
        session.context["orchestrator_initialized"] = True
        resp = await svc.process_message("check security status", session)
        assert resp.model_id == "fallback-mode"

    @pytest.mark.asyncio
    async def test_process_message_with_bedrock(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        # Analysis response
        analysis_json = json.dumps({
            "intent": "security check",
            "tools_to_use": [
                {"name": "CheckSecurityServices", "arguments": {"region": "us-east-1"}, "reason": "security query"}
            ],
            "analysis_approach": "tool-based",
        })
        # Final response
        final_text = "Security check completed. All services are healthy."

        call_count = [0]
        def mock_invoke(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                text = analysis_json
            else:
                text = final_text
            return {
                "body": MagicMock(read=lambda t=text: json.dumps({"content": [{"text": t}]}).encode())
            }

        mock_runtime.invoke_model.side_effect = mock_invoke
        svc._bedrock_runtime = mock_runtime
        svc._bedrock_initialization_error = None

        session = self._make_session()
        session.context["orchestrator_initialized"] = True
        resp = await svc.process_message("check security", session)
        assert "Security check completed" in resp.response
        assert len(resp.tool_executions) == 1

    @pytest.mark.asyncio
    async def test_process_message_tool_execution_failure(self):
        svc = self._make_service()
        svc.mcp_service.call_tool = AsyncMock(side_effect=Exception("tool failed"))
        mock_runtime = MagicMock()
        analysis_json = json.dumps({
            "intent": "test",
            "tools_to_use": [{"name": "BadTool", "arguments": {}, "reason": "test"}],
            "analysis_approach": "test",
        })
        mock_runtime.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps({"content": [{"text": analysis_json}]}).encode())
        }
        svc._bedrock_runtime = mock_runtime
        svc._bedrock_initialization_error = None

        session = self._make_session()
        session.context["orchestrator_initialized"] = True
        resp = await svc.process_message("test", session)
        assert resp.tool_executions[0].status == ToolExecutionStatus.ERROR

    @pytest.mark.asyncio
    async def test_process_message_exception(self):
        svc = self._make_service()
        svc._bedrock_runtime = MagicMock()
        svc._bedrock_initialization_error = None
        svc._bedrock_runtime.invoke_model.side_effect = RuntimeError("unexpected")

        session = self._make_session()
        session.context["orchestrator_initialized"] = True
        resp = await svc.process_message("test", session)
        assert "error" in resp.response.lower()

    @pytest.mark.asyncio
    async def test_process_message_without_bedrock_security(self):
        svc = self._make_service()
        from services.llm_orchestrator_service import BedrockInitializationError
        svc._bedrock_initialization_error = BedrockInitializationError("fail")
        session = self._make_session()
        session.context["orchestrator_initialized"] = True
        resp = await svc._process_message_without_bedrock("check security", session)
        assert resp.model_id == "fallback-mode"
        assert len(resp.tool_executions) >= 1

    @pytest.mark.asyncio
    async def test_process_message_without_bedrock_storage(self):
        svc = self._make_service()
        from services.llm_orchestrator_service import BedrockInitializationError
        svc._bedrock_initialization_error = BedrockInitializationError("fail")
        session = self._make_session()
        session.context["orchestrator_initialized"] = True
        resp = await svc._process_message_without_bedrock("check s3 encryption", session)
        assert resp.model_id == "fallback-mode"

    @pytest.mark.asyncio
    async def test_process_message_without_bedrock_no_match(self):
        svc = self._make_service()
        from services.llm_orchestrator_service import BedrockInitializationError
        svc._bedrock_initialization_error = BedrockInitializationError("fail")
        session = self._make_session()
        session.context["orchestrator_initialized"] = True
        resp = await svc._process_message_without_bedrock("hello how are you", session)
        assert "limited mode" in resp.response.lower()

    @pytest.mark.asyncio
    async def test_process_message_without_bedrock_tool_failure(self):
        svc = self._make_service()
        svc.mcp_service.call_tool = AsyncMock(side_effect=Exception("tool fail"))
        from services.llm_orchestrator_service import BedrockInitializationError
        svc._bedrock_initialization_error = BedrockInitializationError("fail")
        session = self._make_session()
        session.context["orchestrator_initialized"] = True
        resp = await svc._process_message_without_bedrock("check security", session)
        # Should still return a response even if tool fails
        assert resp.response is not None

    def test_generate_fallback_response_no_results(self):
        svc = self._make_service()
        resp = svc._generate_fallback_response("hello", [])
        assert "limited mode" in resp.lower()
        assert "hello" in resp

    def test_generate_fallback_response_with_results(self):
        svc = self._make_service()
        results = [
            {
                "tool_name": "CheckSecurityServices",
                "result": {
                    "all_enabled": False,
                    "resources_checked": 3,
                    "compliant_resources": 2,
                    "non_compliant_resources": 1,
                },
            }
        ]
        resp = svc._generate_fallback_response("security check", results)
        assert "CheckSecurityServices" in resp
        assert "Resources checked: 3" in resp

    def test_analyze_user_request_fallback_security(self):
        svc = self._make_service()
        result = svc._analyze_user_request_fallback("check my security compliance")
        tools = [t["name"] for t in result["tools_to_use"]]
        assert "CheckSecurityServices" in tools

    def test_analyze_user_request_fallback_storage(self):
        svc = self._make_service()
        result = svc._analyze_user_request_fallback("check s3 encryption")
        tools = [t["name"] for t in result["tools_to_use"]]
        assert "CheckStorageEncryption" in tools

    def test_analyze_user_request_fallback_network(self):
        svc = self._make_service()
        result = svc._analyze_user_request_fallback("check my vpc network")
        tools = [t["name"] for t in result["tools_to_use"]]
        assert "CheckNetworkSecurity" in tools

    def test_analyze_user_request_fallback_no_match(self):
        svc = self._make_service()
        result = svc._analyze_user_request_fallback("hello world")
        assert result["tools_to_use"] == []

    @pytest.mark.asyncio
    async def test_analyze_user_request_with_bedrock(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        analysis_json = json.dumps({
            "intent": "security check",
            "tools_to_use": [],
            "analysis_approach": "direct",
        })
        mock_runtime.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps({"content": [{"text": analysis_json}]}).encode())
        }
        svc._bedrock_runtime = mock_runtime
        session = self._make_session()
        session.context["system_prompt"] = "You are helpful"
        result = await svc._analyze_user_request("hello", session)
        assert result["intent"] == "security check"

    @pytest.mark.asyncio
    async def test_analyze_user_request_json_parse_failure(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps({"content": [{"text": "no json here"}]}).encode())
        }
        svc._bedrock_runtime = mock_runtime
        session = self._make_session()
        result = await svc._analyze_user_request("hello", session)
        assert result["intent"] == "general query"

    @pytest.mark.asyncio
    async def test_analyze_user_request_bedrock_unavailable(self):
        svc = self._make_service()
        from services.llm_orchestrator_service import BedrockInitializationError
        svc._bedrock_initialization_error = BedrockInitializationError("fail")
        session = self._make_session()
        result = await svc._analyze_user_request("check security", session)
        assert result["intent"] == "automated analysis based on keywords"

    @pytest.mark.asyncio
    async def test_analyze_user_request_bedrock_exception(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.side_effect = RuntimeError("fail")
        svc._bedrock_runtime = mock_runtime
        session = self._make_session()
        result = await svc._analyze_user_request("check security", session)
        # Falls back to keyword-based
        assert "tools_to_use" in result

    @pytest.mark.asyncio
    async def test_generate_final_response_with_bedrock(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps({
                "content": [{"text": "Here is my analysis."}]
            }).encode())
        }
        svc._bedrock_runtime = mock_runtime
        svc._bedrock_initialization_error = None

        session = self._make_session()
        session.context["system_prompt"] = "You are helpful"
        analysis = {"intent": "test", "tools_to_use": []}
        tool_results = [{"tool_name": "TestTool", "result": {"key": "val"}}]

        result = await svc._generate_final_response("test", analysis, tool_results, session)
        assert result["response"] == "Here is my analysis."
        assert result["structured_data"] is not None

    @pytest.mark.asyncio
    async def test_generate_final_response_bedrock_unavailable(self):
        svc = self._make_service()
        from services.llm_orchestrator_service import BedrockInitializationError
        svc._bedrock_initialization_error = BedrockInitializationError("fail")

        session = self._make_session()
        result = await svc._generate_final_response("test", {}, [], session)
        assert "limited mode" in result["response"].lower()

    @pytest.mark.asyncio
    async def test_generate_final_response_bedrock_exception(self):
        svc = self._make_service()
        mock_runtime = MagicMock()
        mock_runtime.invoke_model.side_effect = RuntimeError("fail")
        svc._bedrock_runtime = mock_runtime
        svc._bedrock_initialization_error = None

        session = self._make_session()
        result = await svc._generate_final_response("test", {}, [], session)
        assert "error" in result["response"].lower()

    def test_get_session_info(self):
        svc = self._make_service()
        svc.available_tools = [{"name": "Tool1", "description": "desc"}]
        session = self._make_session()
        session.context["orchestrator_initialized"] = True
        session.context["bedrock_available"] = True

        info = svc.get_session_info(session)
        assert info["session_id"] == "test-session"
        assert info["tools_available"] == 1
        assert info["initialized"] is True

    def test_get_session_info_uninitialized(self):
        svc = self._make_service()
        session = self._make_session()
        info = svc.get_session_info(session)
        assert info["initialized"] is False
        assert info["bedrock_available"] is False
