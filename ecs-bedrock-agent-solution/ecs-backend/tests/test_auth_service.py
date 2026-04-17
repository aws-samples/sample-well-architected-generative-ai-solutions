"""Tests for services/auth_service.py"""

from unittest.mock import MagicMock, patch

import pytest
from services.auth_service import AuthService


class TestAuthService:
    def test_init(self):
        svc = AuthService()
        assert svc._cognito_client is None

    def test_cognito_client_lazy_init(self):
        svc = AuthService()
        # boto3.client is mocked globally, so accessing .cognito_client triggers init
        client = svc.cognito_client
        assert client is not None
        # Second access returns same instance
        assert svc.cognito_client is client

    def test_cognito_client_init_failure(self):
        svc = AuthService()
        with patch("boto3.client", side_effect=Exception("no creds")):
            client = svc.cognito_client
            assert client is None

    @pytest.mark.asyncio
    async def test_verify_token_returns_demo_user(self):
        svc = AuthService()
        user = await svc.verify_token("some-token")
        assert user["user_id"] == "demo_user"
        assert user["email"] == "demo@example.com"

    @pytest.mark.asyncio
    async def test_verify_token_different_tokens(self):
        svc = AuthService()
        user1 = await svc.verify_token("token-a")
        user2 = await svc.verify_token("token-b")
        # Both return same demo user in current implementation
        assert user1 == user2
