"""Deterministic all-synthetic PNG with no personal or customer information."""
import hashlib
import struct
import zlib

WIDTH = 512
HEIGHT = 384


def _chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xffffffff)


def png_fixture() -> bytes:
    pixels = bytearray()
    for y in range(HEIGHT):
        pixels.append(0)  # PNG scanline with no filter.
        for x in range(WIDTH):
            if 48 <= x < WIDTH - 48 and 48 <= y < HEIGHT - 48:
                value = 220 if ((x // 32 + y // 32) % 2) else 40
                pixels.extend((value, value, 255))
            else:
                pixels.extend((255, 255, 255))
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) +
            _chunk(b"IDAT", zlib.compress(pixels, 9)) +
            _chunk(b"IEND", b""))


def fixture_sha256() -> str:
    return hashlib.sha256(png_fixture()).hexdigest()
