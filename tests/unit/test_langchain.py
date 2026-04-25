import uuid
from unittest.mock import MagicMock, patch

import pytest

from dai.integrations.langchain import DAICallbackHandler


@pytest.fixture
def run_id():
    return uuid.uuid4()

@pytest.fixture
def callback_handler():
    with patch("dai.client.get_client") as mock_get, patch("dai.integrations.langchain._LANGCHAIN_AVAILABLE", True):
        from dai.client import NoopDAIClient
        mock_get.return_value = NoopDAIClient()
        handler = DAICallbackHandler(
            agent_id="lc-agent",
            decision_type="chat",
            policy_id="test-policy",
            policy_version="1.0.0"
        )
        return handler

def test_langchain_callback_init(callback_handler):
    assert callback_handler.agent_id == "lc-agent"
    assert callback_handler.decision_type == "chat"
    assert callback_handler.policy_id == "test-policy"

def test_langchain_on_agent_action(callback_handler, run_id):
    action = MagicMock()
    action.tool = "search_api"
    callback_handler.on_agent_action(action, run_id=run_id)
    key = str(run_id)
    assert key in callback_handler._run_id_to_evidence
    assert callback_handler._run_id_to_evidence[key] == ["langchain:tool:search_api"]

def test_langchain_on_tool_end(callback_handler, run_id):
    callback_handler._get_or_create_decision(run_id)
    callback_handler.on_tool_end("some result", run_id=run_id)
    key = str(run_id)
    assert "langchain:tool_output" in callback_handler._run_id_to_sources[key]

@patch("dai.builder.Decision.commit_sync")
def test_langchain_on_agent_finish(mock_commit, callback_handler, run_id):
    finish = MagicMock()
    finish.return_values = {"output": "hello world", "confidence": "0.95"}

    callback_handler.on_agent_finish(finish, run_id=run_id)

    assert mock_commit.called
    key = str(run_id)
    assert key not in callback_handler._run_id_to_decision

@patch("dai.builder.Decision.commit_sync")
def test_langchain_on_chain_error(mock_commit, callback_handler, run_id):
    callback_handler._get_or_create_decision(run_id)

    callback_handler.on_chain_error(Exception("test error"), run_id=run_id)

    assert mock_commit.called
    key = str(run_id)
    assert key not in callback_handler._run_id_to_decision
