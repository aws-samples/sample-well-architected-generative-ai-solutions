"""Tests for models/chat_models.py"""

from datetime import datetime

import pytest
from models.chat_models import (
    BedrockResponse,
    ChatMessage,
    ChatSession,
    ToolExecution,
    ToolExecutionStatus,
)


class TestToolExecutionStatus:
    def test_enum_values(self):
        assert ToolExecutionStatus.SUCCESS == "success"
        assert ToolExecutionStatus.ERROR == "error"
        assert ToolExecutionStatus.PENDING == "pending"

    def test_enum_is_string(self):
        assert isinstance(ToolExecutionStatus.SUCCESS, str)


class TestToolExecution:
    def test_create_minimal(self):
        te = ToolExecution(tool_name="test_tool", timestamp=datetime.utcnow())
        assert te.tool_name == "test_tool"
        assert te.parameters == {}
        assert te.result is None
        assert te.status == ToolExecutionStatus.SUCCESS

    def test_create_full(self):
        now = datetime.utcnow()
        te = ToolExecution(
            tool_name="CheckSecurity",
            parameters={"region": "us-east-1"},
            result={"ok": True},
            timestamp=now,
            status=ToolExecutionStatus.ERROR,
            error_message="boom",
            tool_input={"a": 1},
            tool_output="output",
        )
        assert te.error_message == "boom"
        assert te.tool_input == {"a": 1}
        assert te.tool_output == "output"

    def test_model_dump(self):
        te = ToolExecution(tool_name="t", timestamp=datetime.utcnow())
        d = te.model_dump()
        assert "tool_name" in d
        assert "status" in d


class TestChatMessage:
    def test_create_user_message(self, sample_chat_message):
        assert sample_chat_message.role == "user"
        assert sample_chat_message.tool_executions == []

    def test_create_assistant_message_with_tools(self, sample_tool_execution):
        msg = ChatMessage(
            role="assistant",
            content="Here are results",
            timestamp=datetime.utcnow(),
            tool_executions=[sample_tool_execution],
        )
        assert len(msg.tool_executions) == 1
        assert msg.tool_executions[0].tool_name == "CheckSecurityServices"


class TestChatSession:
    def test_create_empty_session(self, sample_session):
        assert sample_session.session_id == "test-session-1"
        assert sample_session.messages == []
        assert sample_session.context == {}

    def test_session_with_messages(self, sample_chat_message):
        session = ChatSession(
            session_id="s1",
            created_at=datetime.utcnow(),
            messages=[sample_chat_message],
            context={"key": "val"},
        )
        assert len(session.messages) == 1
        assert session.context["key"] == "val"


class TestBedrockResponse:
    def test_auto_timestamp(self):
        resp = BedrockResponse(response="hello")
        assert resp.timestamp is not None

    def test_explicit_timestamp(self):
        now = datetime.utcnow()
        resp = BedrockResponse(response="hello", timestamp=now)
        assert resp.timestamp == now

    def test_full_response(self, sample_tool_execution):
        resp = BedrockResponse(
            response="Analysis complete",
            tool_executions=[sample_tool_execution],
            structured_data={"findings": []},
            human_summary="All good",
            model_id="claude-3",
            session_id="s1",
        )
        assert resp.model_id == "claude-3"
        assert resp.human_summary == "All good"
        assert len(resp.tool_executions) == 1

    def test_defaults(self):
        resp = BedrockResponse(response="hi")
        assert resp.tool_executions == []
        assert resp.structured_data is None
        assert resp.human_summary is None
        assert resp.model_id is None
        assert resp.session_id is None
