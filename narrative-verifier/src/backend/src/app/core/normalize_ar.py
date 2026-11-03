import re

_STRIP = re.compile("[ً-ْـ]")
_MAP = str.maketrans("أإآٱىةی", "اااايهي")
_WS = re.compile(r"\s+")


def ar_norm(text: str) -> str:
    return _WS.sub(" ", _STRIP.sub("", text).translate(_MAP))
