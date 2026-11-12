"""Minimal pure-Python AES-256-GCM (no external crypto deps).

Implements AES-128/192/256 block encrypt and GCM AEAD as used by
crypto_payload.seal_intent / open_intent. Validated against NIST vectors.
"""
from __future__ import annotations

import hmac
import struct
from typing import Tuple

# --- AES S-box and helpers -------------------------------------------------

_SBOX = (
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
)

_RCON = (
    0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36,
)


def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1B) & 0xFF if (a & 0x80) else (a << 1) & 0xFF


def _mix_column(col: list[int]) -> list[int]:
    a, b, c, d = col
    return [
        _xtime(a) ^ _xtime(b) ^ b ^ c ^ d,
        a ^ _xtime(b) ^ _xtime(c) ^ c ^ d,
        a ^ b ^ _xtime(c) ^ _xtime(d) ^ d,
        _xtime(a) ^ a ^ b ^ c ^ _xtime(d),
    ]


def _expand_key(key: bytes) -> list[list[int]]:
    """AES key expansion → list of 16-byte round keys as lists of ints."""
    key_len = len(key)
    if key_len not in (16, 24, 32):
        raise ValueError("AES key must be 16, 24, or 32 bytes")
    n_k = key_len // 4
    n_r = {16: 10, 24: 12, 32: 14}[key_len]
    w: list[list[int]] = []
    for i in range(n_k):
        w.append(list(key[4 * i : 4 * i + 4]))
    for i in range(n_k, 4 * (n_r + 1)):
        temp = w[i - 1][:]
        if i % n_k == 0:
            temp = [_SBOX[b] for b in (temp[1], temp[2], temp[3], temp[0])]
            temp[0] ^= _RCON[i // n_k]
        elif n_k > 6 and i % n_k == 4:
            temp = [_SBOX[b] for b in temp]
        w.append([w[i - n_k][j] ^ temp[j] for j in range(4)])
    round_keys: list[list[int]] = []
    for r in range(n_r + 1):
        rk: list[int] = []
        for c in range(4):
            rk.extend(w[4 * r + c])
        round_keys.append(rk)
    return round_keys


def _add_round_key(state: list[int], rk: list[int]) -> None:
    for i in range(16):
        state[i] ^= rk[i]


def _sub_bytes(state: list[int]) -> None:
    for i in range(16):
        state[i] = _SBOX[state[i]]


def _shift_rows(state: list[int]) -> None:
    # row 1
    state[1], state[5], state[9], state[13] = state[5], state[9], state[13], state[1]
    # row 2
    state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
    # row 3
    state[3], state[7], state[11], state[15] = state[15], state[3], state[7], state[11]


def _mix_columns(state: list[int]) -> None:
    for c in range(4):
        col = [state[c * 4 + r] for r in range(4)]
        mixed = _mix_column(col)
        for r in range(4):
            state[c * 4 + r] = mixed[r]


def aes_encrypt_block(key: bytes, block: bytes) -> bytes:
    """Encrypt a single 16-byte block with AES."""
    if len(block) != 16:
        raise ValueError("block must be 16 bytes")
    round_keys = _expand_key(key)
    n_r = len(round_keys) - 1
    state = list(block)
    _add_round_key(state, round_keys[0])
    for r in range(1, n_r):
        _sub_bytes(state)
        _shift_rows(state)
        _mix_columns(state)
        _add_round_key(state, round_keys[r])
    _sub_bytes(state)
    _shift_rows(state)
    _add_round_key(state, round_keys[n_r])
    return bytes(state)


# --- Galois field GHASH (GF(2^128)) ----------------------------------------

_R = 0xE1000000000000000000000000000000  # reduction polynomial for GCM


def _bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, "big")


def _int_to_bytes(x: int) -> bytes:
    return x.to_bytes(16, "big")


def _gf_mult(x: int, y: int) -> int:
    """Multiply two elements in GF(2^128) as used by GCM (bit-reflected)."""
    z = 0
    v = y
    for i in range(127, -1, -1):
        if (x >> i) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ _R
        else:
            v >>= 1
    return z & ((1 << 128) - 1)


def _ghash(h: int, data: bytes) -> int:
    """GHASH over data (already length-padded externally as needed)."""
    y = 0
    for i in range(0, len(data), 16):
        block = data[i : i + 16]
        if len(block) < 16:
            block = block + b"\x00" * (16 - len(block))
        y = _gf_mult(y ^ _bytes_to_int(block), h)
    return y


def _inc32(block: bytes) -> bytes:
    """Increment the last 32 bits of a 16-byte counter block."""
    prefix, ctr = block[:12], int.from_bytes(block[12:], "big")
    return prefix + ((ctr + 1) & 0xFFFFFFFF).to_bytes(4, "big")


def _gctr(key: bytes, icb: bytes, data: bytes) -> bytes:
    """GCTR: encrypt successive counter blocks starting at icb, XOR with data."""
    if not data:
        return b""
    out = bytearray()
    cb = icb
    for i in range(0, len(data), 16):
        keystream = aes_encrypt_block(key, cb)
        chunk = data[i : i + 16]
        out.extend(bytes(a ^ b for a, b in zip(chunk, keystream)))
        cb = _inc32(cb)
    return bytes(out)


def _j0_from_iv(h: int, iv: bytes) -> bytes:
    """Compute initial counter block J0 from IV (SP 800-38D)."""
    if len(iv) == 12:
        return iv + b"\x00\x00\x00\x01"
    # For non-96-bit IV: GHASH(H, IV || 0^s || [len(IV)]_64)
    s = (16 - (len(iv) % 16)) % 16
    ghash_in = iv + b"\x00" * s + b"\x00" * 8 + struct.pack(">Q", len(iv) * 8)
    return _int_to_bytes(_ghash(h, ghash_in))


def _auth_tag(h: int, aad: bytes, ciphertext: bytes, j0: bytes, key: bytes) -> bytes:
    """Compute GCM authentication tag (16 bytes)."""
    u = (16 - (len(ciphertext) % 16)) % 16
    v = (16 - (len(aad) % 16)) % 16
    ghash_in = (
        aad
        + b"\x00" * v
        + ciphertext
        + b"\x00" * u
        + struct.pack(">QQ", len(aad) * 8, len(ciphertext) * 8)
    )
    s = _ghash(h, ghash_in)
    # tag = GCTR(K, J0, S) with single block — i.e. E(K, J0) XOR S
    ekj0 = aes_encrypt_block(key, j0)
    return bytes(a ^ b for a, b in zip(ekj0, _int_to_bytes(s)))


def aes_gcm_encrypt(
    key: bytes,
    nonce: bytes,
    plaintext: bytes,
    aad: bytes = b"",
) -> Tuple[bytes, bytes]:
    """AES-GCM encrypt. Returns (ciphertext, tag) with 16-byte tag."""
    if len(key) not in (16, 24, 32):
        raise ValueError("key must be 16, 24, or 32 bytes")
    if not nonce:
        raise ValueError("nonce must be non-empty")
    h = _bytes_to_int(aes_encrypt_block(key, b"\x00" * 16))
    j0 = _j0_from_iv(h, nonce)
    # CTR starts at inc32(J0)
    ciphertext = _gctr(key, _inc32(j0), plaintext)
    tag = _auth_tag(h, aad, ciphertext, j0, key)
    return ciphertext, tag


def aes_gcm_decrypt(
    key: bytes,
    nonce: bytes,
    ciphertext: bytes,
    tag: bytes,
    aad: bytes = b"",
) -> bytes:
    """AES-GCM decrypt. Raises ValueError if authentication fails."""
    if len(key) not in (16, 24, 32):
        raise ValueError("key must be 16, 24, or 32 bytes")
    if len(tag) != 16:
        raise ValueError("tag must be 16 bytes")
    if not nonce:
        raise ValueError("nonce must be non-empty")
    h = _bytes_to_int(aes_encrypt_block(key, b"\x00" * 16))
    j0 = _j0_from_iv(h, nonce)
    expected = _auth_tag(h, aad, ciphertext, j0, key)
    if not hmac.compare_digest(expected, tag):
        raise ValueError("AES-GCM authentication failed")
    return _gctr(key, _inc32(j0), ciphertext)
