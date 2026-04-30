import asyncio
from dataclasses import dataclass

import httpx

_REPO = "fastapi/fastapi"
_BRANCH = "master"
_DOCS_PREFIX = "docs/en/docs/"
_RAW_BASE = f"https://raw.githubusercontent.com/{_REPO}/{_BRANCH}"
_TREE_URL = f"https://api.github.com/repos/{_REPO}/git/trees/{_BRANCH}"

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
            if item["type"] == "blob" and item["path"].startswith(_DOCS_PREFIX) and item["path"].endswith(".md")
        ]

        print(f"Found {len(paths)} markdown files")

        tasks = [_download(client, path) for path in paths]
        docs = await asyncio.gather(*tasks)

    return list(docs)
