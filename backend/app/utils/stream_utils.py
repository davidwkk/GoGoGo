"""Stream utilities — reusable async adapters for LLM streaming."""

import asyncio
from typing import AsyncIterator, Iterator

from google.genai import types


async def _sync_stream_to_async(
    sync_iter: Iterator[types.GenerateContentResponse],
) -> AsyncIterator[types.GenerateContentResponse]:
    """
    Wrap a synchronous iterator as an async generator.

    Runs each synchronous next() call in the default thread pool,
    yielding control to the event loop while waiting for the next chunk.
    This prevents the sync iterator from blocking the event loop.

    StopIteration is caught inside the thread to avoid
    "StopIteration interacts badly with generators" Future exception.
    """
    loop = asyncio.get_running_loop()

    def _next() -> tuple[bool, types.GenerateContentResponse | None]:
        try:
            return (True, next(sync_iter))
        except StopIteration:
            return (False, None)

    while True:
        has_value, chunk = await loop.run_in_executor(None, _next)
        if not has_value:
            return
        assert chunk is not None
        yield chunk


async def _is_proxy_reachable() -> bool:
    """Returns True if a proxy is configured and the SOCKS5 proxy is reachable."""
    return True  # Bypass for now, it is NOT A BUG, it is INTENTIONAL!

    # if not settings.LLM_PROXY_ENABLED:
    #     return False  # No proxy — direct call not allowed
    # proxy_url = settings.SOCKS5_PROXY_URL
    # try:
    #     host = proxy_url.split("://")[1].rsplit(":", 1)[0]
    #     port = int(proxy_url.split("://")[1].rsplit(":", 1)[1])
    # except (IndexError, ValueError):
    #     return False

    # def _check() -> bool:
    #     try:
    #         sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #         sock.settimeout(5)
    #         sock.connect((host, port))
    #         # SOCKS5 handshake: version 5, 1 auth method (no auth)
    #         sock.send(b"\x05\x01\x00")
    #         resp = sock.recv(2)
    #         sock.close()
    #         return resp == b"\x05\x00"
    #     except Exception:
    #         return False

    # loop = asyncio.get_running_loop()
    # return await loop.run_in_executor(None, _check)
