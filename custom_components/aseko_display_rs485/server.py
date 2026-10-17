"""TCP server that receives Waveshare-forwarded RS485 frames."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable

from .const import MAX_CLIENTS, MAX_READ_TIMEOUTS, READ_TIMEOUT
from .protocol import AsekoDisplayFrame, FrameAssembler, decode_frame

_LOGGER = logging.getLogger(__name__)

OnFrame = Callable[[AsekoDisplayFrame], Awaitable[None] | None]
OnDisconnect = Callable[[], Awaitable[None] | None]


class AsekoDisplayServer:
    """Listen for TCP clients and decode display frames."""

    def __init__(
        self,
        host: str,
        port: int,
        on_frame: OnFrame,
        *,
        on_disconnect: OnDisconnect | None = None,
        allowed_host: str | None = None,
        max_clients: int = MAX_CLIENTS,
    ) -> None:
        self.host = host
        self.port = port
        self.on_frame = on_frame
        self.on_disconnect = on_disconnect
        self.allowed_host = allowed_host or None
        self.max_clients = max_clients
        self._server: asyncio.AbstractServer | None = None
        self._client_tasks: set[asyncio.Task[None]] = set()
        self._client_writers: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        sockets = self._server.sockets or []
        bound = ", ".join(str(s.getsockname()) for s in sockets)
        _LOGGER.info("Aseko Display RS485 listening on %s", bound)

    async def stop(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()

        for writer in tuple(self._client_writers):
            writer.close()

        current = asyncio.current_task()
        tasks = [
            task
            for task in tuple(self._client_tasks)
            if task is not current and not task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if server is not None:
            await server.wait_closed()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        peer_host = peer[0] if isinstance(peer, tuple) and peer else str(peer)
        if self.allowed_host is not None and peer_host != self.allowed_host:
            _LOGGER.warning(
                "Rejecting client %s; expected %s", peer, self.allowed_host
            )
            await self._close_writer(writer)
            return
        if len(self._client_writers) >= self.max_clients:
            _LOGGER.warning(
                "Rejecting extra client %s; limit is %d", peer, self.max_clients
            )
            await self._close_writer(writer)
            return

        task = asyncio.current_task()
        if task is not None:
            self._client_tasks.add(task)
        self._client_writers.add(writer)
        _LOGGER.info("Client connected: %s", peer)
        assembler = FrameAssembler()
        read_timeouts = 0
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        reader.read(1024), timeout=READ_TIMEOUT
                    )
                except TimeoutError:
                    read_timeouts += 1
                    if read_timeouts >= MAX_READ_TIMEOUTS:
                        _LOGGER.warning(
                            "Disconnecting idle client %s after %d read timeouts",
                            peer,
                            read_timeouts,
                        )
                        break
                    _LOGGER.debug(
                        "Read timeout %d/%d from %s",
                        read_timeouts,
                        MAX_READ_TIMEOUTS,
                        peer,
                    )
                    continue
                if not chunk:
                    break
                bad_crc_before = assembler.bad_crc_count
                raw_frames = assembler.feed(chunk)
                if assembler.bad_crc_count > bad_crc_before:
                    _LOGGER.warning(
                        "Discarded %d CRC-invalid candidate(s) from %s",
                        assembler.bad_crc_count - bad_crc_before,
                        peer,
                    )
                received_frame = False
                for raw in raw_frames:
                    try:
                        frame = decode_frame(raw)
                    except ValueError as err:
                        _LOGGER.warning(
                            "Dropping frame from %s: %s (%s)",
                            peer,
                            err,
                            raw.hex(),
                        )
                        continue
                    _LOGGER.debug(
                        "Frame SN=%s pH=%s temp=%s",
                        frame.serial_hex,
                        frame.ph,
                        frame.temperature,
                    )
                    result = self.on_frame(frame)
                    if inspect.isawaitable(result):
                        await result
                    received_frame = True
                if received_frame:
                    read_timeouts = 0
        except asyncio.CancelledError:
            raise
        except ConnectionResetError:
            _LOGGER.info("Client reset: %s", peer)
        except Exception:
            _LOGGER.exception("Client handler failed for %s", peer)
        finally:
            try:
                await self._close_writer(writer)
                if self.on_disconnect is not None:
                    result = self.on_disconnect()
                    if inspect.isawaitable(result):
                        await result
            except Exception:
                _LOGGER.exception("Disconnect callback failed for %s", peer)
            finally:
                self._client_writers.discard(writer)
                if task is not None:
                    self._client_tasks.discard(task)
            _LOGGER.info("Client disconnected: %s", peer)

    @staticmethod
    async def _close_writer(writer: asyncio.StreamWriter) -> None:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
