"""Theme token validation (WCAG contrast, font allow-list, no free CSS)."""
import re

FONTS = ("IBM Plex Sans / Plex Arabic", "Noto Sans / Noto Naskh", "Cairo", "System")
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
KEYS = {"primary", "bg", "fg", "font", "radius", "logo_object_ref", "favicon", "rtl_font"}


class ThemeError(ValueError):
    pass


def _lum(h: str) -> float:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def validate(t: dict) -> dict:
    if not isinstance(t, dict) or set(t) - KEYS:
        raise ThemeError(f"unknown theme keys {sorted(set(t) - KEYS) if isinstance(t, dict) else ''}")
    out = {}
    for k in ("primary", "bg", "fg"):
        if k in t:
            if not isinstance(t[k], str) or not HEX.match(t[k]):
                raise ThemeError(f"{k} must be #RRGGBB")
            out[k] = t[k].upper()
    if "font" in t or "rtl_font" in t:
        for k in ("font", "rtl_font"):
            if k in t:
                if t[k] not in FONTS:
                    raise ThemeError(f"{k} must be one of {FONTS}")
                out[k] = t[k]
    if "radius" in t:
        if isinstance(t["radius"], bool) or not isinstance(t["radius"], int) or not 0 <= t["radius"] <= 16:
            raise ThemeError("radius must be an integer 0-16")
        out["radius"] = t["radius"]
    for k in ("logo_object_ref", "favicon"):
        if k in t:
            if not isinstance(t[k], str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", t[k]) or ".." in t[k]:
                raise ThemeError(f"{k} must be an object reference")
            out[k] = t[k]
    bg = out.get("bg", "#FFFFFF")
    for k in ("primary", "fg"):
        if k in out and contrast(out[k], bg) < 4.5:
            raise ThemeError(f"{k} contrast against the background is {contrast(out[k], bg)}:1 (needs 4.5:1)")
    return out
