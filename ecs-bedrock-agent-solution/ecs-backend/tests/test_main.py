"""Tests for main.py — FastAPI endpoints, WebSocket, and helpers."""

import json
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# We need to mock heavy service imports before importing main
# Patch config_service at module level to avoid real SSM calls during import

_mock_config_svc = MagicMock()
_mock_config_svc.get_config_value.return_value = None
_mock_config_svc.get_ssm_status.return_value = {"available": False, "prefix": "/coa/", "cached_parameters": 0}
_mock_config_svc.get_all_config.return_value = {}
_mock_config_svc.refresh_cache.return_value = None
_mock_config_svc.list_ssm_parameters.return_value = {"parameters": [], "count": 0}


def _mock_get_config(key, default=None):
    env_val = os.environ.get(key)
    if env_val:
        return env_val
    return default


@pytest.fixture(autouse=True)
def _patch_services(monkeypatch):
    """Patch services before main is imported."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("USER_POOL_ID", "us-east-1_TestPool")
    monkeypatch.setenv("WEB_APP_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("USE_ENHANCED_AGENT", "false")


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app."""
    # Patch heavy modules before importing main
    with patch("services.config_service.ConfigService", return_value=_mock_config_svc), \
         patch("services.config_service.config_service", _mock_config_svc), \
         patch("services.config_service.get_config", _mock_get_config):

        # Need to also patch the orchestrator and mcp services
        mock_orchestrator = MagicMock()
        mock_orchestrator.health_check = AsyncMock(return_value="healthy")
        mock_orchestrator.process_message = AsyncMock()
        mock_orchestrator.get_session_info = MagicMock(return_value={"session_id": "test", "tools_available": 0})
        mock_orchestrator.initialize_session = AsyncMock(return_value={"status": "initialized", "tools_count": 0})

        mock_mcp = MagicMock()
        mock_mcp.health_check = AsyncMock(return_value="healthy")
        mock_mcp.get_available_tools = AsyncMock(return_value=[{"name": "test_tool", "description": "test"}])

        with patch("main.orchestrator_service", mock_orchestrator), \
             patch("main.mcp_service", mock_mcp), \
             patch("main.config_service", _mock_config_svc), \
             patch("main.get_config", _mock_get_config), \
             patch("main.auth_service") as mock_auth, \
             patch("main.bedrock_service", None), \
             patch("main.use_enhanced_agent", False):

            mock_auth.verify_token = AsyncMock(return_value={"user_id": "test_user", "email": "test@example.com"})

            from httpx import AsyncClient, ASGITransport
            from main import app

            # Store mocks on app for test access
            app._test_mocks = {
                "orchestrator": mock_orchestrator,
                "mcp": mock_mcp,
                "auth": mock_auth,
            }

            from starlette.testclient import TestClient
            yield TestClient(app)


class TestDateTimeEncoder:
    def test_datetime_encoding(self):
        from main import DateTimeEncoder
        encoder = DateTimeEncoder()
        now = datetime.utcnow()
        result = encoder.default(now)
        assert isinstance(result, str)

    def test_non_datetime_raises(self):
        from main import DateTimeEncoder
        encoder = DateTimeEncoder()
        with pytest.raises(TypeError):
            encoder.default(set())


class TestHealthEndpoint:
    def test_health_check_healthy(self, client):
        with patch("main.config_service", _mock_config_svc), \
             patch("main.os.getenv") as mock_getenv:
            # Make required env vars available
            mock_getenv.side_effect = lambda k, d=None: {
                "USER_POOL_ID": "pool",
                "WEB_APP_CLIENT_ID": "client",
                "AWS_DEFAULT_REGION": "us-east-1",
            }.get(k, d)
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert "timestamp" in data

    def test_health_check_missing_env(self, client):
        with patch("main.config_service") as mock_cs, \
             patch("main.os.getenv", return_value=None):
            mock_cs.get_config_value.return_value = None
            resp = client.get("/health")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "unhealthy"

    def test_health_check_unhealthy_service(self, client):
        with patch("main.config_service", _mock_config_svc), \
             patch("main.os.getenv") as mock_getenv, \
             patch("main.orchestrator_service") as mock_orch, \
             patch("main.mcp_service") as mock_mcp:
            mock_getenv.side_effect = lambda k, d=None: {
                "USER_POOL_ID": "pool",
                "WEB_APP_CLIENT_ID": "client",
                "AWS_DEFAULT_REGION": "us-east-1",
            }.get(k, d)
            mock_orch.health_check = AsyncMock(return_value="unhealthy")
            mock_mcp.health_check = AsyncMock(return_value="healthy")
            resp = client.get("/health")
            assert resp.status_code == 503

    def test_health_check_service_exception(self, client):
        with patch("main.config_service", _mock_config_svc), \
             patch("main.os.getenv") as mock_getenv:
            mock_getenv.side_effect = lambda k, d=None: {
                "USER_POOL_ID": "pool",
                "WEB_APP_CLIENT_ID": "client",
                "AWS_DEFAULT_REGION": "us-east-1",
            }.get(k, d)

            # Make the services dict creation raise
            with patch("main.orchestrator_service") as mock_orch:
                mock_orch.health_check = AsyncMock(side_effect=Exception("boom"))
                resp = client.get("/health")
                # Should still return a response (503 with warning)
                assert resp.status_code in [200, 503]


class TestChatEndpoint:
    def test_chat_requires_auth(self, client):
        resp = client.post("/api/chat", json={"message": "hello"})
        # Should fail without auth header
        assert resp.status_code in [401, 403]

    def test_chat_with_auth(self, client):
        from models.chat_models import BedrockResponse
        mock_resp = BedrockResponse(
            response="Hello! How can I help?",
            tool_executions=[],
            session_id="test-session",
        )
        with patch("main.process_chat_message", new_callable=AsyncMock, return_value=MagicMock(
            response="Hello!",
            session_id="test-session",
            tool_executions=[],
            timestamp=datetime.utcnow(),
            structured_data=None,
            human_summary=None,
        )), \
             patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}):
            resp = client.post(
                "/api/chat",
                json={"message": "hello"},
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200


class TestSessionEndpoints:
    def test_get_session_history_not_found(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}):
            resp = client.get(
                "/api/sessions/nonexistent/history",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 404

    def test_get_session_info_not_found(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}):
            resp = client.get(
                "/api/session/nonexistent/info",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 404

    def test_initialize_session(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.orchestrator_service") as mock_orch:
            mock_orch.initialize_session = AsyncMock(return_value={"status": "initialized", "tools_count": 0})
            resp = client.post(
                "/api/session/new-session/initialize",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200


class TestAWSConfigEndpoints:
    def test_get_aws_config(self, client):
        with patch("main.aws_config_service") as mock_aws:
            mock_aws.get_current_config = AsyncMock(return_value={
                "account_id": "123",
                "region": "us-east-1",
                "role_arn": "arn:aws:iam::123:role/test",
                "status": "configured",
            })
            resp = client.get("/api/aws-config")
            assert resp.status_code == 200
            assert resp.json()["status"] == "configured"

    def test_get_aws_config_error(self, client):
        with patch("main.aws_config_service") as mock_aws:
            mock_aws.get_current_config = AsyncMock(side_effect=Exception("fail"))
            resp = client.get("/api/aws-config")
            assert resp.status_code == 200
            assert resp.json()["status"] == "not_configured"

    def test_update_aws_config(self, client):
        with patch("main.aws_config_service") as mock_aws:
            mock_aws.update_config = AsyncMock(return_value={
                "account_info": {"account_id": "123"},
                "role_arn": "arn:aws:iam::123:role/test",
            })
            resp = client.post(
                "/api/aws-config",
                json={"region": "us-west-2"},
            )
            assert resp.status_code == 200

    def test_update_aws_config_error(self, client):
        with patch("main.aws_config_service") as mock_aws:
            mock_aws.update_config = AsyncMock(side_effect=Exception("fail"))
            resp = client.post(
                "/api/aws-config",
                json={"region": "us-west-2"},
            )
            assert resp.status_code == 500


class TestConfigEndpoints:
    def test_get_all_config(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.config_service") as mock_cs:
            mock_cs.get_all_config.return_value = {
                "AWS_ROLE_ARN": "arn:aws:iam::123:role/test",
                "AWS_BEARER_TOKEN_BEDROCK": "secret-token",
            }
            mock_cs.get_ssm_status.return_value = {"available": True}
            resp = client.get(
                "/api/config",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200
            data = resp.json()
            # Sensitive values should be masked
            assert data["config"]["AWS_BEARER_TOKEN_BEDROCK"] == "***"
            assert data["config"]["AWS_ROLE_ARN"] == "arn:aws:iam::123:role/test"

    def test_refresh_config(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.config_service") as mock_cs:
            mock_cs.refresh_cache.return_value = None
            resp = client.post(
                "/api/config/refresh",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "success"

    def test_list_ssm_parameters(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.config_service") as mock_cs:
            mock_cs.list_ssm_parameters.return_value = {"parameters": [], "count": 0}
            resp = client.get(
                "/api/config/ssm/parameters",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200


class TestMCPToolsEndpoint:
    def test_get_available_tools(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.mcp_service") as mock_mcp:
            mock_mcp.get_available_tools = AsyncMock(return_value=[
                {"name": "tool1", "description": "desc1"}
            ])
            resp = client.get(
                "/api/mcp/tools",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200
            assert len(resp.json()["tools"]) == 1


class TestConnectionManager:
    def test_init(self):
        from main import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.active_connections == {}
        assert mgr.sessions == {}

    def test_disconnect(self):
        from main import ConnectionManager
        mgr = ConnectionManager()
        mgr.active_connections["s1"] = MagicMock()
        mgr.sessions["s1"] = MagicMock()
        mgr.disconnect("s1")
        assert "s1" not in mgr.active_connections
        assert "s1" not in mgr.sessions

    def test_disconnect_nonexistent(self):
        from main import ConnectionManager
        mgr = ConnectionManager()
        # Should not raise
        mgr.disconnect("nonexistent")

    @pytest.mark.asyncio
    async def test_send_message(self):
        from main import ConnectionManager
        mgr = ConnectionManager()
        mock_ws = AsyncMock()
        mgr.active_connections["s1"] = mock_ws
        await mgr.send_message("s1", {"type": "test"})
        mock_ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_no_connection(self):
        from main import ConnectionManager
        mgr = ConnectionManager()
        # Should not raise
        await mgr.send_message("nonexistent", {"type": "test"})


class TestValidateStartup:
    @pytest.mark.asyncio
    async def test_validate_startup_ssm_available(self):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123"}
        mock_ssm = MagicMock()
        mock_bedrock = MagicMock()
        mock_bedrock.list_foundation_models.return_value = {"modelSummaries": [{}, {}]}

        def client_factory(svc_name, **kwargs):
            if svc_name == "sts":
                return mock_sts
            elif svc_name == "ssm":
                return mock_ssm
            elif svc_name == "bedrock":
                return mock_bedrock
            return MagicMock()

        with patch("main.config_service") as mock_cs, \
             patch("boto3.client", side_effect=client_factory):
            mock_cs.get_ssm_status.return_value = {"available": True}
            mock_cs.get_all_config.return_value = {"key": "val"}
            mock_cs.get_config_value.side_effect = lambda k, d=None: {
                "ENHANCED_SECURITY_AGENT_ID": "agent-1",
                "ENHANCED_SECURITY_AGENT_ALIAS_ID": "alias-1",
                "BEDROCK_REGION": "us-east-1",
            }.get(k, d)

            from main import validate_startup_requirements
            await validate_startup_requirements()

    @pytest.mark.asyncio
    async def test_validate_startup_ssm_unavailable(self):
        from botocore.exceptions import NoCredentialsError
        with patch("main.config_service") as mock_cs, \
             patch("boto3.client", side_effect=NoCredentialsError()):
            mock_cs.get_ssm_status.return_value = {"available": False}
            mock_cs.get_config_value.return_value = None

            from main import validate_startup_requirements
            await validate_startup_requirements()

    @pytest.mark.asyncio
    async def test_validate_startup_access_denied(self):
        from botocore.exceptions import ClientError
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "GetCallerIdentity"
        )
        with patch("main.config_service") as mock_cs, \
             patch("boto3.client", return_value=mock_sts):
            mock_cs.get_ssm_status.return_value = {"available": False}
            mock_cs.get_config_value.return_value = None

            from main import validate_startup_requirements
            await validate_startup_requirements()

    @pytest.mark.asyncio
    async def test_validate_startup_other_client_error(self):
        from botocore.exceptions import ClientError
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "GetCallerIdentity"
        )
        with patch("main.config_service") as mock_cs, \
             patch("boto3.client", return_value=mock_sts):
            mock_cs.get_ssm_status.return_value = {"available": False}
            mock_cs.get_config_value.return_value = None

            from main import validate_startup_requirements
            await validate_startup_requirements()

    @pytest.mark.asyncio
    async def test_validate_startup_unexpected_error(self):
        with patch("main.config_service") as mock_cs, \
             patch("boto3.client", side_effect=RuntimeError("unexpected")):
            mock_cs.get_ssm_status.return_value = {"available": False}
            mock_cs.get_config_value.return_value = None

            from main import validate_startup_requirements
            await validate_startup_requirements()

    @pytest.mark.asyncio
    async def test_validate_startup_ssm_exception(self):
        with patch("main.config_service") as mock_cs:
            mock_cs.get_ssm_status.side_effect = Exception("ssm fail")
            mock_cs.get_config_value.return_value = None

            from main import validate_startup_requirements
            await validate_startup_requirements()

    @pytest.mark.asyncio
    async def test_validate_startup_bedrock_fail(self):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123"}
        mock_ssm = MagicMock()
        call_count = [0]

        def client_factory(svc_name, **kwargs):
            if svc_name == "sts":
                return mock_sts
            elif svc_name == "ssm":
                return mock_ssm
            elif svc_name in ("bedrock", "bedrock-runtime"):
                raise Exception("bedrock fail")
            return MagicMock()

        with patch("main.config_service") as mock_cs, \
             patch("boto3.client", side_effect=client_factory):
            mock_cs.get_ssm_status.return_value = {"available": True}
            mock_cs.get_all_config.return_value = {}
            mock_cs.get_config_value.side_effect = lambda k, d=None: {
                "ENHANCED_SECURITY_AGENT_ID": None,
                "ENHANCED_SECURITY_AGENT_ALIAS_ID": None,
                "BEDROCK_REGION": "us-east-1",
            }.get(k, d)

            from main import validate_startup_requirements
            await validate_startup_requirements()

    @pytest.mark.asyncio
    async def test_validate_startup_agent_incomplete(self):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123"}
        mock_ssm = MagicMock()
        mock_bedrock = MagicMock()
        mock_bedrock.list_foundation_models.return_value = {"modelSummaries": []}

        def client_factory(svc_name, **kwargs):
            if svc_name == "sts":
                return mock_sts
            elif svc_name == "ssm":
                return mock_ssm
            elif svc_name == "bedrock":
                return mock_bedrock
            return MagicMock()

        with patch("main.config_service") as mock_cs, \
             patch("boto3.client", side_effect=client_factory):
            mock_cs.get_ssm_status.return_value = {"available": True}
            mock_cs.get_all_config.return_value = {}
            mock_cs.get_config_value.side_effect = lambda k, d=None: {
                "ENHANCED_SECURITY_AGENT_ID": "agent-1",
                "ENHANCED_SECURITY_AGENT_ALIAS_ID": None,
                "BEDROCK_REGION": "us-east-1",
            }.get(k, d)

            from main import validate_startup_requirements
            await validate_startup_requirements()


class TestHealthEndpointEnhancedAgent:
    def test_health_with_enhanced_agent(self, client):
        mock_bedrock_svc = MagicMock()
        mock_bedrock_svc.get_agent_info.return_value = {"configured": True}

        with patch("main.config_service", _mock_config_svc), \
             patch("main.os.getenv") as mock_getenv, \
             patch("main.use_enhanced_agent", True), \
             patch("main.bedrock_service", mock_bedrock_svc), \
             patch("main.orchestrator_service") as mock_orch, \
             patch("main.mcp_service") as mock_mcp:
            mock_getenv.side_effect = lambda k, d=None: {
                "USER_POOL_ID": "pool",
                "WEB_APP_CLIENT_ID": "client",
                "AWS_DEFAULT_REGION": "us-east-1",
            }.get(k, d)
            mock_orch.health_check = AsyncMock(return_value="healthy")
            mock_mcp.health_check = AsyncMock(return_value="healthy")
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_health_enhanced_agent_exception(self, client):
        mock_bedrock_svc = MagicMock()
        mock_bedrock_svc.get_agent_info.side_effect = Exception("fail")

        with patch("main.config_service", _mock_config_svc), \
             patch("main.os.getenv") as mock_getenv, \
             patch("main.use_enhanced_agent", True), \
             patch("main.bedrock_service", mock_bedrock_svc), \
             patch("main.orchestrator_service") as mock_orch, \
             patch("main.mcp_service") as mock_mcp:
            mock_getenv.side_effect = lambda k, d=None: {
                "USER_POOL_ID": "pool",
                "WEB_APP_CLIENT_ID": "client",
                "AWS_DEFAULT_REGION": "us-east-1",
            }.get(k, d)
            mock_orch.health_check = AsyncMock(return_value="healthy")
            mock_mcp.health_check = AsyncMock(return_value="healthy")
            resp = client.get("/health")
            # Still returns something
            assert resp.status_code in [200, 503]


class TestHealthEndpointException:
    def test_health_outer_exception(self, client):
        with patch("main.config_service") as mock_cs:
            mock_cs.get_config_value.side_effect = Exception("total failure")
            with patch("main.os.getenv", side_effect=Exception("env fail")):
                resp = client.get("/health")
                assert resp.status_code == 503
                assert resp.json()["status"] == "unhealthy"


class TestChatEndpointErrors:
    def test_chat_endpoint_internal_error(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.process_chat_message", new_callable=AsyncMock, side_effect=Exception("internal")):
            resp = client.post(
                "/api/chat",
                json={"message": "hello"},
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 500


class TestSessionInfoEndpoint:
    def test_get_session_info_success(self, client):
        from main import manager
        from models.chat_models import ChatSession
        session = ChatSession(
            session_id="info-session",
            created_at=datetime.utcnow(),
            messages=[],
            context={},
        )
        manager.sessions["info-session"] = session

        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.orchestrator_service") as mock_orch:
            mock_orch.get_session_info.return_value = {"session_id": "info-session", "tools": 0}
            resp = client.get(
                "/api/session/info-session/info",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200

        manager.disconnect("info-session")

    def test_get_session_info_error(self, client):
        from main import manager
        from models.chat_models import ChatSession
        session = ChatSession(
            session_id="err-info",
            created_at=datetime.utcnow(),
            messages=[],
            context={},
        )
        manager.sessions["err-info"] = session

        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.orchestrator_service") as mock_orch:
            mock_orch.get_session_info.side_effect = Exception("fail")
            resp = client.get(
                "/api/session/err-info/info",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 500

        manager.disconnect("err-info")


class TestSessionHistorySuccess:
    def test_get_session_history_success(self, client):
        from main import manager
        from models.chat_models import ChatSession, ChatMessage
        session = ChatSession(
            session_id="hist-session",
            created_at=datetime.utcnow(),
            messages=[
                ChatMessage(role="user", content="hello", timestamp=datetime.utcnow())
            ],
            context={},
        )
        manager.sessions["hist-session"] = session

        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}):
            resp = client.get(
                "/api/sessions/hist-session/history",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 200
            assert len(resp.json()["messages"]) == 1

        manager.disconnect("hist-session")


class TestMCPToolsError:
    def test_get_tools_error(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.mcp_service") as mock_mcp:
            mock_mcp.get_available_tools = AsyncMock(side_effect=Exception("fail"))
            resp = client.get(
                "/api/mcp/tools",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 500


class TestInitializeSessionError:
    def test_initialize_session_error(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.orchestrator_service") as mock_orch:
            mock_orch.initialize_session = AsyncMock(side_effect=Exception("fail"))
            resp = client.post(
                "/api/session/test-session/initialize",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 500


class TestConfigEndpointErrors:
    def test_get_all_config_error(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.config_service") as mock_cs:
            mock_cs.get_all_config.side_effect = Exception("fail")
            resp = client.get(
                "/api/config",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 500

    def test_refresh_config_error(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.config_service") as mock_cs:
            mock_cs.refresh_cache.side_effect = Exception("fail")
            resp = client.post(
                "/api/config/refresh",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 500

    def test_list_ssm_parameters_error(self, client):
        with patch("main.get_current_user", new_callable=AsyncMock, return_value={"user_id": "test"}), \
             patch("main.config_service") as mock_cs:
            mock_cs.list_ssm_parameters.side_effect = Exception("fail")
            resp = client.get(
                "/api/config/ssm/parameters",
                headers={"Authorization": "Bearer test-token"},
            )
            assert resp.status_code == 500


class TestProcessChatMessage:
    @pytest.mark.asyncio
    async def test_creates_session_if_missing(self):
        from main import process_chat_message, manager
        from models.chat_models import BedrockResponse

        mock_resp = BedrockResponse(
            response="test response",
            tool_executions=[],
        )

        with patch("main.orchestrator_service") as mock_orch:
            mock_orch.process_message = AsyncMock(return_value=mock_resp)
            result = await process_chat_message(
                message="hello",
                session_id="new-session-123",
                context={},
                user_id="user1",
            )
            assert result.session_id == "new-session-123"
            assert result.response == "test response"

    @pytest.mark.asyncio
    async def test_sends_typing_indicator(self):
        from main import process_chat_message, manager
        from models.chat_models import BedrockResponse, ChatSession

        # Set up a session with an active WebSocket connection
        mock_ws = AsyncMock()
        session_id = "ws-session-456"
        manager.active_connections[session_id] = mock_ws
        manager.sessions[session_id] = ChatSession(
            session_id=session_id,
            created_at=datetime.utcnow(),
            messages=[],
            context={},
        )

        mock_resp = BedrockResponse(response="done", tool_executions=[])

        with patch("main.orchestrator_service") as mock_orch:
            mock_orch.process_message = AsyncMock(return_value=mock_resp)
            await process_chat_message("test", session_id, {}, "user1")
            # Should have sent typing indicators
            assert mock_ws.send_text.call_count >= 2  # typing on + typing off

        # Cleanup
        manager.disconnect(session_id)

    @pytest.mark.asyncio
    async def test_error_stops_typing(self):
        from main import process_chat_message, manager
        from models.chat_models import ChatSession

        mock_ws = AsyncMock()
        session_id = "err-session"
        manager.active_connections[session_id] = mock_ws
        manager.sessions[session_id] = ChatSession(
            session_id=session_id,
            created_at=datetime.utcnow(),
            messages=[],
            context={},
        )

        with patch("main.orchestrator_service") as mock_orch:
            mock_orch.process_message = AsyncMock(side_effect=Exception("boom"))
            with pytest.raises(Exception, match="boom"):
                await process_chat_message("test", session_id, {}, "user1")

        manager.disconnect(session_id)
