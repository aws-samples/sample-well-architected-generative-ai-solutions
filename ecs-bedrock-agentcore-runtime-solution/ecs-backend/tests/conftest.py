"""Shared test fixtures for COA Backend tests."""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure clean environment for each test."""
    monkeypatch.delenv("BACKEND_MODE", raising=False)
    monkeypatch.delenv("FORCE_REAL_AGENTCORE", raising=False)
    monkeypatch.delenv("PARAM_PREFIX", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)


@pytest.fixture
def mock_boto3_ssm():
    """Mock boto3 SSM client."""
    with patch("boto3.client") as mock_client:
        ssm = MagicMock()
        mock_client.return_value = ssm
        yield ssm


@pytest.fixture
def mock_boto3_sts():
    """Mock boto3 STS client."""
    with patch("boto3.client") as mock_client:
        sts = MagicMock()
        sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/test-role/session",
        }
        mock_client.return_value = sts
        yield sts
