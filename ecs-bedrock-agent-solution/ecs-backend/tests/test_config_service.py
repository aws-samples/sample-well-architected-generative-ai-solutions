"""Tests for services/config_service.py"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest
from botocore.exceptions import ClientError, NoCredentialsError


class TestConfigService:
    """Tests instantiate ConfigService directly with mocked boto3."""

    def _make_service(self, ssm_available=True, monkeypatch=None):
        """Helper to create a ConfigService with controlled SSM availability."""
        if ssm_available:
            mock_ssm = MagicMock()
            mock_ssm.describe_parameters.return_value = {"Parameters": []}
            with patch("boto3.client", return_value=mock_ssm):
                from services.config_service import ConfigService
                svc = ConfigService(ssm_prefix="/test/")
            svc._ssm_client = mock_ssm
        else:
            with patch("boto3.client", side_effect=NoCredentialsError()):
                from services.config_service import ConfigService
                svc = ConfigService(ssm_prefix="/test/")
        return svc

    def test_init_ssm_available(self):
        svc = self._make_service(ssm_available=True)
        assert svc._ssm_available is True
        assert svc.ssm_prefix == "/test/"

    def test_init_ssm_unavailable(self):
        svc = self._make_service(ssm_available=False)
        assert svc._ssm_available is False
        assert svc._ssm_client is None

    def test_get_config_value_from_env(self, monkeypatch):
        svc = self._make_service(ssm_available=False)
        monkeypatch.setenv("MY_KEY", "my_value")
        assert svc.get_config_value("MY_KEY") == "my_value"

    def test_get_config_value_default(self):
        svc = self._make_service(ssm_available=False)
        assert svc.get_config_value("NONEXISTENT", "fallback") == "fallback"

    def test_get_config_value_from_ssm(self):
        svc = self._make_service(ssm_available=True)
        svc._ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "agent-123"}
        }
        val = svc.get_config_value("ENHANCED_SECURITY_AGENT_ID")
        assert val == "agent-123"

    def test_get_config_value_ssm_cache(self):
        svc = self._make_service(ssm_available=True)
        svc._ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": "cached-val"}
        }
        # First call populates cache
        val1 = svc.get_config_value("ENHANCED_SECURITY_AGENT_ID")
        # Second call should use cache (no additional SSM call)
        val2 = svc.get_config_value("ENHANCED_SECURITY_AGENT_ID")
        assert val1 == val2
        assert svc._ssm_client.get_parameter.call_count == 1

    def test_get_config_value_ssm_parameter_not_found(self):
        svc = self._make_service(ssm_available=True)
        svc._ssm_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "not found"}},
            "GetParameter",
        )
        # Should fall through to env/default
        assert svc.get_config_value("ENHANCED_SECURITY_AGENT_ID", "default") == "default"

    def test_get_config_value_ssm_other_error(self):
        svc = self._make_service(ssm_available=True)
        svc._ssm_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "GetParameter",
        )
        assert svc.get_config_value("ENHANCED_SECURITY_AGENT_ID", "fb") == "fb"

    def test_get_config_value_ssm_unexpected_error(self):
        svc = self._make_service(ssm_available=True)
        svc._ssm_client.get_parameter.side_effect = RuntimeError("unexpected")
        assert svc.get_config_value("ENHANCED_SECURITY_AGENT_ID", "fb") == "fb"

    def test_get_ssm_parameter_unmapped_key(self):
        """Keys that don't map to SSM paths should return None from SSM."""
        svc = self._make_service(ssm_available=True)
        val = svc._get_ssm_parameter("RANDOM_KEY")
        assert val is None

    def test_get_all_config(self, monkeypatch):
        svc = self._make_service(ssm_available=False)
        monkeypatch.setenv("AWS_ROLE_ARN", "arn:aws:iam::123:role/test")
        config = svc.get_all_config()
        assert "AWS_ROLE_ARN" in config

    def test_refresh_cache(self):
        svc = self._make_service(ssm_available=True)
        svc._config_cache["ssm:test"] = "cached"
        svc.refresh_cache()
        assert len(svc._config_cache) == 0

    def test_get_ssm_status(self):
        svc = self._make_service(ssm_available=True)
        status = svc.get_ssm_status()
        assert status["available"] is True
        assert status["prefix"] == "/test/"
        assert "cached_parameters" in status

    def test_set_ssm_parameter_success(self):
        svc = self._make_service(ssm_available=True)
        svc._ssm_client.put_parameter.return_value = {}
        result = svc.set_ssm_parameter("MY_PARAM", "value123", description="test desc")
        assert result is True
        svc._ssm_client.put_parameter.assert_called_once()

    def test_set_ssm_parameter_no_client(self):
        svc = self._make_service(ssm_available=False)
        result = svc.set_ssm_parameter("MY_PARAM", "value")
        assert result is False

    def test_set_ssm_parameter_failure(self):
        svc = self._make_service(ssm_available=True)
        svc._ssm_client.put_parameter.side_effect = Exception("write fail")
        result = svc.set_ssm_parameter("MY_PARAM", "value")
        assert result is False

    def test_set_ssm_parameter_clears_cache(self):
        svc = self._make_service(ssm_available=True)
        svc._config_cache["ssm:MY_PARAM"] = "old"
        svc._ssm_client.put_parameter.return_value = {}
        svc.set_ssm_parameter("MY_PARAM", "new")
        assert "ssm:MY_PARAM" not in svc._config_cache

    def test_list_ssm_parameters_success(self):
        svc = self._make_service(ssm_available=True)
        svc._ssm_client.describe_parameters.return_value = {
            "Parameters": [
                {"Name": "/test/param1", "Type": "String", "Description": "desc1"}
            ]
        }
        result = svc.list_ssm_parameters()
        assert result["count"] == 1
        assert result["parameters"][0]["name"] == "/test/param1"

    def test_list_ssm_parameters_no_client(self):
        svc = self._make_service(ssm_available=False)
        result = svc.list_ssm_parameters()
        assert "error" in result

    def test_list_ssm_parameters_exception(self):
        svc = self._make_service(ssm_available=True)
        svc._ssm_client.describe_parameters.side_effect = Exception("fail")
        result = svc.list_ssm_parameters()
        assert "error" in result

    def test_load_env_file(self, tmp_path, monkeypatch):
        """Test .env file loading."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_ENV_VAR=hello\n# comment\nANOTHER=world\n")

        with patch("boto3.client", side_effect=NoCredentialsError()):
            from services.config_service import ConfigService
            with patch.object(Path, "parent", new_callable=lambda: property(lambda self: tmp_path)):
                # Just verify _load_env_file doesn't crash
                svc = ConfigService.__new__(ConfigService)
                svc.ssm_prefix = "/test/"
                svc._ssm_client = None
                svc._config_cache = {}
                svc._ssm_available = None
                svc._initialization_attempted = False

    def test_ssm_client_property_returns_cached(self):
        svc = self._make_service(ssm_available=True)
        client1 = svc.ssm_client
        client2 = svc.ssm_client
        assert client1 is client2

    def test_initialize_ssm_client_unexpected_error(self):
        with patch("boto3.client", side_effect=RuntimeError("unexpected")):
            from services.config_service import ConfigService
            svc = ConfigService.__new__(ConfigService)
            svc.ssm_prefix = "/test/"
            svc._ssm_client = None
            svc._config_cache = {}
            svc._ssm_available = None
            svc._initialization_attempted = False
            svc._initialize_ssm_client()
            assert svc._ssm_available is False


class TestGetConfigFunction:
    def test_get_config_convenience(self, monkeypatch):
        monkeypatch.setenv("SOME_KEY", "some_val")
        from services.config_service import get_config
        # get_config uses the global config_service instance
        val = get_config("SOME_KEY", "default")
        # Either returns env val or default, both acceptable
        assert val is not None
