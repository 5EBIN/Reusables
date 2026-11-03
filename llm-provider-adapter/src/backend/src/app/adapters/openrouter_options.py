"""What is specific to OpenRouter in a chat request: the `provider` routing object and the app-attribution headers. Field names follow
https://openrouter.ai/docs/guides/routing/provider-selection and https://openrouter.ai/docs/api-reference/overview (checked when this was written):
provider.{order, allow_fallbacks, require_parameters, data_collection ("allow" | "deny"), zdr (boolean)}; headers HTTP-Referer and X-OpenRouter-Title.

Privacy routing is a switch, not a rule (docs/DATA_FLOWS.md): `data_collection` is sent exactly as configured, and `zdr` only when it is true."""
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from app.app.settings import AiSettings


def is_openrouter(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host == "openrouter.ai" or host.endswith(".openrouter.ai")


def provider_options(ai: "AiSettings") -> dict:
    """The `provider` object for every chat call. One function, one place (tests/unit/test_openrouter_options.py)."""
    p: dict = {"data_collection": ai.data_collection, "require_parameters": ai.require_parameters, "allow_fallbacks": ai.allow_fallbacks}
    if ai.zdr:
        p["zdr"] = True
    if ai.provider_order:
        p["order"] = list(ai.provider_order)
    return p


def attribution_headers(ai: "AiSettings") -> dict[str, str]:
    h = {"X-OpenRouter-Title": ai.app_title} if ai.app_title else {}
    if ai.app_url:
        h["HTTP-Referer"] = ai.app_url
    return h
