# Chunk utilities cho Smart Context - shared functions
# Filter va merge chunks, dung chung cho tat ca strategies

from typing import Optional
from collections import defaultdict


def filter_duplicated_chunks(chunks: list[dict]) -> list[dict]:
    """
    Giu chunk dai nhat moi start row.
    Ported from Repomix's filterDuplicatedChunks().

    Args:
        chunks: List of {content, start_row, end_row}

    Returns:
        Filtered list keeping longest chunk per row
    """
    by_start_row: dict[int, list[dict]] = defaultdict(list)
    for chunk in chunks:
        by_start_row[chunk["start_row"]].append(chunk)

    filtered: list[dict] = []
    for start_row in sorted(by_start_row.keys()):
        row_chunks = by_start_row[start_row]
        # Giu chunk co content dai nhat
        row_chunks.sort(key=lambda c: len(c["content"]), reverse=True)
        filtered.append(row_chunks[0])

    return filtered


def merge_adjacent_chunks(chunks: list[dict]) -> list[dict]:
    """
    Merge chunks tren cac dong lien ke.
    Ported from Repomix's mergeAdjacentChunks().

    Args:
        chunks: List of {content, start_row, end_row}

    Returns:
        Merged list where adjacent chunks are combined
    """
    if len(chunks) <= 1:
        return chunks

    merged: list[dict] = [chunks[0].copy()]

    for i in range(1, len(chunks)):
        current = chunks[i]
        previous = merged[-1]

        # Merge neu adjacent (previous end + 1 == current start)
        if previous["end_row"] + 1 == current["start_row"]:
            previous["content"] += "\n" + current["content"]
            previous["end_row"] = current["end_row"]
        else:
            merged.append(current.copy())

    return merged


def check_and_add(content: str, processed: set[str]) -> Optional[str]:
    """
    Kiem tra content da duoc xu ly chua, them neu chua.

    Args:
        content: Content de kiem tra
        processed: Set cac content da xu ly

    Returns:
        Content neu chua duoc xu ly, None neu da co
    """
    normalized = content.strip()
    if normalized in processed:
        return None
    processed.add(normalized)
    return normalized
