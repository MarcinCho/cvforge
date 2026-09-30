import pytest

from cvforge.llm.base import LLMError
from cvforge.llm.command import CommandProvider
from cvforge.llm.fake import FakeProvider
from cvforge.llm.structured import ask_json, extract_json
from cvforge.models import Language


def test_extract_json_from_chatty_output():
    raw = 'Sure! Here it is:\n```json\n{"name": "English", "level": "C1 {x}"}\n```\nAnything else?'
    assert extract_json(raw) == '{"name": "English", "level": "C1 {x}"}'


def test_ask_json_retries_with_validation_feedback():
    fake = FakeProvider(["not json at all", '{"name": "English"}', '{"name": "English", "level": "C1"}'])
    lang = ask_json(fake, "give me a language", Language, max_retries=2)
    assert lang.level == "C1"
    assert "previous answer was invalid" in fake.prompts[1].lower()
    assert "level" in fake.prompts[2]  # the validation error names the missing field


def test_ask_json_gives_up():
    with pytest.raises(LLMError):
        ask_json(FakeProvider(["nope"] * 3), "x", Language, max_retries=2)


def test_command_provider_stdin_and_prompt_file():
    assert CommandProvider("cat").complete("hello") == "hello"
    assert CommandProvider("cat {prompt_file}").complete("from file") == "from file"


def test_command_provider_errors():
    with pytest.raises(LLMError, match="not found"):
        CommandProvider("definitely-not-a-real-llm-cli").complete("x")
    with pytest.raises(LLMError, match="failed"):
        CommandProvider("false").complete("x")


def test_manual_provider_waits_for_answer_file(tmp_path):
    import threading

    from cvforge.llm.manual import ManualProvider

    prov = ManualProvider(tmp_path, timeout_s=10, poll_s=0.05)

    def answer():
        import time

        while not (tmp_path / "prompt-1.md").exists():
            time.sleep(0.02)
        (tmp_path / "answer-1.md").write_text("pong", encoding="utf-8")

    threading.Thread(target=answer).start()
    assert prov.complete("ping") == "pong"
    assert (tmp_path / "prompt-1.md").read_text() == "ping"
