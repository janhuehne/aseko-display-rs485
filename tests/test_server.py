"""Lifecycle tests for the TCP listener."""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path

COMPONENT_DIR = (
    Path(__file__).parents[1] / "custom_components" / "aseko_display_rs485"
)
PACKAGE_NAME = "_aseko_display_rs485_server_tests"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(COMPONENT_DIR)]
sys.modules[PACKAGE_NAME] = package
server_module = importlib.import_module(f"{PACKAGE_NAME}.server")

LIVE_SAMPLE = bytes.fromhex(
    "0a2102c7000c000c00ba0006906b2053470a190a3200ff000000e3"
)


def test_stop_closes_active_client_and_handler() -> None:
    async def run_test() -> None:
        frames = []
        disconnected = asyncio.Event()
        server = server_module.AsekoDisplayServer(
            "127.0.0.1",
            0,
            frames.append,
            on_disconnect=disconnected.set,
            allowed_host="127.0.0.1",
        )
        await server.start()
        assert server._server is not None
        port = server._server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)

        writer.write(LIVE_SAMPLE)
        await writer.drain()
        for _ in range(100):
            if frames:
                break
            await asyncio.sleep(0.01)

        assert len(frames) == 1
        await asyncio.wait_for(server.stop(), 2)
        await asyncio.wait_for(disconnected.wait(), 1)
        assert await asyncio.wait_for(reader.read(), 1) == b""
        writer.close()
        await writer.wait_closed()

    asyncio.run(run_test())
