"""Optional Noir proof provider (nargo + bb). Core forge does not require Noir.

When both tools are available, proves knowledge of (intent, nonce) such that
SHA-256(nonce || padded_intent) == public intent_commitment_zk.

Flow (Noir 1.x): ``nargo execute`` solves the witness, ``bb prove`` makes the
proof, ``bb verify`` checks it. Proving and verification left ``nargo`` in the
1.0 betas, so this provider needs Barretenberg's ``bb`` as well.

Every call works in a private temporary copy of the circuit. Nothing is written
to the installed skill tree, and the witness (plaintext intent and commitment
nonce) is deleted with that copy on success and on failure.

``verify`` never trusts a verification key that travelled with the proof: it
rebuilds the key from this install's circuit, builds the public inputs from the
commitment and intent length it was asked about, and checks the exact proof
file it was handed. Tool output is never copied into a result, because nargo
can print witness values.

Circuit lives under zk/noir/intent_commitment/. Tested with nargo 1.0.0 and
bb 6.0.0. The first proof on a machine makes bb download its reference string
to ``~/.bb-crs``; that is the only network use.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sigil_forge.paths import skill_root
from sigil_forge.proofs.base import ProofResult
from sigil_forge.proofs.zk_commit import MAX_INTENT_BYTES, pad_intent, zk_commit

PACKAGE = "intent_commitment"
# Proof flavour. Stated explicitly so prove, write_vk and verify always agree
# and a change of bb's default cannot silently split them.
VERIFIER_TARGET = "evm"
_HEX64 = re.compile(r"[0-9a-fA-F]{64}")
# Where the upstream installers (noirup, bbup) put the tools.
_STANDARD_DIRS = {"nargo": (".nargo", "bin"), "bb": (".bb",)}


def _tool(name: str) -> str | None:
    """Path of ``nargo`` or ``bb``: PATH first, then the installer's own directory."""
    found = shutil.which(name)
    if found:
        return found
    candidate = Path.home().joinpath(*_STANDARD_DIRS[name], name)
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def public_inputs_bytes(commitment_hex: str, intent_len: int) -> bytes:
    """The circuit's public inputs as bb reads them: 33 big-endian 32-byte fields.

    First the intent length, then one field per commitment byte.
    """
    if not isinstance(commitment_hex, str) or not _HEX64.fullmatch(commitment_hex):
        raise ValueError("intent_commitment_zk must be 64 hex characters")
    if isinstance(intent_len, bool) or not isinstance(intent_len, int):
        raise ValueError("intent_len must be an integer")
    if not 1 <= intent_len <= MAX_INTENT_BYTES:
        raise ValueError(f"intent_len must be 1..{MAX_INTENT_BYTES}")
    return intent_len.to_bytes(32, "big") + b"".join(
        bytes(31) + bytes([b]) for b in bytes.fromhex(commitment_hex)
    )


class NoirProvider:
    name = "noir"
    circuit_version = "2"

    def available(self) -> bool:
        return self._tools() is not None

    def _tools(self) -> tuple[str, str] | None:
        """(nargo, bb) when both exist and the circuit is installed, else None."""
        nargo, bb = _tool("nargo"), _tool("bb")
        if nargo is None or bb is None:
            return None
        if not (self._circuit_dir() / "Nargo.toml").is_file():
            return None
        return nargo, bb

    def _circuit_dir(self) -> Path:
        return skill_root() / "zk" / "noir" / "intent_commitment"

    def _workdir(self) -> Path:
        """A private (0700) copy of the circuit sources: manifest and src/ only."""
        circuit = self._circuit_dir()
        work = Path(tempfile.mkdtemp(prefix="sigil-forge-noir-"))
        try:
            shutil.copyfile(circuit / "Nargo.toml", work / "Nargo.toml")
            shutil.copytree(circuit / "src", work / "src")
        except BaseException:
            shutil.rmtree(work, ignore_errors=True)
            raise
        return work

    @staticmethod
    def _run(argv: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False
        )

    def _result(self, status: str, public_inputs: dict[str, Any], detail: str) -> ProofResult:
        return ProofResult(
            provider=self.name,
            proof_kind="zk_knowledge",
            status=status,
            public_inputs=dict(public_inputs),
            detail=detail,
            circuit_version=self.circuit_version,
        )

    def prove(
        self,
        witness: dict[str, Any],
        public_inputs: dict[str, Any],
        *,
        out_dir: Path | str,
    ) -> ProofResult:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        tools = self._tools()
        if tools is None:
            return self._result("skipped", public_inputs, "noir_unavailable")
        nargo, bb = tools
        normalized = witness.get("normalized_intent") or ""
        nonce = witness.get("nonce")
        if not isinstance(nonce, (bytes, bytearray)) or not normalized:
            return self._result(
                "failed", public_inputs, "witness missing normalized_intent or nonce bytes"
            )
        try:
            c_zk = zk_commit(normalized, bytes(nonce))
            padded, intent_len = pad_intent(normalized)
            if 0 in padded[:intent_len]:
                # The circuit binds the length by requiring non-zero intent bytes.
                raise ValueError("intent contains a NUL byte; not provable by this circuit")
            expected_inputs = public_inputs_bytes(str(c_zk["value"]), intent_len)
        except ValueError as exc:
            return self._result("failed", public_inputs, str(exc))

        proof_dst = out / "intent-proof.bin"
        vk_dst = out / "intent-proof.vk"
        # A failed run must not leave an earlier run's proof looking current.
        for stale in (proof_dst, vk_dst):
            stale.unlink(missing_ok=True)
        work: Path | None = None
        try:
            work = self._workdir()
            # The witness is the plaintext intent and the commitment nonce:
            # owner-only, exclusive create, inside the private work directory.
            fd = os.open(
                work / "Prover.toml",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(
                    f'intent_len = "{intent_len}"\n'
                    f"intent_bytes = [{', '.join(str(b) for b in padded)}]\n"
                    f"nonce = [{', '.join(str(b) for b in nonce)}]\n"
                    f"expected_commitment = [{', '.join(str(b) for b in bytes.fromhex(str(c_zk['value'])))}]\n"
                )
            execute = self._run([nargo, "execute"], work, 300)
            if execute.returncode != 0:
                # nargo can print witness values when the inputs do not fit the
                # circuit, so its output is never copied into the result.
                return self._result(
                    "failed", public_inputs, f"nargo execute failed (exit {execute.returncode})"
                )
            target = work / "target"
            prove = self._run(
                [
                    bb, "prove",
                    "-b", str(target / f"{PACKAGE}.json"),
                    "-w", str(target / f"{PACKAGE}.gz"),
                    "-o", str(work / "out"),
                    "-t", VERIFIER_TARGET,
                    "--write_vk",
                ],
                work,
                600,
            )
            if prove.returncode != 0:
                return self._result(
                    "failed", public_inputs, f"bb prove failed (exit {prove.returncode})"
                )
            produced = work / "out"
            try:
                proof = (produced / "proof").read_bytes()
                vk = (produced / "vk").read_bytes()
                got_inputs = (produced / "public_inputs").read_bytes()
            except OSError:
                return self._result(
                    "failed", public_inputs, "bb prove did not write proof, vk and public_inputs"
                )
            if got_inputs != expected_inputs:
                return self._result(
                    "failed", public_inputs, "bb public inputs do not match the commitment"
                )
            proof_dst.write_bytes(proof)
            vk_dst.write_bytes(vk)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return self._result(
                "failed", public_inputs, f"noir toolchain error: {type(exc).__name__}"
            )
        finally:
            if work is not None:
                shutil.rmtree(work, ignore_errors=True)

        pi = dict(public_inputs)
        pi["intent_commitment_zk"] = c_zk["value"]
        pi["intent_len"] = intent_len
        return ProofResult(
            provider=self.name,
            proof_kind="zk_knowledge",
            status="generated",
            public_inputs=pi,
            proof_path=str(proof_dst),
            verification_key_digest=hashlib.sha256(vk).hexdigest(),
            circuit_version=self.circuit_version,
            detail=f"noir proof generated (ultra_honk, target {VERIFIER_TARGET})",
            intent_disclosed=False,
        )

    def verify(
        self,
        proof_path: Any,
        public_inputs: dict[str, Any],
        *,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        tools = self._tools()
        if proof_path is None or tools is None:
            return False
        nargo, bb = tools
        try:
            proof = Path(proof_path)
            if not proof.is_file():
                return False
            claimed = public_inputs or {}
            inputs = public_inputs_bytes(
                claimed.get("intent_commitment_zk"), claimed.get("intent_len")
            )
        except (OSError, ValueError, TypeError):
            return False
        work: Path | None = None
        try:
            work = self._workdir()
            # Rebuild the verification key from this install's circuit. A key
            # supplied next to the proof could belong to any circuit.
            if self._run([nargo, "compile"], work, 300).returncode != 0:
                return False
            write_vk = self._run(
                [
                    bb, "write_vk",
                    "-b", str(work / "target" / f"{PACKAGE}.json"),
                    "-o", str(work / "vk"),
                    "-t", VERIFIER_TARGET,
                ],
                work,
                300,
            )
            if write_vk.returncode != 0:
                return False
            inputs_path = work / "public_inputs"
            inputs_path.write_bytes(inputs)
            proc = self._run(
                [
                    bb, "verify",
                    "-k", str(work / "vk" / "vk"),
                    "-p", str(proof.resolve()),
                    "-i", str(inputs_path),
                    "-t", VERIFIER_TARGET,
                ],
                work,
                300,
            )
            return proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
        finally:
            if work is not None:
                shutil.rmtree(work, ignore_errors=True)
