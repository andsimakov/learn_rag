import asyncio
from dataclasses import dataclass

import httpx

_REPO = "fastapi/fastapi"
_BRANCH = "master"
_DOCS_ROOT = "docs/en/docs/"
_RAW_BASE = f"https://raw.githubusercontent.com/{_REPO}/{_BRANCH}"
_TREE_URL = f"https://api.github.com/repos/{_REPO}/git/trees/{_BRANCH}"

# Only ingest reference-quality content. Excluded: release-notes (43% of
# chunks, changelog noise), community pages, management, benchmarks, etc.
_ALLOWED_PREFIXES = (
    "docs/en/docs/tutorial/",
    "docs/en/docs/advanced/",
    "docs/en/docs/how-to/",
    "docs/en/docs/reference/",
    "docs/en/docs/deployment/",
)
_ALLOWED_FILES = {
    "docs/en/docs/python-types.md",
    "docs/en/docs/async.md",
    "docs/en/docs/features.md",
}

# Keep concurrent downloads reasonable to avoid being rate-limited.
_SEMAPHORE = asyncio.Semaphore(10)


@dataclass
class DocFile:
    path: str  # e.g. "docs/en/docs/tutorial/first-steps.md"
    content: str  # raw markdown


async def _download(client: httpx.AsyncClient, path: str) -> DocFile:
    async with _SEMAPHORE:
        url = f"{_RAW_BASE}/{path}"
        response = await client.get(url)
        response.raise_for_status()
        return DocFile(path=path, content=response.text)


async def fetch_code_files(paths: list[str]) -> dict[str, str]:
    """Fetch a list of source files (e.g. docs_src/**/*.py) and return {path: content}."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        results = await asyncio.gather(
            *[_download(client, p) for p in paths],
            return_exceptions=True,
        )
    code_map: dict[str, str] = {}
    for path, result in zip(paths, results):
        if isinstance(result, Exception):
            print(f"  Warning: could not fetch {path}: {result}")
        else:
            code_map[result.path] = result.content
    return code_map


async def fetch_fastapi_docs() -> list[DocFile]:
    """
    1. Fetch the full repo tree from the GitHub API (1 API call).
    2. Download each .md file under docs/en/docs/ from raw.githubusercontent.com
       (no API rate limit applies to raw downloads).
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            _TREE_URL,
            params={"recursive": "1"},
            headers={"Accept": "application/vnd.github+json"},
        )
        response.raise_for_status()

        paths = [
            item["path"]
            for item in response.json()["tree"]
            if item["type"] == "blob"
            and item["path"].endswith(".md")
            and (any(item["path"].startswith(p) for p in _ALLOWED_PREFIXES) or item["path"] in _ALLOWED_FILES)
        ]

        print(f"Found {len(paths)} markdown files")

        results = await asyncio.gather(
            *[_download(client, path) for path in paths],
            return_exceptions=True,
        )

    docs: list[DocFile] = []
    for path, result in zip(paths, results):
        if isinstance(result, Exception):
            print(f"  Warning: could not fetch {path}: {result}")
        else:
            docs.append(result)
    return docs
