import os

from app import config, llm


def test_parse_env_handles_comments_quotes_and_export():
    text = """
# a comment
LLM_PROVIDER=groq
GROQ_API_KEY="abc123"
LLM_MODEL = 'openai/gpt-oss-120b'
export EXTRA=1
NOTE=hello # trailing comment
EMPTY=
not a setting
"""
    assert config.parse_env(text) == {
        "LLM_PROVIDER": "groq", "GROQ_API_KEY": "abc123", "LLM_MODEL": "openai/gpt-oss-120b",
        "EXTRA": "1", "NOTE": "hello", "EMPTY": "",
    }


def test_missing_file_is_not_an_error(tmp_path):
    assert config.load_env(tmp_path / "nope.env") == []


def test_env_file_wins_over_stale_settings_and_survives_a_bom(tmp_path, monkeypatch):
    for k in ("LLM_PROVIDER", "GROQ_API_KEY", "LLM_MODEL"):
        monkeypatch.setenv(k, "stale")                    # registers the variable for cleanup after the test
    monkeypatch.setenv("LLM_PROVIDER", "gemini")          # the leftover that caused the original confusion
    f = tmp_path / ".env"
    f.write_text("LLM_PROVIDER=groq\nGROQ_API_KEY=key-from-file\nLLM_MODEL=m\n", encoding="utf-8-sig")
    assert config.load_env(f) == ["LLM_PROVIDER", "GROQ_API_KEY", "LLM_MODEL"]
    assert os.environ["LLM_PROVIDER"] == "groq" and os.environ["GROQ_API_KEY"] == "key-from-file"


def test_make_llm_reads_the_env_file(tmp_path, monkeypatch):
    for k in ("LLM_PROVIDER", "GROQ_API_KEY", "LLM_MODEL"):
        monkeypatch.setenv(k, "stale")
    f = tmp_path / ".env"
    f.write_text("LLM_PROVIDER=groq\nGROQ_API_KEY=k\nLLM_MODEL=m\n")
    monkeypatch.setattr(config, "ENV_FILE", f)
    assert callable(llm.make_llm())                       # would raise LLMError if the file were ignored
