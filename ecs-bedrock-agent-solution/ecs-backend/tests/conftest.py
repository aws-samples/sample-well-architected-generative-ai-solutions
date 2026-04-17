"""
Shared test fixtures for the ECS backend test suite.
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the backend root is on sys.path so imports like `from services.X import Y` work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Environment – set required env vars *before* any application code imports
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Provide a minimal environment for every test."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("USER_POOL_ID", "us-east-1_TestPool")
    monkeypatch.setenv("WEB_APP_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("USE_ENHANCED_AGENT", "false")


# ---------------------------------------------------------------------------
# Mock boto3 globally so no real AWS calls happen
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _mock_boto3(monkeypatch):
    """Patch boto3.client globally to return a MagicMock."""
    mock_client = MagicMock()
    monkeypatch.setattr("boto3.client", lambda *a, **kw: mock_client)
    return mock_client


# ---------------------------------------------------------------------------
# Chat model helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_tool_execution():
    from models.chat_models import ToolExecution, ToolExecutionStatus

    return ToolExecution(
        tool_name="CheckSecurityServices",
        parameters={"region": "us-east-1"},
        result={"status": "ok"},
        timestamp=datetime.utcnow(),
        status=ToolExecutionStatus.SUCCESS,
    )


@pytest.fixture
def sample_chat_message():
    from models.chat_models import ChatMessage

    return ChatMessage(
        role="user",
        content="Check my security",
        timestamp=datetime.utcnow(),
    )


@pytest.fixture
def sample_session():
    from models.chat_models import ChatSession

    return ChatSession(
        session_id="test-session-1",
        created_at=datetime.utcnow(),
        messages=[],
        context={},
    )
