"""Response parsing for the Computer Use driver, using shapes captured from the live
Interactions API (v1beta) on 2026-11-16."""

from app.engines.qa.computer_use import ENDPOINT, _calls, _final_text, _tokens

LIVE_TEXT_REPLY = {
    "id": "v1_example",
    "status": "completed",
    "usage": {
        "total_tokens": 15,
        "total_input_tokens": 14,
        "input_tokens_by_modality": [{"modality": "text", "tokens": 14}],
        "total_cached_tokens": 0,
        "total_output_tokens": 1,
        "total_tool_use_tokens": 0,
        "total_thought_tokens": 0,
        "initial_input_tokens": 14,
    },
    "steps": [
        {"signature": "opaque", "type": "thought"},
        {"content": [{"text": "OK", "type": "text"}], "type": "model_output"},
    ],
}


def test_endpoint_uses_v1beta():
    assert "/v1beta/interactions" in ENDPOINT


def test_live_usage_counts_input_once_and_thoughts_as_output():
    assert _tokens(LIVE_TEXT_REPLY) == (14, 1)
    with_thoughts = {
        **LIVE_TEXT_REPLY,
        "usage": {**LIVE_TEXT_REPLY["usage"], "total_thought_tokens": 30},
    }
    assert _tokens(with_thoughts) == (14, 31)


def test_live_text_reply_is_the_final_answer_with_no_calls():
    assert _calls(LIVE_TEXT_REPLY) == []
    assert _final_text(LIVE_TEXT_REPLY) == "OK"


def test_other_usage_shapes_still_count():
    assert _tokens({"usage": {"prompt_tokens": 8, "completion_tokens": 4}}) == (8, 4)
    assert _tokens({"usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2}}) == (5, 2)
