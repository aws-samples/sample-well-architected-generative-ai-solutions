"""Unit tests for the orchestrator backend."""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


def test_health_endpoint():
    """Test health check returns healthy."""
    from main import app
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_root_endpoint():
    """Test root returns service info."""
    from main import app
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "agentcore-longrun" in resp.json()["service"]


@pytest.mark.asyncio
async def test_parse_intent():
    """Test intent parsing with mocked Bedrock."""
    with patch("orchestrator.services.intent_service._get_client") as mock:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "content": [{"text": '{"tools": ["ask_agent"], "ack": "Sure", "input": "check stacks"}'}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_resp}
        mock.return_value = mock_client

        from orchestrator.services.intent_service import parse_intent
        result = await parse_intent("check my stacks", [])
        assert result["tools"] == ["ask_agent"]
        assert result["ack"] == "Sure"


@pytest.mark.asyncio
async def test_invoke_agentcore_runtime():
    """Test AgentCore runtime invocation with mock."""
    with patch("orchestrator.services.agentcore_service._get_client") as mock, \
         patch("orchestrator.services.agentcore_service.RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-west-2:123:runtime/test"):
        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read.return_value = b'{"response": "Hello World!"}'
        mock_client.invoke_agent_runtime.return_value = {"response": mock_stream}
        mock.return_value = mock_client

        from orchestrator.services.agentcore_service import invoke_agentcore_runtime
        result = await invoke_agentcore_runtime("hello")
        assert result["response"] == "Hello World!"


@pytest.mark.asyncio
async def test_invoke_agentcore_no_arn():
    """Test graceful handling when ARN not configured."""
    with patch("orchestrator.services.agentcore_service.RUNTIME_ARN", ""):
        from orchestrator.services.agentcore_service import invoke_agentcore_runtime
        result = await invoke_agentcore_runtime("hello")
        assert result.get("error") is True
