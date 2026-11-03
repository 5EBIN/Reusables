# Stubs for names this module imports from the host application. Replace each with the host's real implementation.
# They only keep the imports resolvable; calling a function or building a class raises NotImplementedError.
from __future__ import annotations
from typing import *  # noqa: F401,F403


class ApprovalRequest:
    # host must provide this
    def __init__(self, *args, **kwargs):
        raise NotImplementedError('ApprovalRequest')


AsyncSessionLocal: object = None   # host must provide this

