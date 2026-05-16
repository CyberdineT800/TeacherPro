"""Shared SlowAPI rate-limiter singleton.

Defined here so any router can import and apply the same limiter instance
that is registered on app.state.limiter in main.py.

Usage in a router:
    from rate_limit import limiter

    @router.get("/some/path")
    @limiter.limit("60/minute")
    async def my_handler(request: Request, ...):
        ...
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
