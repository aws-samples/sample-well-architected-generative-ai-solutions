"""Tests for services/aws_config_service.py"""

from unittest.mock import MagicMock, patch

import pytest
from services.aws_config_service import AWSConfigService


class TestAWSConfigService:
    def test_init(self):
        svc = AWSConfigService()
        assert svc._sts_client is None

    def test_sts_client_lazy_init(self):
        svc = AWSConfigService()
        client = svc.sts_client
        assert client is not None
        # Cached
        assert svc.sts_client is client

    def test_sts_client_init_failure(self):
        svc = AWSConfigService()
        with patch("boto3.client", side_effect=Exception("fail")):
            client = svc.sts_client
            assert client is None

    @pytest.mark.asyncio
    async def test_get_current_config_success(self):
        svc = AWSConfigService()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:role/test",
        }
        svc._sts_client = mock_sts

        config = await svc.get_current_config()
        assert config["status"] == "configured"
        assert config["account_id"] == "123456789012"
        assert config["role_arn"] == "arn:aws:iam::123456789012:role/test"

    @pytest.mark.asyncio
    async def test_get_current_config_no_client(self):
        svc = AWSConfigService()
        svc._sts_client = None
        # Force the property to return None
        with patch.object(type(svc), "sts_client", new_callable=lambda: property(lambda self: None)):
            config = await svc.get_current_config()
            assert config["status"] == "not_configured"
            assert config["account_id"] is None

    @pytest.mark.asyncio
    async def test_get_current_config_sts_exception(self):
        svc = AWSConfigService()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = Exception("Access denied")
        svc._sts_client = mock_sts

        config = await svc.get_current_config()
        assert config["status"] == "not_configured"

    @pytest.mark.asyncio
    async def test_update_config_delegates_to_get(self):
        svc = AWSConfigService()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "111",
            "Arn": "arn:aws:iam::111:role/x",
        }
        svc._sts_client = mock_sts

        result = await svc.update_config(region="eu-west-1")
        assert result["status"] == "configured"
