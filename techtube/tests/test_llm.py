from unittest import mock

import pytest

from techtube.llm import LLMError, Ollama, parse_json
from techtube.script import write_script


def test_parse_json_variants():
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert parse_json('Sure! Here it is: {"a": 3} hope it helps') == {"a": 3}
    assert parse_json("[1, 2]") == [1, 2]
    assert parse_json("not json") is None
    assert parse_json("") is None


class FakeResp:
    def __init__(self, content, status=200):
        self.status_code = status
        self.ok = status == 200
        self._content = content
        self.text = content

    def json(self):
        return {"message": {"content": self._content}}


def test_chat_json_retries_once():
    llm = Ollama("m")
    answers = iter([FakeResp("oops not json"), FakeResp('{"ok": true}')])
    with mock.patch("techtube.llm.requests.post", side_effect=lambda *a, **k: next(answers)) as p:
        assert llm.chat_json("q") == {"ok": True}
        assert p.call_count == 2
        body = p.call_args.kwargs["json"]
        assert body["format"] == "json" and body["stream"] is False


def test_missing_model_message():
    llm = Ollama("tiny")
    with mock.patch("techtube.llm.requests.post", return_value=FakeResp("", 404)):
        with pytest.raises(LLMError, match="ollama pull tiny"):
            llm.chat("hi")


def test_write_script_with_mocked_model():
    payload = """{"title": "Fix Slow PC", "sections": [
      {"heading": "Slow PC?", "visual": "title", "narration": "Your PC is slow. Let's fix it."},
      {"heading": "Step 1: Restart", "visual": "steps", "bullets": ["Save work", "Restart"],
       "short": true, "narration": "Restart your PC first."},
      {"heading": "Which fix worked?", "visual": "outro", "narration": "Tell me below."}]}"""
    llm = Ollama("m")
    with mock.patch("techtube.llm.requests.post", return_value=FakeResp(payload)):
        s = write_script(llm, "slow pc")
    assert s.title == "Fix Slow PC"
    assert s.problem == "slow pc"
    assert s.sections[1].short
