"""Tests for services/bedrock_chat_service.py"""

from unittest.mock import MagicMock, patch

import pytest
from services.bedrock_chat_service import BedrockChatService


class TestBedrockChatService:
    def test_init(self):
        svc = BedrockChatService()
        assert svc._bedrock_client is None

    def test_bedrock_client_lazy_init(self):
        svc = BedrockChatService()
        client = svc.bedrock_client
        assert client is not None
        assert svc.bedrock_client is client

    def test_bedrock_client_init_failure(self):
        svc = BedrockChatService()
        with patch("boto3.client", side_effect=Exception("no creds")):
            client = svc.bedrock_client
            assert client is None

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        svc = BedrockChatService()
        svc._bedrock_client = MagicMock()
        result = await svc.health_check()
        assert result == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        svc = BedrockChatService()
        with patch.object(
            type(svc), "bedrock_client", new_callable=lambda: property(lambda self: None)
        ):
            result = await svc.health_check()
            assert result == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        svc = BedrockChatService()
        with patch.object(
            type(svc),
            "bedrock_client",
            new_callable=lambda: property(lambda self: (_ for _ in ()).throw(Exception("fail"))),
        ):
            result = await svc.health_check()
            assert result == "unhealthy"

    @pytest.mark.asyncio
    async def test_process_message(self):
        svc = BedrockChatService()
        result = await svc.process_message("hello")
        assert result["response"] == "Echo: hello"
        assert "timestamp" in result
        assert result["tool_executions"] == []

    @pytest.mark.asyncio
    async def test_process_message_with_context(self):
        svc = BedrockChatService()
        result = await svc.process_message("test", context={"key": "val"})
        assert result["response"] == "Echo: test"
