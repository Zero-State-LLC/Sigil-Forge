"""PNG LSB steganography (optional channel).

Pure-Python 8-bit RGB PNG read/write + sequential LSB embed/extract.
No external image libraries required.

Payload format (v1):
  magic ``SF1\\0`` (4 bytes)
  + digest raw 32 bytes
  + optional sealed blob: uint32 BE length + ciphertext bytes

Capacity: each RGB sample carries 1 payload bit (MSB-first within each
payload byte). Image must provide at least ``len(payload) * 8`` samples.
"""

from __future__ import annotations

import struct
import zlib
from typing import Optional

PNG_SIG = b"\x89PNG\r\n\x1a\n"
MAGIC = b"SF1\x00"
DIGEST_LEN = 32


def pack_payload(digest: bytes, sealed: Optional[bytes] = None) -> bytes:
    """Build SF1 payload: magic + 32-byte digest [+ len-prefixed sealed]."""
    if len(digest) != DIGEST_LEN:
        raise ValueError(f"digest must be {DIGEST_LEN} bytes, got {len(digest)}")
    out = MAGIC + digest
    if sealed is not None:
        if len(sealed) > 0xFFFFFFFF:
            raise ValueError("sealed blob too large")
        out += struct.pack(">I", len(sealed)) + sealed
    return out


def unpack_payload(payload: bytes) -> tuple[bytes, Optional[bytes]]:
    """Parse SF1 payload → (digest, sealed_or_None)."""
    if len(payload) < 4 + DIGEST_LEN:
        raise ValueError("payload too short")
    if payload[:4] != MAGIC:
        raise ValueError("bad payload magic")
    digest = payload[4 : 4 + DIGEST_LEN]
    rest = payload[4 + DIGEST_LEN :]
    if not rest:
        return digest, None
    if len(rest) < 4:
        raise ValueError("truncated sealed length")
    (n,) = struct.unpack(">I", rest[:4])
    blob = rest[4:]
    if len(blob) < n:
        raise ValueError("truncated sealed blob")
    return digest, blob[:n]


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag)
    crc = zlib.crc32(data, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def write_rgb_png(width: int, height: int, rgb: bytes) -> bytes:
    """Write a minimal 8-bit RGB (color type 2) PNG.

    ``rgb`` is contiguous RGBRGB... length ``width * height * 3``.
    Filter type 0 (None) per scanline. No ancillary chunks.
    """
    if width < 1 or height < 1:
        raise ValueError("width and height must be >= 1")
    expected = width * height * 3
    if len(rgb) != expected:
        raise ValueError(f"rgb length {len(rgb)} != {expected}")

    stride = width * 3
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter None
        rows.extend(rgb[y * stride : (y + 1) * stride])

    compressed = zlib.compress(bytes(rows), 9)
    # IHDR: width, height, bit_depth=8, color_type=2 (RGB),
    # compression=0, filter=0, interlace=0
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return PNG_SIG + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", compressed) + _chunk(b"IEND", b"")


# Largest image read_rgb_png will decode: 100 megapixels, three times an 8K
# frame. The header is untrusted and this pure-Python reader holds every pixel.
# 8K UHD is 33 megapixels and the largest wallpaper profile is 5. At the old
# limit of 100 a 300 KB crafted file made the reader allocate over a gigabyte.
MAX_PNG_PIXELS = 40_000_000


def inflate_bounded(data: bytes, limit: int) -> bytes:
    """``zlib.decompress`` that refuses to produce more than ``limit`` bytes."""
    d = zlib.decompressobj()
    out = d.decompress(data, limit + 1)
    if len(out) > limit:
        raise ValueError(f"inflated size exceeds {limit} bytes")
    if not d.eof:
        raise zlib.error("incomplete or truncated stream")
    return out


def read_rgb_png(png_bytes: bytes, *, max_rgb_bytes: int | None = None) -> tuple[int, int, bytes]:
    """Read 8-bit non-interlaced RGB PNG → (width, height, rgb_bytes).

    Supports filter type 0 only (as produced by ``write_rgb_png``).
    Concatenates multiple IDAT chunks.

    With ``max_rgb_bytes`` only the first rows needed to supply that many
    channel bytes are inflated and returned. Reading a short hidden payload
    then costs a few rows, not the whole image, so a crafted file that claims
    a huge canvas cannot make a header probe expensive.
    """
    if not png_bytes.startswith(PNG_SIG):
        raise ValueError("not a PNG (bad signature)")

    pos = len(PNG_SIG)
    width: Optional[int] = None
    height: Optional[int] = None
    idat = bytearray()

    while pos + 8 <= len(png_bytes):
        (length,) = struct.unpack_from(">I", png_bytes, pos)
        pos += 4
        tag = png_bytes[pos : pos + 4]
        pos += 4
        if pos + length + 4 > len(png_bytes):
            raise ValueError("truncated PNG chunk")
        data = png_bytes[pos : pos + length]
        pos += length
        # CRC present but not verified (writer is trusted for v1)
        pos += 4

        if tag == b"IHDR":
            if length != 13:
                raise ValueError("bad IHDR length")
            (
                width,
                height,
                bit_depth,
                color_type,
                compression,
                filt,
                interlace,
            ) = struct.unpack(">IIBBBBB", data)
            if width < 1 or height < 1 or width * height > MAX_PNG_PIXELS:
                raise ValueError(
                    f"unsupported PNG size {width}x{height} "
                    f"(limit {MAX_PNG_PIXELS} pixels)"
                )
            if bit_depth != 8 or color_type != 2:
                raise ValueError(
                    f"unsupported PNG: bit_depth={bit_depth} color_type={color_type}"
                )
            if compression != 0 or filt != 0 or interlace != 0:
                raise ValueError("unsupported PNG compression/filter/interlace")
        elif tag == b"IDAT":
            idat.extend(data)
        elif tag == b"IEND":
            break

    if width is None or height is None:
        raise ValueError("missing IHDR")
    if not idat:
        raise ValueError("missing IDAT")

    stride = width * 3
    rows = height
    if max_rgb_bytes is not None:
        rows = min(height, max(1, -(-max_rgb_bytes // stride)))
    expected_raw = rows * (1 + stride)
    if rows == height:
        # IHDR fixes the inflated size, so never inflate past it (zlib bomb guard).
        raw = inflate_bounded(bytes(idat), expected_raw)
    else:
        raw = zlib.decompressobj().decompress(bytes(idat), expected_raw)
    if len(raw) != expected_raw:
        raise ValueError(f"unexpected inflated size {len(raw)} != {expected_raw}")

    out = bytearray(rows * stride)
    i = 0
    o = 0
    for _y in range(rows):
        filter_type = raw[i]
        i += 1
        if filter_type != 0:
            raise ValueError(f"unsupported filter type {filter_type}")
        out[o : o + stride] = raw[i : i + stride]
        i += stride
        o += stride
    return width, height, bytes(out)


def embed_lsb(png_bytes: bytes, payload: bytes) -> bytes:
    """Embed ``payload`` bits into RGB LSBs (MSB-first per payload byte)."""
    if not payload:
        raise ValueError("empty payload")
    w, h, rgb = read_rgb_png(png_bytes)
    return embed_lsb_rgb(w, h, rgb, payload)


def embed_lsb_rgb(w: int, h: int, rgb: bytes, payload: bytes) -> bytes:
    """``embed_lsb`` for pixels already in hand; returns the PNG.

    Callers that have just decoded an image use this instead of encoding it
    and handing it to ``embed_lsb`` to decode again. The result is the same
    bytes either way.
    """
    if not payload:
        raise ValueError("empty payload")
    bits_needed = len(payload) * 8
    if bits_needed > len(rgb):
        raise ValueError(
            f"payload too large for image capacity: need {bits_needed} bits, have {len(rgb)}"
        )
    buf = bytearray(rgb)
    bit_i = 0
    for byte in payload:
        for shift in range(7, -1, -1):
            bit = (byte >> shift) & 1
            buf[bit_i] = (buf[bit_i] & 0xFE) | bit
            bit_i += 1
    return write_rgb_png(w, h, bytes(buf))


def extract_lsb(png_bytes: bytes, n: int) -> bytes:
    """Extract ``n`` payload bytes from RGB LSBs (MSB-first per byte)."""
    if n < 0:
        raise ValueError("n must be >= 0")
    if n == 0:
        return b""
    bits_needed = n * 8
    # Only the rows that hold the payload are decoded.
    w, h, rgb = read_rgb_png(png_bytes, max_rgb_bytes=bits_needed)
    if bits_needed > w * h * 3:
        raise ValueError(
            f"requested {bits_needed} bits exceeds image capacity {w * h * 3}"
        )
    out = bytearray(n)
    bit_i = 0
    for bi in range(n):
        byte = 0
        for _ in range(8):
            byte = (byte << 1) | (rgb[bit_i] & 1)
            bit_i += 1
        out[bi] = byte
    return bytes(out)
