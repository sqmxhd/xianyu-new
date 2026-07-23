"""Loopback SOCKS5 bridge for Chromium and authenticated account proxies."""

from __future__ import annotations

import asyncio
import ipaddress
from contextlib import suppress

from python_socks.async_.asyncio import Proxy


class SocksBridge:
    """Accept unauthenticated local SOCKS5 and forward through one bound proxy."""

    def __init__(self, upstream_url: str) -> None:
        self._upstream_url = upstream_url
        self._server: asyncio.AbstractServer | None = None
        self.host = "127.0.0.1"
        self.port: int | None = None

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(self._handle_client, self.host, 0)
        socket = self._server.sockets[0]
        self.port = int(socket.getsockname()[1])

    async def close(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None
        self.port = None

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        remote_writer: asyncio.StreamWriter | None = None
        try:
            version, method_count = await reader.readexactly(2)
            if version != 5:
                return
            methods = await reader.readexactly(method_count)
            if 0 not in methods:
                writer.write(b"\x05\xff")
                await writer.drain()
                return
            writer.write(b"\x05\x00")
            await writer.drain()

            version, command, _, address_type = await reader.readexactly(4)
            if version != 5 or command != 1:
                await self._reply(writer, 7)
                return
            destination = await self._read_destination(reader, address_type)
            destination_port = int.from_bytes(await reader.readexactly(2), "big")
            try:
                remote_socket = await Proxy.from_url(self._upstream_url).connect(
                    destination, destination_port, timeout=20
                )
                remote_reader, remote_writer = await asyncio.open_connection(sock=remote_socket)
            except Exception:
                await self._reply(writer, 5)
                return

            await self._reply(writer, 0)
            await self._relay(reader, writer, remote_reader, remote_writer)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass
        finally:
            if remote_writer is not None:
                remote_writer.close()
                with suppress(Exception):
                    await remote_writer.wait_closed()
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

    @staticmethod
    async def _read_destination(reader: asyncio.StreamReader, address_type: int) -> str:
        if address_type == 1:
            return str(ipaddress.ip_address(await reader.readexactly(4)))
        if address_type == 3:
            length = int.from_bytes(await reader.readexactly(1), "big")
            return (await reader.readexactly(length)).decode("idna")
        if address_type == 4:
            return str(ipaddress.ip_address(await reader.readexactly(16)))
        raise ConnectionError("unsupported SOCKS5 address type")

    @staticmethod
    async def _reply(writer: asyncio.StreamWriter, status: int) -> None:
        writer.write(bytes((5, status, 0, 1, 0, 0, 0, 0, 0, 0)))
        await writer.drain()

    @staticmethod
    async def _relay(
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        remote_reader: asyncio.StreamReader,
        remote_writer: asyncio.StreamWriter,
    ) -> None:
        async def copy(source: asyncio.StreamReader, target: asyncio.StreamWriter) -> None:
            while data := await source.read(64 * 1024):
                target.write(data)
                await target.drain()

        tasks = {
            asyncio.create_task(copy(client_reader, remote_writer)),
            asyncio.create_task(copy(remote_reader, client_writer)),
        }
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*done, *pending, return_exceptions=True)
