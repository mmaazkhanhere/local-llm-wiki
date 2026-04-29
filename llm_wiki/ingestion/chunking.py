from __future__ import annotations


def chunk_text(text: str, target_words: int = 180) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    for start in range(0, len(words), target_words):
        block = words[start : start + target_words]
        chunks.append(" ".join(block))
    return chunks
