"""Ledger/receipt defaults live under the state root, not the install tree."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sigil_forge import receipt

ROOT = Path(__file__).resolve().parents[1]
_VARS = (
    "SIGIL_FORGE_HOME", "SIGIL_FORGE_ROOT", "SIGIL_FORGE_DIR", "SIGIL_FORGE_SKILL_DIR",
    "SIGIL_FORGE_STATE_DIR", "SIGIL_FORGE_LEDGER", "SIGIL_FORGE_RECEIPTS",
    "SIGIL_FORGE_CANON_PROPOSALS", "HERMES_SKILL_DIR", "HERMES_HOME",
)
_FUNCS = (
    (receipt.default_ledger_path, receipt.DEFAULT_LEDGER_NAME),
    (receipt.default_receipts_path, receipt.DEFAULT_RECEIPTS_NAME),
    (receipt.default_canon_proposals_path, receipt.DEFAULT_CANON_PROPOSALS_NAME),
)


def _clean(monkeypatch, tmp_path):
    for name in _VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SIGIL_FORGE_STATE_DIR", str(tmp_path / "state"))


def test_defaults_under_state_root_when_nothing_legacy(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    install = tmp_path / "install"
    install.mkdir()
    monkeypatch.setenv("HERMES_SKILL_DIR", str(install))
    for fn, name in _FUNCS:
        assert fn() == (tmp_path / "state").resolve() / "ledger" / name


def test_legacy_file_is_kept_when_new_absent(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    install = tmp_path / "install"
    legacy_dir = install / "out" / "sigil-forge"
    legacy_dir.mkdir(parents=True)
    monkeypatch.setenv("HERMES_SKILL_DIR", str(install))
    for fn, name in _FUNCS:
        (legacy_dir / name).write_text("")
        assert fn() == install.resolve() / "out" / "sigil-forge" / name
    # Once the new-location file exists it wins.
    for fn, name in _FUNCS:
        new = (tmp_path / "state").resolve() / "ledger" / name
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_text("")
        assert fn() == new


def test_env_overrides_win(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    for var, fn in (
        ("SIGIL_FORGE_LEDGER", receipt.default_ledger_path),
        ("SIGIL_FORGE_RECEIPTS", receipt.default_receipts_path),
        ("SIGIL_FORGE_CANON_PROPOSALS", receipt.default_canon_proposals_path),
    ):
        monkeypatch.setenv(var, str(tmp_path / var))
        assert fn() == tmp_path / var


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_construct_writes_receipts_under_private_state_ledger(tmp_path, monkeypatch, request):
    from sigil_forge.construct import run as construct_run

    _clean(monkeypatch, tmp_path)
    out_existed = (ROOT / "out").exists()
    before = sorted(p.name for p in (ROOT / "out").iterdir()) if out_existed else []
    previous = os.umask(0o022)
    request.addfinalizer(lambda: os.umask(previous))
    construct_run("I maintain calm focus")
    ledger_dir = tmp_path / "state" / "ledger"
    assert (ledger_dir / receipt.DEFAULT_RECEIPTS_NAME).is_file()
    assert ledger_dir.stat().st_mode & 0o777 == 0o700
    assert (ROOT / "out").exists() == out_existed
    if out_existed:
        assert sorted(p.name for p in (ROOT / "out").iterdir()) == before


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_operator_env_path_keeps_plain_mkdir_mode(tmp_path, monkeypatch, request):
    _clean(monkeypatch, tmp_path)
    previous = os.umask(0o022)
    request.addfinalizer(lambda: os.umask(previous))
    target = tmp_path / "elsewhere" / "sub" / "r.jsonl"
    monkeypatch.setenv("SIGIL_FORGE_RECEIPTS", str(target))
    receipt.append_receipt_log({"a": 1})
    assert target.parent.stat().st_mode & 0o777 == 0o755


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_new_receipt_files_are_owner_only(tmp_path, monkeypatch, request):
    """Receipts are private records: files this engine creates are 0600."""
    _clean(monkeypatch, tmp_path)
    previous = os.umask(0o022)
    request.addfinalizer(lambda: os.umask(previous))
    single = receipt.write_receipt_file({"a": 1}, tmp_path / "run" / "run-receipt.json")
    assert single.stat().st_mode & 0o777 == 0o600
    log = tmp_path / "shared" / "r.jsonl"
    receipt.append_receipt_log({"a": 1}, log)
    receipt.append_receipt_log({"a": 2}, log)
    assert log.stat().st_mode & 0o777 == 0o600
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_existing_receipt_log_keeps_its_mode(tmp_path, monkeypatch):
    _clean(monkeypatch, tmp_path)
    log = tmp_path / "r.jsonl"
    log.write_text("", encoding="utf-8")
    os.chmod(log, 0o644)
    receipt.append_receipt_log({"a": 1}, log)
    assert log.stat().st_mode & 0o777 == 0o644


def test_receipt_has_no_plaintext_or_nonce_but_is_not_digests_only(tmp_path, monkeypatch):
    """Pins why receipts are private: intent-derived method data is in them."""
    import json

    from sigil_forge.construct import run as construct_run

    _clean(monkeypatch, tmp_path)
    intent = "I maintain calm focus"
    monkeypatch.setenv("SIGIL_FORGE_RECEIPTS", str(tmp_path / "log.jsonl"))
    result = construct_run(intent, out_root=tmp_path / "products")
    path = result["artifacts"]["receipt_json"]
    text = open(path, encoding="utf-8").read()
    assert intent.lower() not in text.lower()
    assert "nonce" not in text.lower()
    methods = json.loads(text)["methods"]
    assert methods["spare"]["spare_result"]["spare_letters"] == "mntclfs"


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_run_folder_is_owner_only_even_under_a_chosen_out(tmp_path, monkeypatch, request):
    """Private run files rely on this: most have ordinary modes inside it."""
    from sigil_forge.construct import run as construct_run

    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("SIGIL_FORGE_RECEIPTS", str(tmp_path / "log.jsonl"))
    previous = os.umask(0o022)
    request.addfinalizer(lambda: os.umask(previous))
    out = tmp_path / "chosen"
    out.mkdir(mode=0o755)
    packet = construct_run("I maintain calm focus", out_root=out)
    run_dir = Path(packet["artifacts"]["run_dir"])
    assert run_dir.parent == out
    assert run_dir.stat().st_mode & 0o777 == 0o700
    assert out.stat().st_mode & 0o777 == 0o755  # the operator's folder is left alone


def test_manifest_is_private_and_the_root_needs_only_its_digest(tmp_path, monkeypatch):
    """Pins why forge-manifest.json is private, and that the public file does not need it."""
    import json

    from sigil_forge.construct import run as construct_run

    _clean(monkeypatch, tmp_path)
    monkeypatch.setenv("SIGIL_FORGE_RECEIPTS", str(tmp_path / "log.jsonl"))
    intent = "I maintain calm focus"
    packet = construct_run(intent, out_root=tmp_path / "products")
    run_dir = Path(packet["artifacts"]["run_dir"])
    raw = (run_dir / "forge-manifest.json").read_bytes()
    manifest = json.loads(raw)
    # Intent-derived, so private ...
    assert manifest["methods"]["spare"]["spare_result"]["spare_letters"] == "mntclfs"
    # ... but no plaintext and no nonce value.
    text = raw.decode("utf-8").lower()
    assert intent.lower() not in text
    assert not any("nonce" in key.lower() for key in _keys(manifest))
    # The public root file carries the manifest's digest, not its content.
    root_text = (run_dir / "artifact-root.json").read_text(encoding="utf-8")
    assert "mntclfs" not in root_text and "methods" not in root_text
    from sigil_forge.forge_manifest import manifest_digest

    leaves = {leaf["type"]: leaf["value"] for leaf in json.loads(root_text)["leaves"]}
    assert leaves["forge_manifest_digest"] == manifest_digest(manifest)


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)
