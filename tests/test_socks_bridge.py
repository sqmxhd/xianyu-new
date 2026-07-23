import asyncio
import unittest

from apps.api.xianyu_admin_api.socks_bridge import SocksBridge


class SocksBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_chromium_facing_bridge_relays_through_upstream_socks(self) -> None:
        upstream_connections = 0

        async def fake_upstream(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ) -> None:
            nonlocal upstream_connections
            upstream_connections += 1
            try:
                version, method_count = await reader.readexactly(2)
                self.assertEqual(version, 5)
                await reader.readexactly(method_count)
                writer.write(b"\x05\x00")
                await writer.drain()
                version, command, _, address_type = await reader.readexactly(4)
                self.assertEqual((version, command), (5, 1))
                if address_type == 3:
                    length = (await reader.readexactly(1))[0]
                    await reader.readexactly(length)
                elif address_type == 1:
                    await reader.readexactly(4)
                else:
                    await reader.readexactly(16)
                await reader.readexactly(2)
                writer.write(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x01")
                await writer.drain()
                while payload := await reader.read(65536):
                    writer.write(payload)
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        upstream = await asyncio.start_server(fake_upstream, "127.0.0.1", 0)
        upstream_port = int(upstream.sockets[0].getsockname()[1])
        bridge = SocksBridge(f"socks5://127.0.0.1:{upstream_port}")
        await bridge.start()
        assert bridge.port is not None
        reader, writer = await asyncio.open_connection("127.0.0.1", bridge.port)
        try:
            writer.write(b"\x05\x01\x00")
            await writer.drain()
            self.assertEqual(await reader.readexactly(2), b"\x05\x00")
            host = b"target.invalid"
            writer.write(
                b"\x05\x01\x00\x03"
                + bytes((len(host),))
                + host
                + (443).to_bytes(2, "big")
            )
            await writer.drain()
            self.assertEqual((await reader.readexactly(10))[1], 0)
            writer.write(b"through-bound-proxy")
            await writer.drain()
            self.assertEqual(
                await reader.readexactly(len(b"through-bound-proxy")),
                b"through-bound-proxy",
            )
            self.assertEqual(upstream_connections, 1)
        finally:
            writer.close()
            await writer.wait_closed()
            await bridge.close()
            upstream.close()
            await upstream.wait_closed()


if __name__ == "__main__":
    unittest.main()
