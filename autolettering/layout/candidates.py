from __future__ import annotations


def generate_line_break_candidates(text: str, max_lines: int = 3) -> list[str]:
    compact = "".join(text.split())
    if not compact:
        return [""]

    candidates: list[str] = [compact]
    for lines in range(2, max_lines + 1):
        chunks = _balanced_chunks(compact, lines)
        candidate = "\n".join(chunks)
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _balanced_chunks(text: str, lines: int) -> list[str]:
    length = len(text)
    base = length // lines
    extra = length % lines
    chunks: list[str] = []
    offset = 0
    for index in range(lines):
        size = base + int(index < extra)
        if size <= 0:
            continue
        chunks.append(text[offset : offset + size])
        offset += size
    return chunks
