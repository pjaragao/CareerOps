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


def prompt_rule() -> str:
    """Added to the prompt of every skill that writes text to be sent."""
    topics = "; ".join(_rules()["topics"])
    return (f"\n\nCONFIDENTIALITY (absolute rule, overrides the candidate data above): the candidate is under an NDA. Never "
            f"mention these subjects, in any language or wording: {topics}. Where the data lists them, leave them out or "
            f'write "infrastructure" ("infraestrutura" in Portuguese) when the sentence needs a word there.\n')


def retry_rule(found: List[str]) -> str:
    return (f"\n\nYour previous answer contained forbidden expressions ({', '.join(found)}). Answer again without them "
            f"and without any other reference to those subjects.\n")


def ensure_clean(value: Any, what: str = "O texto") -> None:
    found = forbidden_in(value)
    if found:
        raise BlockedContent(f"{what} cita assunto protegido por NDA ({', '.join(found)}) e não foi usado")
