# Stubs for names this module imports from the host application. Replace each with the host's real implementation.
# They only keep the imports resolvable; calling a function or building a class raises NotImplementedError.
from __future__ import annotations
from typing import *  # noqa: F401,F403


class Item:
    # host must provide this
    def __init__(self, *args, **kwargs):
        raise NotImplementedError('Item')


async def get_current_user(credentials: HTTPAuthorizationCredentials | None=...) -> dict:
    # host must provide this
    raise NotImplementedError('get_current_user')


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    # host must provide this
    raise NotImplementedError('get_db')

