"""Tests for shared middleware."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestCorsMiddleware:
    def test_get_cors_config(self):
        from shared.middleware.cors_middleware import get_cors_config_for_version
        config = get_cors_config_for_version()
        assert config["allow_credentials"] is True
        assert "Authorization" in config["allow_headers"]
        assert "X-Strands-Agent" in config["allow_headers"]
        assert "X-AgentCore-Session" in config["allow_headers"]

    def test_get_cors_config_with_version(self):
        from shared.middleware.cors_middleware import get_cors_config_for_version
        config = get_cors_config_for_version("agentcore")
        assert "GET" in config["allow_methods"]
        assert "POST" in config["allow_methods"]

    def test_configure_cors_for_version(self):
        from shared.middleware.cors_middleware import configure_cors_for_version
        app = FastAPI()
        configure_cors_for_version(app)  # Should not raise

    def test_get_default_cors_origins(self):
        from shared.middleware.cors_middleware import get_default_cors_origins
        origins = get_default_cors_origins()
        assert isinstance(origins, list)
        assert len(origins) > 0


class TestAuthMiddleware:
    def test_auth_config_skip_paths(self):
        from shared.middleware.auth_middleware import AuthConfig
        config = AuthConfig()
        assert "/health" in config.skip_auth_paths
        assert "/docs" in config.skip_auth_paths
        assert "/api/agentcore/status" in config.skip_auth_paths

    def test_auth_config_default_version(self):
        from shared.middleware.auth_middleware import AuthConfig
        config = AuthConfig()
        assert config.version == "agentcore"


class TestLoggingMiddleware:
    def test_setup_request_logging(self):
        from shared.middleware.logging_middleware import setup_request_logging
        app = FastAPI()
        setup_request_logging(app=app, version="agentcore")  # Should not raise
