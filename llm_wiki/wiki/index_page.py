from __future__ import annotations

from pathlib import Path


def rebuild_index_page(index_path: Path, sources_dir: Path, vault_root: Path) -> None:
    links = []
    for summary_file in sorted(sources_dir.glob("*.md"), key=lambda p: p.name.lower()):
        rel = summary_file.relative_to(vault_root).as_posix()
        links.append(f"- [[{summary_file.stem}]] (`{rel}`)")
    body = "# LLM Wiki Index\n\n## Source Summaries\n\n"
    body += "\n".join(links) + ("\n" if links else "")
    index_path.write_text(body, encoding="utf-8")
