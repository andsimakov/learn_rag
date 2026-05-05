from app.core.retriever import _fts_query


def test_fts_query_strips_stopwords():
    assert _fts_query("How do I declare path parameters?") == "declare & path & parameters"


def test_fts_query_only_stopwords_returns_none():
    assert _fts_query("how what where can does") is None


def test_fts_query_empty_string_returns_none():
    assert _fts_query("") is None


def test_fts_query_filters_short_terms():
    # all terms are ≤2 chars after stripping
    assert _fts_query("to an at it") is None


def test_fts_query_fastapi_is_stopword():
    assert _fts_query("fastapi") is None


def test_fts_query_strips_special_characters():
    assert _fts_query("middleware! exceptions?") == "middleware & exceptions"
