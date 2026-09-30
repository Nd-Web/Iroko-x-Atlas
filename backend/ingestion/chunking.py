"""Exact substring chunks with bounded tokens and real source offsets."""

import hashlib
import re
from functools import lru_cache

import tiktoken


@lru_cache(maxsize=1)
def encoding():
    return tiktoken.get_encoding("cl100k_base")


def chunk_pages(pages, target=600, maximum=1000, overlap=60):
    _encoding = encoding()
    if not 0 <= overlap < target <= maximum:
        raise ValueError("Require 0 <= overlap < target <= maximum")
    texts, spans, cursor = [], [], 0
    for item in pages:
        text = item["text"]
        spans.append((cursor, cursor + len(text), item))
        texts.append(text)
        cursor += len(text) + 2
    full = "\n\n".join(texts)
    headings = [
        (m.start(), m.group().strip())
        for m in re.finditer(
            r"(?m)^(?:#{1,6} .+|[A-Z][A-Z /&0-9-]{5,100}|\d+\. [A-Z][^\n]{2,100})$", full
        )
    ]
    chunks, start = [], 0
    while start < len(full):
        # Binary search a character boundary; never decode a partial Unicode token.
        low, high = start + 1, min(len(full), start + maximum * 8)
        end = low
        while low <= high:
            middle = (low + high) // 2
            if len(_encoding.encode(full[start:middle])) <= target:
                end, low = middle, middle + 1
            else:
                high = middle - 1
        if end < len(full):
            boundary = full.rfind("\n", start + (end - start) // 2, end)
            if boundary > start:
                end = boundary + 1
        content = full[start:end]
        if content.strip():
            locations = [item for a, b, item in spans if a < end and b > start]
            numbers = [p["page_number"] for p in locations if p["page_number"] is not None]
            heading = next((h for pos, h in reversed(headings) if pos <= start), None)
            chunks.append(
                {
                    "content": content,
                    "chunk_index": len(chunks),
                    "char_start": start,
                    "char_end": end,
                    "page_start": min(numbers) if numbers else None,
                    "page_end": max(numbers) if numbers else None,
                    "locators": list(
                        dict.fromkeys(p["locator"] for p in locations if p["locator"])
                    ),
                    "section_heading": heading,
                    "token_count": len(_encoding.encode(content)),
                    "text_sha256": hashlib.sha256(content.encode()).hexdigest(),
                }
            )
        if end >= len(full):
            break
        # Small bounded overlap, while always making forward progress.
        next_start = end
        low, high = start + 1, end
        while low <= high:
            middle = (low + high) // 2
            if len(_encoding.encode(full[middle:end])) <= overlap:
                next_start, high = middle, middle - 1
            else:
                low = middle + 1
        start = max(start + 1, next_start)
    return chunks
