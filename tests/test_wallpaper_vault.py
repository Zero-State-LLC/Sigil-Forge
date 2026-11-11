"""v0.13 product: wallpaper SF12 sealed vault (intent + methods in-image)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from construct import run as construct_run
from wallpaper.pipeline import build_wallpaper
from wallpaper.vault import (
    build_vault_document,
    open_wallpaper_vault,
    pack_sf12,
    seal_vault,
    unpack_sf12,
)

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"


def test_sf12_roundtrip_pack_unpack():
    vault = {
        "schema": "sigil-forge-wallpaper-vault/1",
        "intent": "I maintain calm focus",
        "normalized_intent": "i maintain calm focus",
        "intent_digest": "ab" * 32,
    }
    sealed = seal_vault(vault, "vault-pass", kdf="pbkdf2-sha256")
    payload = pack_sf12(
        intent_digest="ab" * 32,
        sigil_root="cd" * 32,
        sealed_blob=sealed,
    )
    env = unpack_sf12(payload)
    assert env["format"] == "SF12"
    assert env["intent_digest"] == "ab" * 32
    assert env["sigil_root"] == "cd" * 32
    assert env["has_vault"] is True


def test_build_vault_document_methods():
    packet = {
        "intent_digest": "11" * 32,
        "normalized_intent": "i maintain calm focus",
        "sigil_root": "22" * 32,
        "methods": {"spare": {"mode": "letter_monogram"}},
        "channels": [{"id": "spare_monogram", "status": "applied"}],
        "ontology": {"family": "intent_sigil"},
        "intent_commitment": {"scheme": "sha256-salted-v1", "value": "33" * 32},
    }
    v = build_vault_document(packet=packet, intent="I maintain calm focus")
    assert v["intent"] == "I maintain calm focus"
    assert v["methods"]["spare"]["mode"] == "letter_monogram"
    assert v["product"] == "wallpaper"


def test_wallpaper_embeds_vault(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path / "forge",
        kamea_encoding="latin_mod9_v1",
        passphrase="vault-pass",
        kdf="pbkdf2-sha256",
        write_receipt=False,
    )
    run = Path(packet["artifacts"]["run_dir"])
    res = build_wallpaper(
        run,
        surface="phone_lock",
        passphrase="vault-pass",
        intent="I maintain calm focus",
        embedded_payload="vault",
        kdf="pbkdf2-sha256",
    )
    assert res["ok"] is True, res
    assert res["vault_status"] == "embedded"
    assert res["embedded_payload"] == "vault"
    wp = Path(res["wallpaper"])
    assert wp.is_file()
    opened = open_wallpaper_vault(wp, "vault-pass")
    assert opened["ok"] is True
    assert opened["normalized_intent"] == "i maintain calm focus"
    assert opened["vault"]["methods"]
    # wrong passphrase fails
    import pytest

    with pytest.raises(Exception):
        open_wallpaper_vault(wp, "wrong-pass")


def test_open_wallpaper_cli(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path / "forge",
        kamea_encoding="latin_mod9_v1",
        passphrase="cli-vault",
        kdf="pbkdf2-sha256",
        write_receipt=False,
    )
    run = Path(packet["artifacts"]["run_dir"])
    res = build_wallpaper(
        run,
        surface="phone_lock",
        passphrase="cli-vault",
        intent="I maintain calm focus",
        embedded_payload="vault",
        kdf="pbkdf2-sha256",
    )
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "open",
            "--wallpaper",
            res["wallpaper"],
            "--passphrase",
            "cli-vault",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert "calm focus" in (out.get("intent") or out.get("normalized_intent") or "")


def test_construct_wallpaper_product_one_shot(tmp_path: Path):
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "construct",
            "--intent",
            "I maintain calm focus",
            "--out",
            str(tmp_path / "out"),
            "--kamea-encoding",
            "latin_mod9_v1",
            "--wallpaper",
            "--surface",
            "phone_lock",
            "--passphrase",
            "one-shot-pass",
            "--kdf",
            "pbkdf2-sha256",
            "--embed",
            "vault",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={**__import__("os").environ, "SIGIL_FORGE_PASSPHRASE": ""},
    )
    assert r.returncode == 0, r.stderr + r.stdout
    summary = json.loads(r.stdout)
    assert summary.get("ok") is not False
    wps = summary.get("wallpapers") or []
    assert wps, summary
    assert wps[0].get("vault_status") == "embedded"


def test_sf12_refuses_decompression_bomb():
    """A carrier PNG is untrusted: a tiny sealed block must not inflate unbounded."""
    import struct
    import zlib

    import pytest

    from wallpaper import vault

    bomb = zlib.compress(b"\x00" * (vault.SF12_MAX_SEALED_JSON + 1), 9)
    assert len(bomb) < 64_000  # fits well inside the 512 kB extract limit
    body = (
        vault.SF12_MAGIC
        + bytes([vault.SF12_VERSION, vault.SF12_FLAG_VAULT])
        + b"\x00" * 64
        + struct.pack(">I", len(bomb))
        + bomb
    )
    payload = body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    with pytest.raises(ValueError, match="inflated size exceeds"):
        unpack_sf12(payload)
