import asyncio


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    """Uvicorn loop factory compatible with Psycopg on Windows and Unix."""
    return asyncio.SelectorEventLoop()
