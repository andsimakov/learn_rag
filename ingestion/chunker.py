import re
from dataclasses import dataclass


@dataclass
class Chunk:
    source_url: str
    chunk_index: int
    heading: str | None
    content: str


_HEADING_RE = re.compile(r"^(#{1,3} .+)$", re.MULTILINE)
# FastAPI docs use {* path/to/file.py hl[n] *} to include code examples.
_MDX_INCLUDE_RE = re.compile(r"\{\*[^*]*\*\}")
# Headings carry HTML anchors: "Path Parameters { #path-parameters }"
_HEADING_ANCHOR_RE = re.compile(r"\s*\{[^}]+\}\s*$")
# Collapse runs of blank lines left behind after stripping directives.
_BLANK_LINES_RE = re.compile(r"\n{3,}")

# Chunks larger than this get split further.
_MAX_CHARS = 800
# Overlap carried over between split sub-chunks to preserve boundary context.
_OVERLAP = 100


def _clean(text: str) -> str:
    text = _MDX_INCLUDE_RE.sub("", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _clean_heading(heading: str) -> str:
    return _HEADING_ANCHOR_RE.sub("", heading).strip()


def chunk_document(source_path: str, content: str) -> list[Chunk]:
    """Split a markdown file into section-aware chunks.

    Splits on # / ## / ### headings, then sub-splits oversized sections with
    a character-level sliding window so no chunk exceeds _MAX_CHARS.
    """
    parts = _HEADING_RE.split(content)

    # re.split with a capturing group alternates: [pre, heading, body, heading, body, ...]
    sections: list[tuple[str | None, str]] = []

    if parts and parts[0].strip():
        sections.append((None, _clean(parts[0])))

    i = 1
    while i < len(parts) - 1:
        heading = _clean_heading(parts[i].lstrip("#").strip())
        body = _clean(parts[i + 1])
        if body:
            sections.append((heading, body))
        i += 2

    chunks: list[Chunk] = []
    chunk_index = 0

    for heading, body in sections:
        if len(body) <= _MAX_CHARS:
            chunks.append(
                Chunk(
                    source_url=source_path,
                    chunk_index=chunk_index,
                    heading=heading,
                    content=body,
                )
            )
            chunk_index += 1
        else:
            for sub in _split_with_overlap(body):
                chunks.append(
                    Chunk(
                        source_url=source_path,
                        chunk_index=chunk_index,
                        heading=heading,
                        content=sub,
                    )
                )
                chunk_index += 1

    return chunks


def _split_with_overlap(text: str) -> list[str]:
    """Slide a window of _MAX_CHARS over text with _OVERLAP carry-over."""
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = start + _MAX_CHARS
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = end - _OVERLAP
    return parts
