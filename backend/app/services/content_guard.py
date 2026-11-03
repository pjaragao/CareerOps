"""What never goes out (config/automation.yml → content_guard): checked on every text written to be sent. The file is
required: without it the guard refuses instead of letting everything through."""
import re
from functools import lru_cache
from typing import Any, List

import yaml

from app.core.config import settings


class BlockedContent(RuntimeError):
    """A text kept a forbidden subject. RuntimeError: the routes already turn it into an error the user reads."""


@lru_cache(maxsize=1)
def _rules() -> dict:
    path = settings.CONFIG_DIR / "automation.yml"
    if not path.exists():
        raise BlockedContent(f"{path} não encontrado: sem as regras de conteúdo, nenhum texto é gerado para envio")
    guard = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("content_guard") or {}
    return {"topics": guard.get("topics") or [], "patterns": [re.compile(p, re.I) for p in guard.get("patterns") or []]}


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)


def forbidden_in(value: Any) -> List[str]:
    """The forbidden expressions found in a text or anywhere inside a skill's JSON answer."""
    found = []
    for text in _strings(value):
        for pattern in _rules()["patterns"]:
            found += [m.group(0) for m in pattern.finditer(text)]
    return list(dict.fromkeys(found))


def prompt_rule(prompt: str = "") -> str:
    """Added to the prompt of every skill that writes text to be sent. The subjects are named only when the prompt itself
    brings them (a job ad about them): naming them to a model that had no reason to write them made it write them."""
    if not forbidden_in(prompt):
        return ("\n\nCONFIDENTIALITY: the candidate is under an NDA about part of past work. Describe the experience only as the "
                "candidate data above does; never add a sector, client type or subject that it does not state.\n")
    topics = "; ".join(_rules()["topics"])
    return (f"\n\nCONFIDENTIALITY (absolute rule, overrides the candidate data above): the candidate is under an NDA. Never "
            f"mention these subjects, in any language or wording: {topics}. Where the data lists them, leave them out or "
            f'write "infrastructure" ("infraestrutura" in Portuguese) when the sentence needs a word there.\n')


def retry_rule(found: List[str]) -> str:
    return (f"\n\nYour previous answer contained forbidden expressions ({', '.join(found)}). Answer again without them "
            f"and without any other reference to those subjects.\n")


SENTENCE = re.compile(r"(?<=[.!?;])\s+")
MAX_SCRUB = 0.2


def scrub(value: Any) -> Any:
    """The last resort, after the AI was told twice: each sentence (or bullet) citing the subject is dropped. A text that
    would lose more than a fifth of itself is not rescued this way: it is refused (ensure_clean)."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if not isinstance(value, str) or not forbidden_in(value):
        return value
    lines = []
    for line in value.split("\n"):
        if forbidden_in(line):
            line = " ".join(p for p in SENTENCE.split(line) if not forbidden_in(p))
            if not line.strip(" -*•#"):
                continue
        lines.append(line)
    out = "\n".join(lines)
    return out if len(out) >= len(value) * (1 - MAX_SCRUB) else value


def ensure_clean(value: Any, what: str = "O texto") -> None:
    found = forbidden_in(value)
    if found:
        raise BlockedContent(f"{what} cita assunto protegido por NDA ({', '.join(found)}) e não foi usado")
