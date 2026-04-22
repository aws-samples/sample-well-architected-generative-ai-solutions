"""Tests for shared services."""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestVersionConfig:
    def test_default_config(self):
        from shared.services.version_config import VersionConfigService
        svc = VersionConfigService()
        assert svc.version_info["version"] == "agentcore"

    def test_get_version_config(self):
        from shared.services.version_config import VersionConfigService
        svc = VersionConfigService()
        config = svc.get_version_config()
        assert config["version"] == "agentcore"
        assert config["features"]["strands_agents"] is True
        assert config["features"]["agentcore_runtime"] is True
        assert config["graceful_degradation"] is True

    def test_validate_no_warnings_when_env_set(self, monkeypatch):
        monkeypatch.setenv("PARAM_PREFIX", "coa")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
        from shared.services.version_config import VersionConfigService
        svc = VersionConfigService()
        result = svc.validate_version_constraints()
        assert result["valid"] is True
        assert len(result["warnings"]) == 0

    def test_validate_warnings_when_env_missing(self):
        from shared.services.version_config import VersionConfigService
        svc = VersionConfigService()
        result = svc.validate_version_constraints()
        assert result["valid"] is True
        assert len(result["warnings"]) > 0

    def test_feature_flags(self):
        from shared.services.version_config import VersionConfigService
        svc = VersionConfigService()
        flags = svc.get_feature_flags()
        assert flags["strands_agents"] is True

    def test_service_flags(self):
        from shared.services.version_config import VersionConfigService
        svc = VersionConfigService()
        flags = svc.get_service_flags()
        assert flags["strands_discovery"] is True

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, monkeypatch):
        monkeypatch.setenv("PARAM_PREFIX", "coa")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
        from shared.services.version_config import VersionConfigService
        svc = VersionConfigService()
        assert await svc.health_check() == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        from shared.services.version_config import VersionConfigService
        svc = VersionConfigService()
        assert await svc.health_check() == "degraded"

    def test_is_agentcore_version(self):
        from shared.services.version_config import is_agentcore_version
        assert is_agentcore_version() is True

    def test_get_version_specific_config(self):
        from shared.services.version_config import get_version_specific_config
        config = get_version_specific_config()
        assert config["version"] == "agentcore"

    def test_get_version_config_service_singleton(self):
        import shared.services.version_config as vc
        vc._version_config_service = None
        svc1 = vc.get_version_config_service()
        svc2 = vc.get_version_config_service()
        assert svc1 is svc2


class TestConfigService:
    def test_get_config_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "test_value")
        from shared.services.config_service import get_config
        assert get_config("TEST_KEY") == "test_value"

    def test_get_config_default(self):
        from shared.services.config_service import get_config
        assert get_config("NONEXISTENT_KEY", "default") == "default"

    def test_get_config_none(self):
        from shared.services.config_service import get_config
        assert get_config("NONEXISTENT_KEY") is None


class TestAWSConfigService:
    @pytest.mark.asyncio
    async def test_get_current_config_success(self):
        from shared.services.aws_config_service import AWSConfigService
        svc = AWSConfigService()
        with patch.object(svc, '_sts_client', None):
            with patch("boto3.client") as mock_client:
                sts = MagicMock()
                sts.get_caller_identity.return_value = {
                    "Account": "123456789012",
                    "Arn": "arn:aws:sts::123456789012:role/test",
                }
                mock_client.return_value = sts
                result = await svc.get_current_config()
                assert result["status"] == "configured"
                assert result["account_id"] == "123456789012"

    @pytest.mark.asyncio
    async def test_get_current_config_failure(self):
        from shared.services.aws_config_service import AWSConfigService
        svc = AWSConfigService()
        svc._sts_client = MagicMock()
        svc._sts_client.get_caller_identity.side_effect = Exception("fail")
        result = await svc.get_current_config()
        assert result["status"] == "not_configured"

    @pytest.mark.asyncio
    async def test_update_config(self):
        from shared.services.aws_config_service import AWSConfigService
        svc = AWSConfigService()
        svc._sts_client = MagicMock()
        svc._sts_client.get_caller_identity.return_value = {"Account": "123", "Arn": "arn"}
        result = await svc.update_config()
        assert "status" in result


class TestErrorHandler:
    def test_import(self):
        from shared.services.error_handler import ErrorHandler
        handler = ErrorHandler()
        assert handler is not None


class TestBedrockModelService:
    def test_import(self):
        from shared.services.bedrock_model_service import BedrockModelService
        svc = BedrockModelService()
        assert svc is not None
