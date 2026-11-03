"""Shared pieces for routes that call a model and must keep working when it does not answer."""
import logging
from typing import Any

from app.app.ai_guard import metered

log = logging.getLogger("app.ai")


async def narrate_or_none(llm: Any, kind: str, computed: dict, labels: dict, *, pool: Any, org_id: str) -> list | None:
    """The model's draft sentences, or None when it is unavailable or its reply stays invalid after the re-ask. Every caller already has a code-only text for None.
    The provider's real usage is recorded either way."""
    try:
        async with metered(pool, org_id):
            return await llm.narrate(kind, computed, labels)
    except Exception as e:                                          # outage, breaker, refusal, bad output: the type only, never the text
        log.warning("%s narrative unavailable: %s", kind, type(e).__name__)
        return None
