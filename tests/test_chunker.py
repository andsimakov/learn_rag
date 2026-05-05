from ingestion.chunker import (
    _MAX_CHARS,
    Chunk,
    _split_with_overlap,
    chunk_document,
    extract_fetch_paths,
    substitute_code,
)


def test_chunk_document_preamble_only():
    content = "Some intro text without any headings."
    chunks = chunk_document("test.md", content)
    assert len(chunks) == 1
    assert chunks[0].heading is None
    assert chunks[0].content == content
    assert chunks[0].source_url == "test.md"
    assert chunks[0].chunk_index == 0


def test_chunk_document_multiple_headings():
    content = "# First\n\nFirst body.\n\n## Second\n\nSecond body.\n\n### Third\n\nThird body."
    chunks = chunk_document("test.md", content)
    assert len(chunks) == 3
    assert [c.heading for c in chunks] == ["First", "Second", "Third"]
    assert "First body" in chunks[0].content
    assert "Second body" in chunks[1].content
    assert "Third body" in chunks[2].content


def test_chunk_document_oversized_section():
    long_body = ("word " * 400).strip()  # ~2000 chars
    content = f"# Big Section\n\n{long_body}"
    chunks = chunk_document("test.md", content)
    assert len(chunks) > 1
    assert all(len(c.content) <= _MAX_CHARS for c in chunks)
    assert all(c.heading == "Big Section" for c in chunks)


def test_chunk_document_mdx_directive_replaced():
    content = "# Example\n\n{* ../../docs_src/path/to/file.py *}"
    chunks = chunk_document("test.md", content)
    assert len(chunks) == 1
    assert "<<<FETCH:docs_src/path/to/file.py>>>" in chunks[0].content
    assert "{*" not in chunks[0].content


def test_chunk_document_heading_anchor_stripped():
    content = "# Path Parameters { #path-parameters }\n\nSome content."
    chunks = chunk_document("test.md", content)
    assert chunks[0].heading == "Path Parameters"


def test_extract_fetch_paths_deduplication():
    chunks = [
        Chunk("a.md", 0, None, "<<<FETCH:docs_src/foo.py>>> and <<<FETCH:docs_src/bar.py>>>"),
        Chunk("a.md", 1, None, "<<<FETCH:docs_src/foo.py>>>"),
    ]
    paths = extract_fetch_paths(chunks)
    assert paths == ["docs_src/foo.py", "docs_src/bar.py"]


def test_substitute_code_replaces_marker():
    chunks = [Chunk("a.md", 0, None, "See example:\n\n<<<FETCH:docs_src/foo.py>>>")]
    result = substitute_code(chunks, {"docs_src/foo.py": "print('hello')"})
    assert len(result) == 1
    assert "```python" in result[0].content
    assert "print('hello')" in result[0].content


def test_substitute_code_drops_chunk_when_marker_missing_from_map():
    chunks = [Chunk("a.md", 0, None, "<<<FETCH:docs_src/missing.py>>>")]
    result = substitute_code(chunks, {})
    assert result == []


def test_split_with_overlap_cuts_at_newline():
    line = "word " * 60  # ~300 chars per line
    text = "\n".join([line] * 8)  # ~2400 chars total
    parts = _split_with_overlap(text)
    assert len(parts) > 1
    for part in parts[:-1]:
        assert part.endswith("\n"), f"Expected newline-terminated chunk, got: {repr(part[-10:])}"


def test_split_with_overlap_no_infinite_loop_when_newline_near_start():
    # Newline appears within _OVERLAP chars of start — without the max() guard
    # start could go backwards, causing an infinite loop or wrong output.
    line_a = "x" * 90 + "\n"  # newline at char 91 — inside _OVERLAP window
    line_b = "y" * 1600  # long line, no newline, pushes total > _MAX_CHARS
    text = line_a + line_b
    parts = _split_with_overlap(text)
    assert all(len(p) > 0 for p in parts)
    assert sum(len(p) for p in parts) >= len(text)  # overlap means sum >= original
