"""The worker only talks to the backend: the rules, the limits and the state of each action live there."""
import os
from typing import Optional

import httpx


class Api:
    def __init__(self, base: Optional[str] = None, token: Optional[str] = None):
        self.base = (base or os.environ["CAREEROPS_API_BASE"]).rstrip("/")
        self.token = token or os.environ.get("CAREEROPS_WORKER_TOKEN", "")
        self.client = httpx.AsyncClient(timeout=30, headers={"X-CareerOps-Token": self.token})

    async def call(self, method: str, path: str, **kwargs) -> Optional[dict]:
        res = await self.client.request(method, self.base + path, **kwargs)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    async def post(self, path: str, body: Optional[dict] = None) -> Optional[dict]:
        return await self.call("POST", path, json=body or {})

    async def get(self, path: str) -> Optional[dict]:
        return await self.call("GET", path)

    async def download(self, path: str) -> Optional[tuple]:
        """(file name, bytes) of a document, or None when it does not exist."""
        try:
            res = await self.client.get(self.base + path)
        except httpx.HTTPError:   # the PDF service is down, say: the extension reports it if the form really needs the file
            return None
        if res.status_code != 200:
            return None
        disposition = res.headers.get("content-disposition", "")
        name = disposition.split('filename="')[-1].rstrip('"') if 'filename="' in disposition else "document.pdf"
        return name, res.content

    async def close(self) -> None:
        await self.client.aclose()
