from pathlib import Path

from llm_wiki.core.errors import TransientError
from llm_wiki.core.repair import append_repair_event, list_open_repairs, run_repair
from llm_wiki.core.retries import RetryPolicy, with_retry
from llm_wiki.core.secrets import load_groq_api_key, save_groq_api_key
from llm_wiki.core.vault import initialize_vault


def test_with_retry_retries_transient_then_succeeds() -> None:
    attempts = {"count": 0}

    def op() -> int:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TransientError("retry me")
        return 7

    value = with_retry(op, RetryPolicy(max_attempts=3, base_delays_seconds=(0.0, 0.0), jitter_seconds=0.0))
    assert value == 7
    assert attempts["count"] == 3


def test_secrets_fallback_roundtrip(tmp_path: Path) -> None:
    metadata_dir = tmp_path / ".llm-wiki"
    save_groq_api_key(metadata_dir, "abc123")
    loaded = load_groq_api_key(metadata_dir)
    assert loaded == "abc123"


def test_repair_event_tracking_and_run(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    # seed a summary file so rebuild has input
    summary = layout.sources_dir / "Sample summary.md"
    summary.write_text("# Sample Summary\n", encoding="utf-8")
    append_repair_event(
        vault_root=tmp_path,
        event_type="post_write_inconsistency",
        source_relative_path="raw.md",
        generated_relative_path="LLM Wiki/Sources/Sample summary.md",
        detail="audit append failed",
    )
    open_repairs = list_open_repairs(tmp_path)
    assert len(open_repairs) == 1
    count = run_repair(tmp_path)
    assert count == 1
    assert "Source Summaries" in layout.index_file.read_text(encoding="utf-8")
