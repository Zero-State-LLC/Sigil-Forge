"""v0.1.1 hardening: atomic run dirs, env passphrase, epsilon verify depth."""

from __future__ import annotations

from pathlib import Path

import pytest

from sigil_forge.construct import PASSPHRASE_ENV, resolve_passphrase, run as construct_run
from sigil_forge.stego_svg import expected_epsilon_bits, extract as extract_svg
from sigil_forge.verify import run as verify_run


def test_resolve_passphrase_env_and_explicit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(PASSPHRASE_ENV, raising=False)
    assert resolve_passphrase(None) is None
    monkeypatch.setenv(PASSPHRASE_ENV, "from-env")
    assert resolve_passphrase(None) == "from-env"
    assert resolve_passphrase("from-cli") == "from-cli"
    assert resolve_passphrase("") is None or resolve_passphrase("") == "from-env"
    # empty string is not a real passphrase; resolve treats "" as unset explicit
    assert resolve_passphrase(None) == "from-env"


def test_construct_passphrase_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(PASSPHRASE_ENV, "env-secret-passphrase")
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        mode="creative",
        out_root=tmp_path,
        square="saturn",
        seal_packet=True,
        passphrase=None,
    )
    assert packet["crypto"]["key_policy"] == "passphrase"
    assert packet["crypto"]["ciphertext_present"] is True
    assert "normalized_intent" not in packet or packet.get("normalized_intent") is None


def test_atomic_run_dir_no_staging_left(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        out_root=tmp_path,
        square="saturn",
    )
    run_dir = Path(packet["artifacts"]["run_dir"])
    assert run_dir.is_dir()
    assert (run_dir / "glyph.svg").is_file()
    assert (run_dir / "forge-packet.json").is_file()
    leftovers = [
        p for p in tmp_path.iterdir() if p.name.startswith(".sf-staging-")
    ]
    assert leftovers == []


def test_verify_epsilon_bits_match_digest(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus while shipping Sigil-Forge",
        out_root=tmp_path,
        square="saturn",
    )
    svg = Path(packet["artifacts"]["svg"])
    text = svg.read_text(encoding="utf-8")
    got = extract_svg(text)
    bits = got.get("epsilon_bits") or []
    assert bits, "expected path_epsilon bits on fused glyph"
    expected = expected_epsilon_bits(packet["intent_digest"], len(bits))
    assert bits == expected

    v = verify_run(svg)
    assert v["ok"] is True
    assert v.get("epsilon_bit_count") == len(bits)

    # Tamper one coordinate parity → verify fails
    tampered = text
    # Flip a data-sf-metric first to ensure we still have metrics; for epsilon
    # replace first float digit slightly by rewriting a points value.
    import re

    def flip_first_float(m: re.Match[str]) -> str:
        body = m.group(2)
        fm = re.search(r"[-+]?(?:\d+\.\d+|\d+)", body)
        if not fm:
            return m.group(0)
        val = float(fm.group(0))
        # Push off EPS parity grid relative to encoded bit
        new_val = val + 0.0015
        new_body = body[: fm.start()] + f"{new_val:.6f}" + body[fm.end() :]
        return f"points=\"{new_body}\"" if m.group(0).startswith("points") else m.group(0)

    # Simpler: corrupt digest in metadata so metrics still pass format but
    # epsilon stream won't match the forged metadata digest. Replace d= hex in
    # base64 is hard; instead flip epsilon by rewriting first points float off-grid.
    from sigil_forge.stego_svg import EPS, _decode_float_bit, _encode_float_bit

    def flip_points(m: re.Match[str]) -> str:
        quote = m.group(1)
        body = m.group(2)
        fm = re.search(r"[-+]?(?:\d+\.\d+|\d+\.|\.\d+|\d+)", body)
        if not fm:
            return m.group(0)
        val = float(fm.group(0))
        bit = _decode_float_bit(val)
        flipped = _encode_float_bit(val, 1 - bit)
        # ensure different
        if abs(flipped - val) < EPS / 2:
            flipped = val + EPS
        new_body = body[: fm.start()] + f"{flipped:.6f}" + body[fm.end() :]
        return f"points={quote}{new_body}{quote}"

    tampered = re.sub(
        r'points=([\'"])(.*?)\1',
        flip_points,
        text,
        count=1,
        flags=re.DOTALL,
    )
    bad_path = tmp_path / "tampered.svg"
    bad_path.write_text(tampered, encoding="utf-8")
    bad = verify_run(bad_path)
    assert bad["ok"] is False
    assert "epsilon" in (bad.get("detail") or "").lower() or "bit" in (
        bad.get("detail") or ""
    ).lower()
