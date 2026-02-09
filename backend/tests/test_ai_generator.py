import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add backend/ to path so we can import ai_generator directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai_generator import AIGenerator

# --- Helpers to build mock response objects ---


def make_text_block(text="Hello"):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_tool_use_block(
    name="search_course_content", tool_id="tool_1", tool_input=None
):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = tool_id
    block.input = tool_input or {"query": "test"}
    return block


def make_response(stop_reason="end_turn", content=None):
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = content or [make_text_block()]
    return resp


@pytest.fixture
def generator():
    with patch("ai_generator.anthropic.Anthropic"):
        gen = AIGenerator(api_key="test-key", model="test-model")
    return gen


@pytest.fixture
def mock_tool_manager():
    tm = MagicMock()
    tm.execute_tool = MagicMock(return_value="tool result text")
    return tm


DUMMY_TOOLS = [
    {"name": "search_course_content", "description": "test", "input_schema": {}}
]


# --- Tests ---


class TestDirectResponses:
    def test_direct_response_no_tools(self, generator):
        """No tools provided -> single API call, text returned."""
        text_resp = make_response(content=[make_text_block("Direct answer")])
        generator.client.messages.create = MagicMock(return_value=text_resp)

        result = generator.generate_response("What is AI?")

        assert result == "Direct answer"
        assert generator.client.messages.create.call_count == 1
        # Verify no tools in call
        call_kwargs = generator.client.messages.create.call_args[1]
        assert "tools" not in call_kwargs

    def test_direct_response_with_tools_not_used(self, generator, mock_tool_manager):
        """Tools offered but Claude doesn't use them (stop_reason != tool_use)."""
        text_resp = make_response(
            stop_reason="end_turn", content=[make_text_block("I know this")]
        )
        generator.client.messages.create = MagicMock(return_value=text_resp)

        result = generator.generate_response(
            "General question", tools=DUMMY_TOOLS, tool_manager=mock_tool_manager
        )

        assert result == "I know this"
        assert generator.client.messages.create.call_count == 1
        mock_tool_manager.execute_tool.assert_not_called()


class TestSingleToolRound:
    def test_single_tool_round(self, generator, mock_tool_manager):
        """One tool call -> results -> text answer. 2 API calls, 1 tool execution."""
        tool_resp = make_response(
            stop_reason="tool_use",
            content=[
                make_tool_use_block("search_course_content", "t1", {"query": "AI"})
            ],
        )
        # On intermediate round, Claude calls tool; on follow-up (with tools still attached
        # since round 0 < MAX-1), Claude returns text
        final_resp = make_response(content=[make_text_block("Here is the answer")])
        generator.client.messages.create = MagicMock(
            side_effect=[tool_resp, final_resp]
        )

        result = generator.generate_response(
            "Search AI", tools=DUMMY_TOOLS, tool_manager=mock_tool_manager
        )

        assert result == "Here is the answer"
        assert generator.client.messages.create.call_count == 2
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="AI"
        )


class TestTwoSequentialToolRounds:
    def test_two_sequential_tool_rounds(self, generator, mock_tool_manager):
        """Outline -> search -> text. 3 API calls, 2 tool executions."""
        # Round 0: initial call returns tool_use
        resp1 = make_response(
            stop_reason="tool_use",
            content=[
                make_tool_use_block("get_course_outline", "t1", {"course": "MCP"})
            ],
        )
        # Round 0 follow-up (tools attached): Claude calls another tool
        resp2 = make_response(
            stop_reason="tool_use",
            content=[
                make_tool_use_block("search_course_content", "t2", {"query": "agents"})
            ],
        )
        # Round 1 follow-up (no tools): Claude returns text
        resp3 = make_response(content=[make_text_block("Combined answer")])

        generator.client.messages.create = MagicMock(side_effect=[resp1, resp2, resp3])
        mock_tool_manager.execute_tool = MagicMock(
            side_effect=["outline data", "content data"]
        )

        result = generator.generate_response(
            "Multi-step question", tools=DUMMY_TOOLS, tool_manager=mock_tool_manager
        )

        assert result == "Combined answer"
        assert generator.client.messages.create.call_count == 3
        assert mock_tool_manager.execute_tool.call_count == 2

        # Verify tool calls were made with correct args
        calls = mock_tool_manager.execute_tool.call_args_list
        assert calls[0][0] == ("get_course_outline",)
        assert calls[0][1] == {"course": "MCP"}
        assert calls[1][0] == ("search_course_content",)
        assert calls[1][1] == {"query": "agents"}

    def test_max_rounds_enforced(self, generator, mock_tool_manager):
        """After 2 tool rounds, final call has no tools attached."""
        resp1 = make_response(
            stop_reason="tool_use",
            content=[make_tool_use_block("get_course_outline", "t1", {"course": "X"})],
        )
        resp2 = make_response(
            stop_reason="tool_use",
            content=[
                make_tool_use_block("search_course_content", "t2", {"query": "Y"})
            ],
        )
        resp3 = make_response(content=[make_text_block("Final")])

        generator.client.messages.create = MagicMock(side_effect=[resp1, resp2, resp3])

        result = generator.generate_response(
            "test", tools=DUMMY_TOOLS, tool_manager=mock_tool_manager
        )

        assert result == "Final"
        # 3rd call (index 2) should NOT have tools
        third_call_kwargs = generator.client.messages.create.call_args_list[2][1]
        assert "tools" not in third_call_kwargs

        # 2nd call (index 1) SHOULD have tools (intermediate round)
        second_call_kwargs = generator.client.messages.create.call_args_list[1][1]
        assert "tools" in second_call_kwargs

        # Verify messages list in 3rd call has 5 entries:
        # user, assistant+tool1, tool_result1, assistant+tool2, tool_result2
        third_call_messages = third_call_kwargs["messages"]
        assert len(third_call_messages) == 5
        assert third_call_messages[0]["role"] == "user"
        assert third_call_messages[1]["role"] == "assistant"
        assert third_call_messages[2]["role"] == "user"
        assert third_call_messages[3]["role"] == "assistant"
        assert third_call_messages[4]["role"] == "user"


class TestErrorHandling:
    def test_tool_exception_handled(self, generator, mock_tool_manager):
        """execute_tool raises -> is_error result, Claude still responds."""
        tool_resp = make_response(
            stop_reason="tool_use",
            content=[
                make_tool_use_block("search_course_content", "t1", {"query": "fail"})
            ],
        )
        final_resp = make_response(
            content=[make_text_block("Sorry, I couldn't find that")]
        )
        generator.client.messages.create = MagicMock(
            side_effect=[tool_resp, final_resp]
        )
        mock_tool_manager.execute_tool = MagicMock(
            side_effect=RuntimeError("DB connection failed")
        )

        result = generator.generate_response(
            "bad query", tools=DUMMY_TOOLS, tool_manager=mock_tool_manager
        )

        assert result == "Sorry, I couldn't find that"
        assert generator.client.messages.create.call_count == 2

        # Verify the tool result sent to Claude has is_error=True
        second_call_messages = generator.client.messages.create.call_args_list[1][1][
            "messages"
        ]
        tool_result_msg = second_call_messages[2]  # user message with tool_results
        assert tool_result_msg["content"][0]["is_error"] is True
        assert "DB connection failed" in tool_result_msg["content"][0]["content"]

    def test_no_tool_manager_returns_text(self, generator):
        """tool_manager=None with tool_use response -> returns text from response."""
        # Response has both a text block and a tool_use block, but stop_reason is tool_use
        resp = make_response(
            stop_reason="tool_use",
            content=[make_text_block("Partial text"), make_tool_use_block()],
        )
        generator.client.messages.create = MagicMock(return_value=resp)

        result = generator.generate_response(
            "query", tools=DUMMY_TOOLS, tool_manager=None
        )

        assert result == "Partial text"
        assert generator.client.messages.create.call_count == 1


class TestSystemPromptAndExtraction:
    def test_conversation_history_in_system(self, generator):
        """History is appended to system prompt in the API call."""
        text_resp = make_response(content=[make_text_block("answer")])
        generator.client.messages.create = MagicMock(return_value=text_resp)

        generator.generate_response(
            "question", conversation_history="User: hi\nAI: hello"
        )

        call_kwargs = generator.client.messages.create.call_args[1]
        assert "Previous conversation:" in call_kwargs["system"]
        assert "User: hi" in call_kwargs["system"]

    def test_text_extraction_from_mixed_content(self, generator):
        """TextBlock not at index 0 -> still found correctly."""
        tool_block = make_tool_use_block()
        text_block = make_text_block("The real answer")
        resp = make_response(stop_reason="end_turn", content=[tool_block, text_block])
        generator.client.messages.create = MagicMock(return_value=resp)

        result = generator.generate_response("query")

        assert result == "The real answer"
