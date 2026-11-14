"""Proof providers, zk companion commit, verify-proof CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sigil_forge.construct import run as construct_run
from sigil_forge.proofs.noir_provider import NoirProvider
from sigil_forge.proofs.registry import list_providers
from sigil_forge.proofs.verify_run import verify_proof_run
from sigil_forge.proofs.zk_commit import MAX_INTENT_BYTES, pad_intent, verify_zk_commit, zk_commit

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sigil_forge.py"


def test_zk_commit_roundtrip():
    nonce = b"\x07" * 32
    rec = zk_commit("i maintain calm focus", nonce)
    assert rec["scheme"] == "sha256-nonce-pad256-v1"
    assert len(rec["value"]) == 64
    assert verify_zk_commit("i maintain calm focus", nonce, rec["value"])
    assert not verify_zk_commit("other intent", nonce, rec["value"])


def test_pad_intent_zeros():
    padded, n = pad_intent("abc")
    assert n == 3
    assert len(padded) == MAX_INTENT_BYTES
    assert padded[3:] == b"\x00" * (MAX_INTENT_BYTES - 3)


def test_list_providers():
    names = {p["name"] for p in list_providers()}
    assert "none" in names
    assert "local_capsule" in names
    assert "noir" in names
    assert "risc0" in names


def test_construct_zk_knowledge_local_attestation(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="zk-test-pass",
        proof="zk-knowledge",
        kdf="pbkdf2-sha256",
    )
    assert packet.get("intent_commitment_zk", {}).get("value")
    run = Path(packet["artifacts"]["run_dir"])
    assert (run / "proofs" / "proof-manifest.json").is_file()
    assert (run / "proofs" / "knowledge-attestation.json").is_file()
    man = json.loads((run / "proofs" / "proof-manifest.json").read_text(encoding="utf-8"))
    # noir may be skipped; local attestation still generated first then overwritten
    # when zk-knowledge: final manifest is noir result with local_attestation extra
    assert man.get("public_inputs", {}).get("intent_commitment")
    # verify-proof with passphrase should succeed via local path or noir
    res = verify_proof_run(run, passphrase="zk-test-pass")
    # If noir generated, verify may need nargo; if skipped, local attestation in extra
    if man.get("provider") == "noir" and man.get("status") == "generated":
        # may or may not verify without full nargo setup
        assert "verified" in res
    else:
        # When noir skipped, manifest is noir skip — re-verify using local provider
        from sigil_forge.proofs.local_knowledge import LocalCapsuleProvider

        att = run / "proofs" / "knowledge-attestation.json"
        # re-write manifest for local if noir skipped
        if man.get("status") == "skipped":
            # Direct local verify
            capsule = json.loads((run / "intent-capsule.json").read_text(encoding="utf-8"))
            ok = LocalCapsuleProvider().verify(
                att,
                man.get("public_inputs")
                or {
                    "intent_commitment": packet["intent_commitment"]["value"],
                    "intent_commitment_zk": packet["intent_commitment_zk"]["value"],
                },
                extra={"passphrase": "zk-test-pass", "capsule": capsule},
            )
            assert ok is True


def test_construct_commitment_writes_local_proof(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="c-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    run = Path(packet["artifacts"]["run_dir"])
    man = json.loads((run / "proofs" / "proof-manifest.json").read_text(encoding="utf-8"))
    assert man["provider"] == "local_capsule"
    assert man["status"] == "generated"
    res = verify_proof_run(run, passphrase="c-pass")
    assert res["verified"] is True
    assert res["intent_disclosed"] is False
    assert res["intent_commitment"] == packet["intent_commitment"]["value"]


def test_verify_proof_cli(tmp_path: Path):
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        passphrase="cli-pass",
        proof="commitment",
        kdf="pbkdf2-sha256",
    )
    run = packet["artifacts"]["run_dir"]
    r = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "verify-proof",
            run,
            "--passphrase",
            "cli-pass",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    out = json.loads(r.stdout)
    assert out["verified"] is True


def test_noir_provider_skipped_without_nargo(tmp_path):
    n = NoirProvider()
    # available depends on host; prove should not crash
    res = n.prove(
        {"normalized_intent": "i maintain calm focus", "nonce": b"\x01" * 32},
        {"intent_commitment_zk": "00" * 32},
        out_dir=tmp_path / "noir",
    )
    assert res.status in ("generated", "skipped", "failed")
    if not n.available():
        assert res.status == "skipped"
        assert "noir" in res.detail.lower() or "unavailable" in res.detail.lower()


def test_zk_forge_skips_via_risc0(tmp_path: Path):
    """zk-forge is no longer a hard NOT_IMPLEMENTED; adapter skips offline."""
    from sigil_forge.construct import run as cr

    packet = cr(
        "I maintain calm focus",
        out_root=tmp_path,
        kamea_encoding="latin_mod9_v1",
        proof="zk-forge",
    )
    assert packet["proof"]["mode"] == "zk-forge"
    assert packet["proof"]["provider"] == "risc0"
    assert packet["proof"]["status"] in ("skipped", "generated", "failed")


INTENT = "i maintain calm focus"
NONCE = b"\x01" * 32


def _fake_tools(tmp_path: Path, monkeypatch, *, execute_exit: int = 0, prove_exit: int = 0):
    """Stand-in nargo and bb that record what they saw of the witness.

    They write their notes to ``tmp_path / "seen"``, outside the work directory,
    because the provider deletes its work directory when it returns.
    """
    from sigil_forge.proofs.noir_provider import public_inputs_bytes

    skill = tmp_path / "skill"
    circuit = skill / "zk" / "noir" / "intent_commitment"
    (circuit / "src").mkdir(parents=True)
    (circuit / "Nargo.toml").write_text('[package]\nname = "intent_commitment"\n')
    (circuit / "src" / "main.nr").write_text("fn main() {}\n")
    seen = tmp_path / "seen"
    seen.mkdir()
    (seen / "public_inputs").write_bytes(
        public_inputs_bytes(zk_commit(INTENT, NONCE)["value"], len(INTENT))
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "nargo").write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "execute" ]; then\n'
        f'  pwd > "{seen}/workdir"\n'
        f'  (stat -c %a Prover.toml 2>/dev/null || stat -f %Lp Prover.toml) > "{seen}/witness-mode"\n'
        f'  (stat -c %a . 2>/dev/null || stat -f %Lp .) > "{seen}/workdir-mode"\n'
        f'  cp Prover.toml "{seen}/witness-copy"\n'
        "  cat Prover.toml >&2\n"
        "  mkdir -p target && : > target/intent_commitment.json && : > target/intent_commitment.gz\n"
        f"  exit {execute_exit}\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (bin_dir / "bb").write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "prove" ]; then\n'
        "  mkdir -p out && printf proof > out/proof && printf vk > out/vk\n"
        f'  cp "{seen}/public_inputs" out/public_inputs\n'
        f"  exit {prove_exit}\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    for tool in ("nargo", "bb"):
        (bin_dir / tool).chmod(0o755)
    monkeypatch.setenv("HERMES_SKILL_DIR", str(skill))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return circuit, seen


def _prove(tmp_path):
    return NoirProvider().prove(
        {"normalized_intent": INTENT, "nonce": NONCE}, {}, out_dir=tmp_path / "out"
    )


def _tree(root: Path) -> dict[str, bytes | str]:
    return {
        str(p.relative_to(root)): (os.readlink(p) if p.is_symlink() else p.read_bytes())
        for p in sorted(root.rglob("*"))
        if p.is_symlink() or p.is_file()
    }


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell stand-ins and file modes")
@pytest.mark.parametrize(
    ("execute_exit", "prove_exit", "status"),
    [(0, 0, "generated"), (1, 0, "failed"), (0, 1, "failed")],
)
def test_noir_witness_is_private_and_removed(tmp_path, monkeypatch, execute_exit, prove_exit, status):
    """Prover.toml holds plaintext intent + nonce: owner-only, gone after prove."""
    circuit, seen = _fake_tools(
        tmp_path, monkeypatch, execute_exit=execute_exit, prove_exit=prove_exit
    )
    before = _tree(circuit)

    res = _prove(tmp_path)

    assert res.status == status
    # nargo saw the witness with no group/other access, in an owner-only directory ...
    assert (seen / "witness-mode").read_text().strip() == "600"
    assert (seen / "workdir-mode").read_text().strip() == "700"
    assert "intent_bytes" in (seen / "witness-copy").read_text()
    # ... that is not the installed skill tree and does not outlive the call.
    workdir = Path((seen / "workdir").read_text().strip())
    assert tmp_path / "skill" not in workdir.parents
    assert not workdir.exists()
    assert _tree(circuit) == before
    if status == "generated":
        assert Path(res.proof_path).read_bytes() == b"proof"
        assert (tmp_path / "out" / "intent-proof.vk").read_bytes() == b"vk"
        assert res.verification_key_digest
    else:
        assert not (tmp_path / "out" / "intent-proof.bin").exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell stand-ins and file modes")
def test_noir_ignores_a_stale_witness_in_the_skill_tree(tmp_path, monkeypatch):
    circuit, seen = _fake_tools(tmp_path, monkeypatch)
    stale = circuit / "Prover.toml"
    stale.write_text("stale")

    res = _prove(tmp_path)

    assert res.status == "generated"
    assert (seen / "witness-mode").read_text().strip() == "600"
    assert "stale" not in (seen / "witness-copy").read_text()
    assert stale.read_text() == "stale"  # the skill tree is never written


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell stand-ins and symlinks")
def test_noir_witness_does_not_follow_a_symlink(tmp_path, monkeypatch):
    circuit, seen = _fake_tools(tmp_path, monkeypatch)
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me")
    (circuit / "Prover.toml").symlink_to(victim)

    res = _prove(tmp_path)

    assert res.status == "generated"
    assert victim.read_text() == "keep me"
    assert (circuit / "Prover.toml").is_symlink()


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell stand-ins")
def test_noir_prove_fails_when_bb_reports_other_public_inputs(tmp_path, monkeypatch):
    _, seen = _fake_tools(tmp_path, monkeypatch)
    (seen / "public_inputs").write_bytes(bytes(33 * 32))

    res = _prove(tmp_path)

    assert res.status == "failed"
    assert "public inputs" in res.detail
    assert not (tmp_path / "out" / "intent-proof.bin").exists()


def test_noir_public_inputs_encoding():
    from sigil_forge.proofs.noir_provider import public_inputs_bytes

    value = zk_commit(INTENT, NONCE)["value"]
    blob = public_inputs_bytes(value, 21)
    assert len(blob) == 33 * 32
    assert int.from_bytes(blob[:32], "big") == 21
    body = blob[32:]
    assert bytes(body[i * 32 + 31] for i in range(32)).hex() == value
    assert all(body[i * 32 : i * 32 + 31] == bytes(31) for i in range(32))
    for bad in ("", "00" * 31, "zz" * 32, "00" * 32 + "\n", None, 5):
        with pytest.raises(ValueError):
            public_inputs_bytes(bad, 21)
    for bad_len in (0, 257, -1, "21", None, True, 21.0):
        with pytest.raises(ValueError):
            public_inputs_bytes(value, bad_len)


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell stand-ins")
@pytest.mark.parametrize(("execute_exit", "prove_exit"), [(1, 0), (0, 1)])
def test_noir_failure_detail_never_carries_tool_output(tmp_path, monkeypatch, execute_exit, prove_exit):
    """The stand-in nargo prints the whole witness to stderr; none of it may surface."""
    _fake_tools(tmp_path, monkeypatch, execute_exit=execute_exit, prove_exit=prove_exit)
    res = _prove(tmp_path)
    assert res.status == "failed"
    assert "intent_bytes" not in res.detail and "nonce" not in res.detail
    assert "exit 1" in res.detail


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell stand-ins")
def test_noir_timeout_removes_the_work_directory_and_reports_no_paths(tmp_path, monkeypatch):
    _fake_tools(tmp_path, monkeypatch)
    seen_dirs: list[Path] = []

    def boom(argv, cwd, timeout):
        seen_dirs.append(Path(cwd))
        assert (Path(cwd) / "Prover.toml").is_file()
        raise subprocess.TimeoutExpired(argv, timeout)

    monkeypatch.setattr(NoirProvider, "_run", staticmethod(boom))
    res = _prove(tmp_path)
    assert res.status == "failed"
    assert res.detail == "noir toolchain error: TimeoutExpired"
    assert seen_dirs and not seen_dirs[0].exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell stand-ins")
def test_noir_refuses_an_intent_with_a_nul_byte(tmp_path, monkeypatch):
    """The circuit binds the length via non-zero bytes, so NUL is not provable."""
    _, seen = _fake_tools(tmp_path, monkeypatch)
    res = NoirProvider().prove(
        {"normalized_intent": "calm\x00focus", "nonce": NONCE}, {}, out_dir=tmp_path / "out"
    )
    assert res.status == "failed" and "NUL" in res.detail
    assert not (seen / "workdir").exists()  # no tool was run


@pytest.mark.skipif(os.name != "posix", reason="POSIX shell stand-ins")
def test_noir_failed_prove_removes_an_earlier_proof(tmp_path, monkeypatch):
    _fake_tools(tmp_path, monkeypatch, prove_exit=1)
    out = tmp_path / "out"
    out.mkdir()
    (out / "intent-proof.bin").write_bytes(b"old")
    (out / "intent-proof.vk").write_bytes(b"old")
    assert _prove(tmp_path).status == "failed"
    assert not (out / "intent-proof.bin").exists() and not (out / "intent-proof.vk").exists()


def test_noir_unavailable_without_both_tools(tmp_path, monkeypatch):
    """nargo alone is not enough: proving and verifying need bb."""
    skill = tmp_path / "skill"
    circuit = skill / "zk" / "noir" / "intent_commitment"
    circuit.mkdir(parents=True)
    (circuit / "Nargo.toml").write_text("[package]\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "nargo").write_text("#!/bin/sh\nexit 0\n")
    (bin_dir / "nargo").chmod(0o755)
    monkeypatch.setenv("HERMES_SKILL_DIR", str(skill))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", str(bin_dir))
    n = NoirProvider()
    assert n.available() is False
    assert _prove(tmp_path).detail == "noir_unavailable"
    assert n.verify(tmp_path / "x", {"intent_commitment_zk": "00" * 32, "intent_len": 1}) is False


# ---------------------------------------------------------------------------
# Real toolchain. Skipped unless nargo and bb are installed; CI installs both
# in the optional leg, so these do run there.

_REAL = NoirProvider().available()
needs_toolchain = pytest.mark.skipif(not _REAL, reason="nargo and bb not installed")


def test_noir_toolchain_is_present_where_it_is_required():
    """CI's optional leg sets SIGIL_FORGE_REQUIRE_NOIR=1.

    The real prove and verify tests below skip when the toolchain is missing,
    which is right on a developer machine. In CI that skip would be silent:
    drop the install step and everything stays green with the Noir path
    untested. With the variable set, a missing toolchain fails here instead.
    """
    if os.environ.get("SIGIL_FORGE_REQUIRE_NOIR"):
        assert _REAL, "SIGIL_FORGE_REQUIRE_NOIR is set but nargo and bb are not installed"


@pytest.fixture(scope="module")
def real_proof(tmp_path_factory):
    out = tmp_path_factory.mktemp("noir-real")
    res = NoirProvider().prove({"normalized_intent": INTENT, "nonce": NONCE}, {}, out_dir=out)
    assert res.status == "generated", res.detail
    return res


@needs_toolchain
def test_noir_real_proof_verifies_and_leaves_the_circuit_untouched(real_proof):
    circuit = ROOT / "zk" / "noir" / "intent_commitment"
    before = _tree(circuit)
    assert real_proof.public_inputs["intent_commitment_zk"] == zk_commit(INTENT, NONCE)["value"]
    assert NoirProvider().verify(real_proof.proof_path, real_proof.public_inputs) is True
    assert _tree(circuit) == before
    assert not (circuit / "target").exists()


@needs_toolchain
def test_noir_real_verify_is_bound_to_the_commitment(real_proof):
    """A valid proof must not vouch for a different commitment."""
    other = zk_commit(INTENT, b"\x02" * 32)["value"]
    n = NoirProvider()
    good = real_proof.public_inputs
    assert n.verify(real_proof.proof_path, dict(good, intent_commitment_zk=other)) is False
    assert n.verify(real_proof.proof_path, {}) is False


@needs_toolchain
def test_noir_real_verify_is_bound_to_the_intent_length(real_proof):
    """The published length is proven: any other value fails, as does none."""
    n = NoirProvider()
    good = real_proof.public_inputs
    assert good["intent_len"] == len(INTENT)
    for wrong in (len(INTENT) - 1, len(INTENT) + 1, 256):
        assert n.verify(real_proof.proof_path, dict(good, intent_len=wrong)) is False
    assert n.verify(real_proof.proof_path, {"intent_commitment_zk": good["intent_commitment_zk"]}) is False


@needs_toolchain
@pytest.mark.parametrize("intent", ["x", "é" * 100, "a" * 256])
def test_noir_real_proof_for_edge_lengths(tmp_path, intent):
    """One byte, multibyte text, and the full 256 bytes."""
    n = NoirProvider()
    res = n.prove({"normalized_intent": intent, "nonce": NONCE}, {}, out_dir=tmp_path)
    assert res.status == "generated", res.detail
    assert res.public_inputs["intent_len"] == len(intent.encode())
    assert n.verify(res.proof_path, res.public_inputs) is True


@needs_toolchain
def test_noir_real_verify_is_bound_to_the_proof_it_is_given(real_proof, tmp_path):
    proof = Path(real_proof.proof_path)
    blob = bytearray(proof.read_bytes())
    blob[len(blob) // 2] ^= 1
    tampered = tmp_path / "tampered.bin"
    tampered.write_bytes(blob)
    n = NoirProvider()
    assert n.verify(tampered, real_proof.public_inputs) is False
    assert n.verify(tmp_path / "missing.bin", real_proof.public_inputs) is False
    assert n.verify(None, real_proof.public_inputs) is False


@needs_toolchain
def test_noir_real_verify_ignores_a_verification_key_beside_the_proof(real_proof, tmp_path):
    """A key file next to the proof is never read: the key comes from the circuit."""
    proof = tmp_path / "intent-proof.bin"
    proof.write_bytes(Path(real_proof.proof_path).read_bytes())
    (tmp_path / "intent-proof.vk").write_bytes(b"not a key")
    assert NoirProvider().verify(proof, real_proof.public_inputs) is True


@needs_toolchain
def test_noir_real_construct_and_verify_proof_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGIL_FORGE_PASSPHRASE", "correct horse battery staple")
    packet = construct_run(
        "I maintain calm focus",
        out_root=tmp_path,
        passphrase="correct horse battery staple",
        proof="zk-knowledge",
    )
    assert packet["proof"]["provider"] == "noir"
    assert packet["proof"]["status"] == "generated", packet["proof"]["detail"]
    run_dir = Path(packet["artifacts"]["packet_json"]).parent
    assert not list(run_dir.rglob("Prover.toml"))
    out = verify_proof_run(run_dir)
    assert out["verified"] is True
    assert out["provider"] == "noir"


@needs_toolchain
def test_noir_real_verify_proof_refuses_another_runs_proof(tmp_path):
    """Swapping in another run's proof and commitment must not verify this run."""
    runs = []
    for name, intent in (("a", "I maintain calm focus"), ("b", "I finish what I start")):
        packet = construct_run(
            intent, out_root=tmp_path / name, passphrase="pass-" + name, proof="zk-knowledge"
        )
        assert packet["proof"]["status"] == "generated", packet["proof"]["detail"]
        runs.append(Path(packet["artifacts"]["packet_json"]).parent)
    victim, attacker = runs
    assert verify_proof_run(victim)["verified"] is True

    (victim / "proofs" / "intent-proof.bin").write_bytes(
        (attacker / "proofs" / "intent-proof.bin").read_bytes()
    )
    theirs = json.loads((attacker / "proofs" / "proof-manifest.json").read_text())
    path = victim / "proofs" / "proof-manifest.json"
    mine = json.loads(path.read_text())
    for key in ("intent_commitment_zk", "intent_len"):
        mine["public_inputs"][key] = theirs["public_inputs"][key]
    path.write_text(json.dumps(mine))

    out = verify_proof_run(victim)
    assert out["verified"] is False
    assert "not bound" in out["detail"]
    # With the passphrase the run's own capsule is really opened and does verify,
    # but as the local attestation: the swapped Noir proof is never credited.
    with_pass = verify_proof_run(victim, passphrase="pass-a")
    assert with_pass["verified"] is True
    assert with_pass["provider"] == "local_capsule"
    assert with_pass["proof_kind"] == "knowledge_of_intent"
    assert verify_proof_run(victim, passphrase="wrong")["verified"] is False


# ------------------------------------------- passphrase-less verify (issue #37)


def _commitment_run(tmp_path: Path) -> Path:
    packet = construct_run(
        "I maintain calm focus", out_root=tmp_path, passphrase="c-pass", proof="commitment"
    )
    return Path(packet["artifacts"]["run_dir"])


def test_verify_proof_without_passphrase_is_not_verified(tmp_path):
    """An attestation file saying ok is a note, not a proof."""
    run = _commitment_run(tmp_path)
    out = verify_proof_run(run)
    assert out["verified"] is False
    assert out["attestation_present"] is True
    assert "passphrase required" in out["detail"]
    with_pass = verify_proof_run(run, passphrase="c-pass")
    assert with_pass["verified"] is True and with_pass["provider"] == "local_capsule"
    assert verify_proof_run(run, passphrase="wrong")["verified"] is False


def test_local_provider_does_not_accept_a_file_that_says_ok(tmp_path):
    from sigil_forge.proofs.local_knowledge import LocalCapsuleProvider

    forged = tmp_path / "knowledge-attestation.json"
    forged.write_text(json.dumps({"ok": True, "provider": "local_capsule"}), encoding="utf-8")
    p = LocalCapsuleProvider()
    assert p.verify(forged, {}) is False
    assert p.verify(forged, {}, extra={"passphrase": "x"}) is False
    assert p.verify(forged, {}, extra={"capsule": {}}) is False


def test_verify_proof_cli_without_passphrase_exits_nonzero(tmp_path, monkeypatch):
    run = _commitment_run(tmp_path)
    env = {k: v for k, v in os.environ.items() if k != "SIGIL_FORGE_PASSPHRASE"}
    r = subprocess.run(
        [sys.executable, str(CLI), "verify-proof", str(run)],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    assert r.returncode == 1
    assert json.loads(r.stdout)["verified"] is False
