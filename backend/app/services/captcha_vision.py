"""CAPTCHA image questions (2026-11-19): the worker's solver sends a numbered grid and "which cells hold X?"; this asks
Lolo's vision model (the free Nous model) through the host shim, model "hermes-vision", and returns the cell numbers."""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import List

log = logging.getLogger(__name__)

RULES = ("You solve image-selection puzzles. Look at the picture and answer ONLY with a JSON list of the numbers of the "
         "matching cells, e.g. [2, 5, 9]. Answer [] when no cell matches. No other text.")


def parse_cells(text: str, n: int) -> List[int]:
    m = re.search(r"\[([^\]]*)\]", text or "")
    part = m.group(1) if m else (text or "")
    out: List[int] = []
    for tok in re.findall(r"\d+", part):
        i = int(tok)
        if 1 <= i <= n and i not in out:
            out.append(i)
    return out


def ask_cells(image_b64: str, instruction: str, cells: int) -> dict:
    url = os.getenv("CLAUDE_SHIM_URL", "http://172.26.0.1:8788/v1")
    if not url or url.lower() == "off":
        return {"error": "shim off"}
    body = {"model": "hermes-vision", "messages": [
        {"role": "system", "content": RULES},
        {"role": "user", "content": [{"type": "text", "text": instruction},
                                     {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}]}]}
    token = os.getenv("CLAUDE_SHIM_TOKEN") or os.getenv("AGY_SHIM_TOKEN") or ""
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            data = json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.warning("captcha vision failed: %s", e)
        return {"error": str(e)[:200]}
    text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
    return {"cells": parse_cells(text, cells), "raw": text[:200]}
