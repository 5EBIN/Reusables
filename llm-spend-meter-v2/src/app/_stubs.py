# Stubs for names this module imports from the host application. Replace each with the host's real implementation.
# They only keep the imports resolvable; calling a function or building a class raises NotImplementedError.
from __future__ import annotations
from typing import *  # noqa: F401,F403


def get_settings() -> Settings:
    # host must provide this
    raise NotImplementedError('get_settings')

