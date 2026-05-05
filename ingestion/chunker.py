import re
from dataclasses import dataclass


@dataclass
class Chunk:
    source_url: str
    chunk_index: int
    heading: str | None
    content: str


_HEADING_RE = re.compile(r"^(#{1,3} .+)$", re.MULTILINE)
# FastAPI docs use {* path/to/file.py [hl[n]] *} to include code examples.
# We replace them with fetch markers; pipeline substitutes actual code before embedding.
_MDX_INCLUDE_RE = re.compile(r"\{\*\s*([^\s*}]+)[^*]*\*\}")
_FETCH_MARKER_RE = re.compile(r"<<<FETCH:([^>]+)>>>")
# Headings carry HTML anchors: "Path Parameters { #path-parameters }"
_HEADING_ANCHOR_RE = re.compile(r"\s*\{[^}]+\}\s*$")
# Collapse runs of blank lines left behind after stripping directives.
_BLANK_LINES_RE = re.compile(r"\n{3,}")

# Larger limit than before to keep prose + one code example in a single chunk.
_MAX_CHARS = 1500
# Overlap carried over between split sub-chunks to preserve boundary context.
_OVERLAP = 100


def _clean(text: str) -> str:
    def _make_marker(m: re.Match) -> str:
        path = re.sub(r"^(\.\./)+", "", m.group(1))
        return f"<<<FETCH:{path}>>>"

    text = _MDX_INCLUDE_RE.sub(_make_marker, text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _clean_heading(heading: str) -> str:
    return _HEADING_ANCHOR_RE.sub("", heading).strip()


def chunk_document(source_path: str, content: str) -> list[Chunk]:
    """Split a markdown file into section-aware chunks.

    Splits on # / ## / ### headings, then sub-splits oversized sections with
    a character-level sliding window so no chunk exceeds _MAX_CHARS.
    MDX include directives are replaced with <<<FETCH:path>>> markers;
    call substitute_code() after fetching the referenced files.
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


def extract_fetch_paths(chunks: list[Chunk]) -> list[str]:
    """Return unique file paths referenced by <<<FETCH:...>>> markers."""
    seen: set[str] = set()
    paths: list[str] = []
    for chunk in chunks:
        for m in _FETCH_MARKER_RE.finditer(chunk.content):
            path = m.group(1)
            if path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def substitute_code(chunks: list[Chunk], code_map: dict[str, str]) -> list[Chunk]:
    """Replace <<<FETCH:path>>> markers with fenced Python code blocks."""
    result = []
    for chunk in chunks:
        content = _FETCH_MARKER_RE.sub(
            lambda m: f"```python\n{code_map[m.group(1)].strip()}\n```" if m.group(1) in code_map else "",
            chunk.content,
        )
        content = _BLANK_LINES_RE.sub("\n\n", content).strip()
        if content:
            result.append(
                Chunk(
                    source_url=chunk.source_url,
                    chunk_index=chunk.chunk_index,
                    heading=chunk.heading,
                    content=content,
                )
            )
    return result


def _split_with_overlap(text: str) -> list[str]:
    """Slide a window of _MAX_CHARS over text with _OVERLAP carry-over.

    Cuts at the nearest preceding newline to avoid breaking mid-word.
    Falls back to a hard cut only when the window contains no newline.
    """
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = start + _MAX_CHARS
        if end < len(text):
            nl = text.rfind("\n", start, end)
            if nl > start:
                end = nl + 1
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - _OVERLAP, start + 1)  # guarantee forward progress
    return parts
