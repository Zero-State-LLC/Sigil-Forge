"""The forge manifest is public (ids and digests); method detail is private."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge import forge_manifest as fm
from sigil_forge.construct import run as construct_run
from sigil_forge.normalize import normalize_intent

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "scripts" / "sigil_forge.py")]
INTENT = "I maintain calm focus"
# What the engine derives from INTENT; none of it may reach a public file.
LETTERS = "mntclfs"


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("split")
    packet = construct_run(INTENT, out_root=out, passphrase="split-pass", proof="commitment")
    return Path(packet["artifacts"]["run_dir"])


def _copy(run_dir: Path, tmp_path: Path) -> Path:
    import shutil

    dest = tmp_path / "run"
    shutil.copytree(run_dir, dest)
    return dest


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def test_public_manifest_holds_identifiers_and_digests_only(run_dir):
    raw = (run_dir / fm.PUBLIC_NAME).read_text(encoding="utf-8")
    manifest = json.loads(raw)
    assert manifest["schema_version"] == "2.0.0"
    low = raw.lower()
    for private in (INTENT.lower(), normalize_intent(INTENT), LETTERS, "nonce"):
        assert private not in low, private
    # No lists inside methods, no numbers anywhere in them: nothing that could
    # carry a sequence, a coordinate or a length.
    for path, value in _walk(manifest["methods"], "methods"):
        assert "[" not in path, path
        assert isinstance(value, str), (path, value)
        assert path.rsplit(".", 1)[-1] in fm.PUBLIC_METHOD_KEYS, path
    assert all(set(c) == {"id", "status"} for c in manifest["channels"])
    assert fm.public_shape_problems(manifest) == []
    assert manifest["methods"] == fm.public_methods(manifest["methods"])


def test_method_manifest_holds_the_detail_and_is_owner_only(run_dir):
    path = run_dir / fm.METHOD_NAME
    method = json.loads(path.read_text(encoding="utf-8"))
    assert method["kind"] == "sigil_forge_method_manifest"
    assert method["methods"]["spare"]["spare_result"]["spare_letters"] == LETTERS
    assert any(c.get("detail") for c in method["channels"])
    text = path.read_text(encoding="utf-8").lower()
    assert INTENT.lower() not in text  # still no plaintext
    assert not any("nonce" in p.rsplit(".", 1)[-1].lower() for p, _ in _walk(method))
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_the_two_leaves_are_distinct_and_match_their_files(run_dir):
    leaves = {
        leaf["type"]: leaf["value"]
        for leaf in json.loads((run_dir / fm.ROOT_NAME).read_text(encoding="utf-8"))["leaves"]
    }
    public = json.loads((run_dir / fm.PUBLIC_NAME).read_text(encoding="utf-8"))
    method = json.loads((run_dir / fm.METHOD_NAME).read_text(encoding="utf-8"))
    assert leaves["forge_manifest_digest"] == fm.manifest_digest(public)
    assert leaves["method_manifest_digest"] == fm.manifest_digest(method)
    assert leaves["forge_manifest_digest"] != leaves["method_manifest_digest"]
    assert public["method_manifest_digest"] == leaves["method_manifest_digest"]
    capsule = json.loads((run_dir / "intent-capsule.json").read_text(encoding="utf-8"))
    assert leaves["method_manifest_digest"] in json.dumps(capsule)


def test_public_methods_drops_everything_but_allowlisted_identifiers():
    methods = {
        "spare": {
            "family": "intent_compression",
            "letter_count": 7,
            "spare_result": {"spare_letters": "mntclfs", "letter_sequence": ["m"], "status": "shipped"},
            "notes": ["free text"],
        },
        "kamea": {"planet": "saturn", "order": 3, "path": [[1.5, 2.5]], "cipher": "x" * 200},
        "odd": {"family": "has\nnewline", "method_id": {"nested": "dict"}, "status": True},
        "empty": {"hebrew_sequence": ["a"]},
        "sigil_root": "ab" * 32,
        "not_a_dict": "text",
    }
    assert fm.public_methods(methods) == {
        "empty": {},
        "kamea": {"planet": "saturn"},
        "odd": {},
        "spare": {"family": "intent_compression", "spare_result": {"status": "shipped"}},
    }


def test_verify_root_with_public_files_only(run_dir, tmp_path):
    """What a third party holds: the root and the public manifest."""
    public_only = tmp_path / "shared"
    public_only.mkdir()
    for name in (fm.ROOT_NAME, fm.PUBLIC_NAME):
        (public_only / name).write_bytes((run_dir / name).read_bytes())
    got = fm.check_run_root(public_only)
    assert got["ok"] is True and got["manifest_public_shape"] is True
    assert "forge_manifest_digest" in got["checked"]
    assert any("method_manifest_digest" in n for n in got["not_checked"])
    assert fm.check_run_root(public_only / fm.ROOT_NAME)["ok"] is True
    full = fm.check_run_root(run_dir)
    assert full["ok"] is True and "method_manifest_digest" in full["checked"]


@pytest.mark.parametrize(
    ("name", "edit", "expect"),
    [
        (fm.PUBLIC_NAME, lambda d: d.update(mode="practice"), "does not match its leaf"),
        (fm.PUBLIC_NAME, lambda d: d["methods"]["spare"].update(spare_letters="x"), "does not match its leaf"),
        (fm.METHOD_NAME, lambda d: d["methods"]["spare"].update(letter_count=99), "method-manifest.json does not match"),
        (fm.ROOT_NAME, lambda d: d.update(sigil_root="0" * 64), "sigil_root does not match"),
        (fm.ROOT_NAME, lambda d: d["leaves"][0].update(value="0" * 64), "sigil_root does not match"),
        (fm.ROOT_NAME, lambda d: d["leaves"].append(dict(d["leaves"][0])), "malformed"),
        (fm.ROOT_NAME, lambda d: d.update(leaves=[]), "malformed"),
    ],
)
def test_verify_root_catches_changes(run_dir, tmp_path, name, edit, expect):
    run = _copy(run_dir, tmp_path)
    path = run / name
    data = json.loads(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    got = fm.check_run_root(run)
    assert got["ok"] is False and expect in got["detail"], got["detail"]


def test_a_manifest_that_smuggles_detail_is_not_reported_public(run_dir, tmp_path):
    """Even with every digest fixed up, extra method data is called out."""
    from sigil_forge.artifact_root import merkle_root

    run = _copy(run_dir, tmp_path)
    manifest = json.loads((run / fm.PUBLIC_NAME).read_text(encoding="utf-8"))
    manifest["methods"]["spare"]["spare_letters"] = LETTERS
    (run / fm.PUBLIC_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    root = json.loads((run / fm.ROOT_NAME).read_text(encoding="utf-8"))
    for leaf in root["leaves"]:
        if leaf["type"] == "forge_manifest_digest":
            leaf["value"] = fm.manifest_digest(manifest)
    root["sigil_root"] = merkle_root([(leaf["type"], leaf["value"]) for leaf in root["leaves"]])
    (run / fm.ROOT_NAME).write_text(json.dumps(root), encoding="utf-8")
    got = fm.check_run_root(run)
    assert got["ok"] is False and got["manifest_public_shape"] is False
    assert "more than identifiers" in got["detail"]
    assert "does not match its leaf" not in got["detail"]  # caught by shape, not by digest


def test_a_run_from_before_the_split_still_checks_and_is_reported_private(run_dir, tmp_path):
    """Rebuild the old shape: one manifest with the detail, one digest for both leaves."""
    from sigil_forge.artifact_root import merkle_root

    run = _copy(run_dir, tmp_path)
    method = json.loads((run / fm.METHOD_NAME).read_text(encoding="utf-8"))
    public = json.loads((run / fm.PUBLIC_NAME).read_text(encoding="utf-8"))
    old = {k: v for k, v in public.items() if k != "method_manifest_digest"}
    old.update(schema_version="1.0.0", methods=method["methods"], channels=method["channels"])
    (run / fm.PUBLIC_NAME).write_text(json.dumps(old), encoding="utf-8")
    (run / fm.METHOD_NAME).unlink()
    digest = fm.manifest_digest(old)
    root = json.loads((run / fm.ROOT_NAME).read_text(encoding="utf-8"))
    for leaf in root["leaves"]:
        if leaf["type"] in ("forge_manifest_digest", "method_manifest_digest"):
            leaf["value"] = digest
    root["sigil_root"] = merkle_root([(leaf["type"], leaf["value"]) for leaf in root["leaves"]])
    (run / fm.ROOT_NAME).write_text(json.dumps(root), encoding="utf-8")
    got = fm.check_run_root(run)
    assert got["ok"] is True
    assert got["manifest_schema"] == "1.0.0" and got["manifest_public_shape"] is False


@pytest.mark.parametrize("junk", ["[]", "7", "null", "{}", '{"leaves": 3, "sigil_root": 1}', "\xff"])
def test_verify_root_never_raises_on_bad_input(tmp_path, junk):
    (tmp_path / fm.ROOT_NAME).write_bytes(junk.encode("latin-1"))
    got = fm.check_run_root(tmp_path)
    assert got["ok"] is False and got["detail"]


def test_verify_root_needs_a_run_folder_or_its_root_file(run_dir, tmp_path):
    """Any other path used to fall back to checking its parent folder."""
    assert fm.check_run_root(run_dir / "does-not-exist.txt")["ok"] is False
    assert fm.check_run_root(run_dir / fm.PUBLIC_NAME)["ok"] is False
    assert fm.check_run_root(tmp_path / "nowhere")["ok"] is False
    assert fm.check_run_root(run_dir / fm.ROOT_NAME)["ok"] is True


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="needs symlinks")
def test_verify_root_refuses_a_symlinked_manifest(run_dir, tmp_path):
    run = _copy(run_dir, tmp_path)
    real = tmp_path / "real.json"
    (run / fm.PUBLIC_NAME).rename(real)
    (run / fm.PUBLIC_NAME).symlink_to(real)
    assert fm.check_run_root(run)["ok"] is False


def test_the_glyph_leaf_really_cannot_be_recomputed_from_the_finished_file(run_dir):
    """Pins the reason verify-root lists it under not_checked."""
    import hashlib

    leaves = {
        leaf["type"]: leaf["value"]
        for leaf in json.loads((run_dir / fm.ROOT_NAME).read_text(encoding="utf-8"))["leaves"]
    }
    finished = hashlib.sha256((run_dir / "glyph.svg").read_bytes()).hexdigest()
    assert finished != leaves["canonical_glyph_digest"]


def test_cli_verify_root_exit_codes(run_dir, tmp_path):
    ok = subprocess.run([*CLI, "verify-root", str(run_dir)], capture_output=True, text=True)
    assert ok.returncode == 0 and json.loads(ok.stdout)["ok"] is True
    run = _copy(run_dir, tmp_path)
    (run / fm.PUBLIC_NAME).write_text("{}", encoding="utf-8")
    bad = subprocess.run([*CLI, "verify-root", str(run)], capture_output=True, text=True)
    assert bad.returncode == 1 and json.loads(bad.stdout)["ok"] is False


def test_other_private_files_are_unchanged_by_the_split(run_dir):
    """The packet and receipt keep their content; only the manifest was split."""
    packet = json.loads((run_dir / "forge-packet.json").read_text(encoding="utf-8"))
    receipt = json.loads((run_dir / "run-receipt.json").read_text(encoding="utf-8"))
    for holder in (packet, receipt):
        assert holder["methods"]["spare"]["spare_result"]["spare_letters"] == LETTERS


# ------------------------------------------------ findings from review of #47


def _resealed(run: Path, edit_manifest=None, edit_root=None, drop_method=True) -> Path:
    """Change files, then fix up the leaf and the root so only the shape check can object."""
    from sigil_forge.artifact_root import merkle_root

    manifest = json.loads((run / fm.PUBLIC_NAME).read_text(encoding="utf-8"))
    if edit_manifest:
        edit_manifest(manifest)
    (run / fm.PUBLIC_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    root = json.loads((run / fm.ROOT_NAME).read_text(encoding="utf-8"))
    for leaf in root["leaves"]:
        if leaf["type"] == "forge_manifest_digest":
            leaf["value"] = fm.manifest_digest(manifest)
    if edit_root:
        edit_root(root)
    root["sigil_root"] = merkle_root([(leaf["type"], leaf["value"]) for leaf in root["leaves"]])
    (run / fm.ROOT_NAME).write_text(json.dumps(root), encoding="utf-8")
    if drop_method:
        (run / fm.METHOD_NAME).unlink(missing_ok=True)
    return run


SECRET = "i maintain calm focus"


@pytest.mark.parametrize(
    "smuggle",
    [
        lambda m: m.update(notes=SECRET),
        lambda m: m["output"].update(extra=SECRET),
        lambda m: m["construction"].update(extra=SECRET),
        lambda m: m["construction"].update(algorithm_version=SECRET),
        lambda m: m.update(mode=SECRET),
        lambda m: m.update(mode="calm"),
        lambda m: m["channels"][0].update(status=SECRET),
        lambda m: m["channels"][0].update(id=SECRET),
        lambda m: m["channels"][0].update(detail=SECRET),
        lambda m: m["channels"].append(SECRET),
        lambda m: m.update(channels=SECRET),
        lambda m: m.update(channels={"a": SECRET}),
        lambda m: m["methods"]["spare"].update(family=SECRET),
        lambda m: m["methods"]["spare"].update(family="calm_focus " * 20),
        lambda m: m["methods"]["spare"].update({"MNTCLFS cl m": {"family": "x"}}),
        lambda m: m["methods"].update({"I maintain": {"family": "x"}}),
        lambda m: m["methods"]["spare"].update(letter_sequence=["m", "n"]),
        lambda m: m["methods"]["spare"].update(letter_count=7),
        lambda m: m.update(forge_version=SECRET),
        lambda m: m.update(method_manifest_digest="mntclfs"),
        lambda m: m.pop("intent_digest"),
        lambda m: m["channels"][0].update(status="applied"),  # a letter channel must stay masked
    ],
)
def test_no_field_of_the_public_manifest_can_carry_free_text(run_dir, tmp_path, smuggle):
    """Leaf and root are fixed up each time, so only the shape check stands in the way."""
    run = _resealed(_copy(run_dir, tmp_path), edit_manifest=smuggle)
    got = fm.check_run_root(run)
    assert got["ok"] is False, got["detail"]
    assert got["manifest_public_shape"] is False
    assert "does not match its leaf" not in got["detail"]
    assert "sigil_root does not match" not in got["detail"]


def test_duplicate_keys_cannot_hide_content_from_the_digest(run_dir, tmp_path):
    run = _copy(run_dir, tmp_path)
    text = (run / fm.PUBLIC_NAME).read_text(encoding="utf-8")
    hidden = '{\n  "methods": {"spare": {"spare_letters": "mntclfs"}},' + text.lstrip()[1:]
    (run / fm.PUBLIC_NAME).write_text(hidden, encoding="utf-8")
    assert json.loads(hidden) == json.loads(text)  # an ordinary parser sees no difference
    got = fm.check_run_root(run)
    assert got["ok"] is False and "malformed" in got["detail"]


@pytest.mark.parametrize(
    "edit_root",
    [
        lambda r: r.update(notes=SECRET),
        lambda r: r["leaves"][0].update(note=SECRET),
        lambda r: [leaf.update(value="mntclfs") for leaf in r["leaves"] if leaf["type"] == "method_manifest_digest"],
        lambda r: r["leaves"].append({"type": "extra_leaf", "value": "0" * 64}),
        lambda r: r.update(leaves=[leaf for leaf in r["leaves"] if leaf["type"] != "method_manifest_digest"]),
        lambda r: r.update(leaves=[leaf for leaf in r["leaves"] if leaf["type"] != "intent_digest"]),
    ],
)
def test_the_root_file_itself_must_have_the_exact_public_shape(run_dir, tmp_path, edit_root):
    run = _resealed(_copy(run_dir, tmp_path), edit_root=edit_root)
    assert fm.check_run_root(run)["ok"] is False


@pytest.mark.parametrize("schema", [2, "2", "2.0.0-x", "02.0.0", "3.0.0", "", None, "two"])
def test_unknown_manifest_schema_is_refused(run_dir, tmp_path, schema):
    run = _resealed(_copy(run_dir, tmp_path), edit_manifest=lambda m: m.update(schema_version=schema))
    got = fm.check_run_root(run)
    assert got["ok"] is False and got["manifest_public_shape"] is False


def _public_without_digests(manifest: dict) -> dict:
    m = json.loads(json.dumps(manifest))
    for key in ("intent_digest", "intent_commitment", "method_manifest_digest"):
        m.pop(key)
    m["output"].pop("geometry_digest")
    return m


def test_public_manifest_does_not_depend_on_the_intents_letters(tmp_path):
    """Same options, very different intents: only the digests may differ.

    A vowel-only intent has no monogram or bind-rune, which used to show as a
    different channel status in the public file.
    """
    manifests = []
    for i, intent in enumerate(
        ["I maintain calm focus", "aeiou aeiou", "A", "Zzz zzz zzz zzz zzz zzz zzz zzz", "I keep my word"]
    ):
        packet = construct_run(intent, out_root=tmp_path / str(i), square="mars")
        run = Path(packet["artifacts"]["run_dir"])
        manifests.append(json.loads((run / fm.PUBLIC_NAME).read_text(encoding="utf-8")))
        assert fm.check_run_root(run)["manifest_public_shape"] is True
    first = _public_without_digests(manifests[0])
    for other in manifests[1:]:
        assert _public_without_digests(other) == first


def test_letter_channels_are_masked_in_public_and_kept_in_private(run_dir):
    public = json.loads((run_dir / fm.PUBLIC_NAME).read_text(encoding="utf-8"))
    private = json.loads((run_dir / fm.METHOD_NAME).read_text(encoding="utf-8"))
    statuses = {c["id"]: c["status"] for c in public["channels"]}
    for cid in fm.LETTER_CHANNELS:
        assert statuses[cid] == "private"
    assert statuses["intent_digest"] == "applied"
    real = {c["id"]: c["status"] for c in private["channels"]}
    assert real["spare_monogram"] == "applied"


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"mode": "practice"},
        {"kamea_encoding": "latin_mod9_v1"},
        {"kamea_encoding": "latin_extended"},
        {"spare_mode": "pictorial"},
        {"spare_mode": "phonetic_mantric"},
        {"square": "venus"},
        {"write_polish": True},
        {"passphrase": "p", "proof": "commitment"},
        {"passphrase": "p", "seal_packet": True},
    ],
)
def test_every_real_run_has_the_public_shape(tmp_path, options):
    """The strict check must accept everything the engine itself writes."""
    packet = construct_run(INTENT, out_root=tmp_path, **options)
    got = fm.check_run_root(Path(packet["artifacts"]["run_dir"]))
    assert got["ok"] is True and got["manifest_public_shape"] is True, got["detail"]
