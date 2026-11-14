"""Full construct pipeline: safety → normalize → digest → fuse → stego → packet."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from sigil_forge.artifact_root import build_sigil_root
from sigil_forge.commitment import commit_intent, public_commitment
from sigil_forge.crypto_payload import seal_intent
from sigil_forge.forge_core import ForgeConfig, compute_forge
from sigil_forge.forge_manifest import (
    METHOD_NAME,
    build_forge_manifest,
    build_method_manifest,
    write_manifest,
    write_private_manifest,
)
from sigil_forge.phonetic import build_phonetic_artifact
from sigil_forge.intent_capsule import build_capsule, ciphertext_digest
from sigil_forge.normalize import normalize_intent
from sigil_forge.ontology import assert_not_entity_seal_request, default_packet_ontology
from sigil_forge.packet import build_packet, validate_packet, write_packet_files
from sigil_forge.paths import (
    default_out_dir,
    ensure_private_dir,
    make_run_id,
    run_dir as make_run_dir,
    skill_root,
    write_private_text,
)
from sigil_forge.safety import check_intent
from sigil_forge.stego_png import embed_lsb, pack_payload
from sigil_forge.stego_svg import embed as stego_svg_embed
from sigil_forge.svg_export import layout_to_svg
from sigil_forge.wallpaper.seed import file_sha256

# Env passphrase avoids argv exposure (process list / shell history).
PASSPHRASE_ENV = "SIGIL_FORGE_PASSPHRASE"


def resolve_passphrase(explicit: str | None = None) -> str | None:
    """CLI/explicit passphrase wins; else ``SIGIL_FORGE_PASSPHRASE`` env."""
    if explicit is not None and str(explicit) != "":
        return str(explicit)
    env = os.environ.get(PASSPHRASE_ENV)
    if env is not None and env != "":
        return env
    return None

SCHEMA_VERSION = "1.2"

_CHANNEL_ORDER = (
    "spare_monogram",
    "kamea_path",
    "kamea_square_choice",
    "bind_runes",
    "rose_cross_path",
    "planetary_seal",
    "intent_digest",
    "intent_commitment",
    "optional_ciphertext",
    "svg_metadata",
    "path_epsilon",
    "path_order",
    "metric_quantize",
    "png_lsb",
    "gen_seed",
    "phonetic_sigil",
)


def _ch(cid: str, status: str, detail: str) -> dict[str, str]:
    return {"id": cid, "status": status, "detail": detail}


# Phrase-scan threshold: short normalized intents skip substring scan (stego
# never embeds them; short strings false-positive against hex/coords/metadata).
_PRIVACY_PHRASE_MIN_LEN = 12
_PRIVACY_SPARE_MIN_LEN = 4


def _assert_svg_privacy(svg: str, *, normalized: str, spare: str) -> None:
    """Raise RuntimeError if public SVG appears to leak intent or spare letters.

    Short intents (len < 12) skip the phrase scan — stego path never embeds
    plaintext intent. Spare letter runs are checked when len >= 4.
    """
    svg_low = svg.lower()
    if len(normalized) >= _PRIVACY_PHRASE_MIN_LEN and normalized in svg_low:
        raise RuntimeError("public SVG leaked normalized intent")
    spare_low = (spare or "").lower()
    if len(spare_low) >= _PRIVACY_SPARE_MIN_LEN and spare_low in svg_low:
        raise RuntimeError("public SVG leaked spare letters")


def _merge_channels(
    craft: list[dict[str, str]],
    stego: list[dict[str, str]],
    extras: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for c in craft + stego + extras:
        by_id[c["id"]] = c
    ordered = [by_id[i] for i in _CHANNEL_ORDER if i in by_id]
    # Any unexpected ids after known order
    for cid, c in by_id.items():
        if cid not in _CHANNEL_ORDER:
            ordered.append(c)
    return ordered


def _try_png_lsb(
    svg: str,
    digest_hex: str,
    out_png: Path,
    *,
    monogram_points: list[tuple[float, float]] | None = None,
    kamea_points: list[tuple[float, float]] | None = None,
) -> tuple[str | None, dict[str, str]]:
    """Rasterize + LSB embed when possible; else skip with reason.

    Prefer stdlib layout raster (filter-0 RGB, always LSB-compatible). Fall
    back to optional SVG backends, re-encoding when needed.

    Public PNG payload is digest-only (``pack_payload(digest)``). Full seal
    blob stays in the local forge packet.
    """
    png_bytes: bytes | None = None
    source = "none"

    # 1. Stdlib layout geometry → filter-0 RGB PNG (Hermes offline default)
    if monogram_points is not None or kamea_points is not None:
        try:
            from sigil_forge.layout_raster import layout_to_png_bytes

            png_bytes = layout_to_png_bytes(
                monogram_points or [],
                kamea_points or [],
            )
            source = "layout_raster"
        except Exception:  # noqa: BLE001
            png_bytes = None

    # 2. Optional SVG raster backends
    if not png_bytes:
        try:
            from sigil_forge.raster_svg import svg_to_png_bytes

            png_bytes = svg_to_png_bytes(svg)
            source = "svg_backend" if png_bytes else "none"
        except Exception as exc:  # noqa: BLE001
            return None, _ch("png_lsb", "skipped", f"raster_error: {exc}")

    if not png_bytes:
        return None, _ch("png_lsb", "skipped", "no_raster_backend")

    # If backend PNG is not filter-0 RGB, re-encode via layout when available
    digest_raw = bytes.fromhex(digest_hex)
    payload = pack_payload(digest_raw)
    try:
        stego_png = embed_lsb(png_bytes, payload)
    except Exception:
        # Retry with pure layout raster if external PNG was incompatible
        if source != "layout_raster" and (
            monogram_points is not None or kamea_points is not None
        ):
            try:
                from sigil_forge.layout_raster import layout_to_png_bytes

                png_bytes = layout_to_png_bytes(
                    monogram_points or [],
                    kamea_points or [],
                )
                stego_png = embed_lsb(png_bytes, payload)
                source = "layout_raster_retry"
            except Exception as exc:  # noqa: BLE001
                return None, _ch("png_lsb", "skipped", f"embed_failed: {exc}")
        else:
            return None, _ch("png_lsb", "skipped", "embed_failed: incompatible_png")

    out_png.write_bytes(stego_png)
    return str(out_png), _ch(
        "png_lsb",
        "applied",
        f"LSB digest-only {len(payload)} bytes via {source}",
    )


def run(
    intent: str,
    *,
    mode: str = "creative",
    out_root: Path | str | None = None,
    passphrase: str | None = None,
    square: str | None = None,
    seal_packet: bool = False,
    write_polish: bool = False,
    polish_style: str | None = None,
    write_receipt: bool = True,
    kamea_encoding: str | None = None,
    spare_mode: str = "letter_monogram",
    planetary_seal: bool = False,
    planetary_seal_kind: str = "traditional_seal",
    planetary_geometry: str = "auto",
    prefer_argon2: bool = False,
    kdf: str | None = None,
    proof: str = "none",
    interop: bool = False,
    phonetic: bool = False,
) -> dict[str, Any]:
    """Orchestrate full forge: safety → normalize → digest → seal? → fuse → stego → packet.

    Writes under ``out_root/<run-id>/``:
      glyph.svg, glyph.png (when raster ok), forge-packet.json/md,
      run-receipt.json (default), optional polish_prompt.json when ``write_polish``,
      forge-manifest.json, optional intent-capsule.json (Proof of Intent).

    Returns the forge-packet dict. Raises ValueError on harmful/empty intent.
    """
    if mode not in ("creative", "practice"):
        raise ValueError(f"mode must be 'creative' or 'practice', got {mode!r}")

    proof_mode = (proof or "none").strip().lower()
    if proof_mode not in ("none", "commitment", "zk-knowledge", "zk-forge"):
        raise ValueError(f"unsupported proof mode: {proof!r}")
    # zk-forge: optional risc0/zkVM adapter; skips when toolchain/guest absent

    passphrase = resolve_passphrase(passphrase)
    if seal_packet and not passphrase:
        raise ValueError(
            "seal_packet=True requires passphrase "
            f"(--passphrase or ${PASSPHRASE_ENV})"
        )
    if proof_mode == "commitment" and not passphrase:
        raise ValueError(
            "proof=commitment requires passphrase for intent capsule "
            f"(--passphrase or ${PASSPHRASE_ENV})"
        )

    ok, reason = check_intent(intent)
    if not ok:
        raise ValueError(reason or "refused: harmful intent")
    assert_not_entity_seal_request(intent)

    # --- pure forge core (deterministic geometry; no FS / clock / random) ---
    normalized = normalize_intent(intent)
    core = compute_forge(
        normalized,
        ForgeConfig(
            mode=mode,
            square=square,
            kamea_encoding=kamea_encoding,
            spare_mode=spare_mode,
            planetary_seal=planetary_seal,
            planetary_seal_kind=planetary_seal_kind,
            planetary_geometry=planetary_geometry,
            phonetic=phonetic,
        ),
    )
    digest = core.intent_digest
    layout = core.layout
    spare = core.spare_letters
    square_name = core.square_name
    order = core.square_order
    enc = core.kamea_encoding

    # Privacy commitment (per-run nonce) — outside pure core; geometry uses digest
    commitment_rec = commit_intent(normalized)

    # KDF policy: explicit kdf wins; else prefer_argon2 → auto; else pbkdf2 default
    kdf_arg = kdf
    if kdf_arg is None and prefer_argon2:
        kdf_arg = "auto"
    prefer_for_seal = prefer_argon2 or (kdf_arg in ("auto", "argon2id") if kdf_arg else False)

    craft_channels: list[dict[str, str]] = []
    sealed_blob: dict[str, Any] | None = None

    # --- optional ciphertext (local packet only; not embedded in public PNG) ---
    if passphrase:
        sealed_blob = seal_intent(
            intent,
            passphrase,
            prefer_argon2=prefer_for_seal,
            kdf=kdf_arg,
        )
        craft_channels.append(
            _ch(
                "optional_ciphertext",
                "applied",
                f"aes-256-gcm kdf={sealed_blob.get('kdf')} "
                f"iter={sealed_blob.get('iterations')}",
            )
        )
        key_policy = "passphrase"
        crypto = {
            "algorithm": "aes-256-gcm",
            "kdf": sealed_blob.get("kdf", "pbkdf2-sha256"),
            "key_policy": key_policy,
            "ciphertext_present": True,
            "crypto_version": sealed_blob.get("crypto_version", 2),
        }
        if sealed_blob.get("iterations") is not None:
            crypto["iterations"] = sealed_blob["iterations"]
        if sealed_blob.get("argon2"):
            crypto["argon2"] = sealed_blob["argon2"]
    else:
        craft_channels.append(
            _ch("optional_ciphertext", "skipped", "no_passphrase")
        )
        crypto = {
            "algorithm": "none",
            "key_policy": "none",
            "ciphertext_present": False,
        }

    craft_channels.append(
        _ch("intent_digest", "applied", f"sha256 hex len={len(digest)}")
    )
    craft_channels.append(
        _ch(
            "intent_commitment",
            "applied",
            f"scheme={commitment_rec['scheme']} (nonce private)",
        )
    )

    if layout.monogram_points:
        craft_channels.append(
            _ch(
                "spare_monogram",
                "applied",
                f"letters={len(spare)} points={len(layout.monogram_points)}",
            )
        )
    else:
        craft_channels.append(
            _ch("spare_monogram", "skipped", "no_letters_after_reduction")
        )

    if layout.kamea_points:
        craft_channels.append(
            _ch(
                "kamea_path",
                "applied",
                f"planet={square_name} points={len(layout.kamea_points)}",
            )
        )
    else:
        craft_channels.append(
            _ch("kamea_path", "skipped", "no_path_points")
        )

    choice_src = "operator_override" if square else "digest_mod"
    craft_channels.append(
        _ch(
            "kamea_square_choice",
            "applied",
            f"planet={square_name} order={order} via={choice_src}",
        )
    )

    # Bind-runes + Rose Cross expansion craft channels
    if layout.bind_polylines and layout.bind_runes:
        craft_channels.append(
            _ch(
                "bind_runes",
                "applied",
                f"runes={len(layout.bind_runes)} strokes={len(layout.bind_polylines)}",
            )
        )
    else:
        craft_channels.append(
            _ch("bind_runes", "skipped", "no_runes_after_mapping")
        )

    if layout.rose_points and len(layout.rose_points) >= 1:
        craft_channels.append(
            _ch(
                "rose_cross_path",
                "applied",
                f"hebrew_petals={len(layout.rose_slots)} points={len(layout.rose_points)}",
            )
        )
    else:
        craft_channels.append(
            _ch("rose_cross_path", "skipped", "no_rose_path_points")
        )

    if planetary_seal and layout.planetary_seal_path:
        craft_channels.append(
            _ch(
                "planetary_seal",
                "applied",
                f"kind={planetary_seal_kind} planet={square_name} "
                f"points={len(layout.planetary_seal_path)}",
            )
        )
    else:
        craft_channels.append(
            _ch(
                "planetary_seal",
                "skipped",
                "not_requested" if not planetary_seal else "empty_seal",
            )
        )

    # --- SVG + stego ---
    base_svg = layout_to_svg(layout)
    stego_svg, stego_channels = stego_svg_embed(base_svg, digest, spare_letters=spare)

    # Privacy guard: public SVG must not leak plaintext intent or spare runs.
    # Short normalized intents (len < 12) skip the phrase scan — stego never
    # embeds them, and short substrings false-positive against hex/metadata.
    _assert_svg_privacy(stego_svg, normalized=normalized, spare=spare)

    # --- atomic run dir: stage under out_root, promote only after full success ---
    if out_root is not None:
        root = Path(out_root)
        root.mkdir(parents=True, exist_ok=True)
    else:
        root = ensure_private_dir(default_out_dir())
    # Run ids carry a one-second timestamp, so the same intent forged twice in
    # one second would get the same folder. Never reuse one: an earlier run
    # (with its wallpapers and proofs) must not be replaced.
    # The folder is claimed here with mkdir, which is atomic, so two forges
    # running at once get different ids and neither waits or fails.
    base_rid = make_run_id(digest)
    rid, attempt = base_rid, 1
    while True:
        final_dir = make_run_dir(root, rid)
        try:
            os.mkdir(final_dir, 0o700)
            break
        except FileExistsError:
            attempt += 1
            if attempt > 1000:
                raise RuntimeError("could not find a free run folder name") from None
            rid = f"{base_rid}-{attempt}"
    try:
        staging = Path(
            tempfile.mkdtemp(prefix=f".sf-staging-{rid}-", dir=str(root))
        )
    except BaseException:
        try:
            os.rmdir(final_dir)  # do not leave the claimed folder behind
        except OSError:
            pass
        raise

    try:
        svg_path = staging / "glyph.svg"
        svg_path.write_text(stego_svg, encoding="utf-8")

        # Prefer layout raster including bind/rose geometry
        png_path_str, png_channel = _try_png_lsb(
            stego_svg,
            digest,
            staging / "glyph.png",
            monogram_points=list(layout.monogram_points),
            kamea_points=list(layout.kamea_points),
        )
        # Re-apply with full layout if simple mono/kamea path was used
        if png_path_str and (
            layout.bind_polylines
            or layout.rose_points
            or layout.planetary_seal_strokes
            or layout.planetary_seal_path
        ):
            try:
                from sigil_forge.layout_raster import layout_to_png_bytes
                from sigil_forge.stego_png import embed_lsb, pack_payload as _pack

                seal_strokes = layout.planetary_seal_strokes or (
                    [layout.planetary_seal_path] if layout.planetary_seal_path else None
                )
                full_png = layout_to_png_bytes(
                    layout.monogram_points,
                    layout.kamea_points,
                    bind_polylines=layout.bind_polylines,
                    rose_points=layout.rose_points,
                    planetary_seal_strokes=seal_strokes,
                )
                stego_full = embed_lsb(full_png, _pack(bytes.fromhex(digest)))
                (staging / "glyph.png").write_bytes(stego_full)
                png_channel = _ch(
                    "png_lsb",
                    "applied",
                    "LSB digest-only via layout_raster+bind+rose+seal",
                )
            except Exception:  # noqa: BLE001
                pass

        # Optional geometry-locked AI polish prompt (no image API)
        gen_seed_channel = _ch("gen_seed", "skipped", "no_ai_polish")
        polish_path_final: str | None = None
        if write_polish:
            import json as _json

            from sigil_forge.prompt_polish import build_prompt

            stroke_count = (1 if layout.monogram_points else 0) + (
                1 if layout.kamea_points else 0
            )
            summary = {
                "intent_digest": digest,
                "stroke_count": stroke_count,
                "path_count": stroke_count,
                "view_box": list(layout.view_box),
                "bbox": [0.0, 0.0, 100.0, 100.0],
                "square_name": square_name,
            }
            polish_pkg = build_prompt(summary, polish_style)
            polish_file = staging / "polish_prompt.json"
            polish_file.write_text(
                _json.dumps(polish_pkg, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            gen_seed_channel = _ch(
                "gen_seed",
                "applied",
                f"seed={polish_pkg['seed']} polish_prompt.json",
            )
            polish_path_final = str(final_dir / "polish_prompt.json")

        # Assisted Spare seed artifact (non-monogram modes)
        spare_seed_final: str | None = None
        if spare_mode != "letter_monogram" and (layout.spare_result or {}).get(
            "artifact"
        ):
            import json as _json

            seed_path = staging / "spare-seed.json"
            seed_path.write_text(
                _json.dumps(layout.spare_result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            spare_seed_final = str(final_dir / "spare-seed.json")

        # Phonetic / mantric carrier (JSON only)
        phonetic_channel = _ch("phonetic_sigil", "skipped", "not_requested")
        phonetic_final: str | None = None
        if phonetic or spare_mode == "phonetic_mantric":
            import json as _json

            ph = build_phonetic_artifact(
                normalized, intent_digest=digest, mode="phonetic_mantric"
            )
            # The mantric form spells the intent out; owner-only, like the packet.
            ph_path = staging / "phoneme-sequence.json"
            write_private_text(ph_path, _json.dumps(ph, indent=2, sort_keys=True) + "\n")
            phonetic_final = str(final_dir / "phoneme-sequence.json")
            phonetic_channel = _ch(
                "phonetic_sigil",
                "applied",
                f"tokens={len(ph.get('phoneme_sequence') or [])}",
            )

        extras = [png_channel, gen_seed_channel, phonetic_channel]

        channels = _merge_channels(craft_channels, list(stego_channels), extras)

        kprov = layout.kamea_provenance or {}
        methods = {
            "spare": {
                "family": "intent_compression",
                "mode": (layout.spare_result or {}).get("mode", spare_mode),
                "reduction": "vowels_and_duplicate_collapse_v1",
                "letter_count": len(spare),
                "determinism": (layout.spare_result or {}).get("determinism"),
                "semantic_verification": (layout.spare_result or {}).get(
                    "semantic_verification"
                ),
                "spare_result": layout.spare_result,
            },
            "kamea": {
                "family": "name_path",
                "planet": square_name,
                "order": order,
                "encoding_system": kprov.get("encoding_system", enc),
                "transliteration_system": kprov.get("transliteration_system"),
                "original_numeric_sequence": kprov.get("original_numeric_sequence"),
                "reduced_numeric_sequence": kprov.get("reduced_numeric_sequence"),
                "reduction_operations": kprov.get("reduction_operations"),
                "path": kprov.get("path"),
                "claimed_historical_status": kprov.get("claimed_historical_status"),
                # legacy key kept for readers:
                "cipher": kprov.get("encoding_system", enc),
            },
            "bind_runes": {
                "family": "alphabetic_ligature",
                "system": "elder_futhark_stick_v1",
                "historical_basis": "runic_ligature",
                "intent_sigil_system": {"status": "modern_derivation"},
                "claimed_historical_status": "modern_derivation",
                "runes": list(layout.bind_runes or []),
            },
            "rose_cross": layout.rose_provenance
            or {
                "method_id": "rose_cross.hebrew_petal_path",
                "family": "name_path",
            },
            "planetary_seal": layout.planetary_seal
            or {"status": "not_requested"},
        }
        ontology = default_packet_ontology(
            spare_mode=spare_mode,
            kamea_encoding=enc,
            include_bind=True,
            include_rose=True,
            include_planetary_seal=bool(planetary_seal),
            planet=square_name if planetary_seal else None,
            planetary_seal_kind=planetary_seal_kind,
        )
        provenance = {
            "kamea": kprov,
            "rose_cross": layout.rose_provenance,
            "spare": layout.spare_result,
            "planetary_seal": layout.planetary_seal,
            "bind_runes": {
                "claimed_historical_status": "modern_derivation",
                "historical_basis": "runic_ligature",
            },
        }

        # Artifact paths point at the final location (post-promote).
        final_svg = final_dir / "glyph.svg"
        final_png = final_dir / "glyph.png" if png_path_str else None
        packet_json_path = final_dir / "forge-packet.json"
        packet_md_path = final_dir / "forge-packet.md"
        receipt_path_final = final_dir / "run-receipt.json"
        artifacts: dict[str, Any] = {
            "svg": str(final_svg),
            "png": str(final_png) if final_png else None,
            "run_dir": str(final_dir),
            "run_id": rid,
            "packet_json": str(packet_json_path),
            "packet_md": str(packet_md_path),
        }
        if polish_path_final:
            artifacts["polish_prompt_path"] = polish_path_final
        if spare_seed_final:
            artifacts["spare_seed_path"] = spare_seed_final
        if phonetic_final:
            artifacts["phoneme_sequence_path"] = phonetic_final
        if write_receipt:
            artifacts["receipt_json"] = str(receipt_path_final)

        verify_target = str(final_svg)
        verify_cmd = f"python3 scripts/sigil_forge.py verify {verify_target}"

        interop_block: dict[str, Any] = {}
        if interop:
            # Thin dual-name export (Orchestra-compatible labels); empty-ok otherwise
            interop_block = {
                "intent_token": digest[:16],
                "sigil_glyph": f"sf:{rid}",
                "related_skills": [],
                "note": "Thin interop export — not Enochian/Goetic authority seals",
            }

        include_normalized = not seal_packet

        # --- Proof of Intent: glyph digest, forge-manifest, Merkle root, capsule ---
        version = "0.0.0"
        vpath = skill_root() / "VERSION"
        if vpath.is_file():
            version = vpath.read_text(encoding="utf-8").strip() or version

        glyph_digest = file_sha256(str(staging / "glyph.svg"))
        pub_commit = public_commitment(commitment_rec)
        # Private detail first; the public manifest names it by digest only.
        method_manifest = build_method_manifest(
            forge_version=version,
            intent_digest=digest,
            methods=methods,
            channels=channels,
        )
        mm_digest = write_private_manifest(staging / METHOD_NAME, method_manifest)
        forge_manifest = build_forge_manifest(
            forge_version=version,
            intent_digest=digest,
            intent_commitment=pub_commit["value"],
            mode=mode,
            methods=methods,
            channels=channels,
            glyph_digest=glyph_digest,
            method_manifest_digest=mm_digest,
        )
        mf_digest = write_manifest(staging / "forge-manifest.json", forge_manifest)

        import json as _json

        capsule: dict[str, Any] | None = None
        ct_digest: str | None = None
        if passphrase:
            # Seal witness once; public_bindings.artifact_root filled after Merkle
            # (public fields only — does not re-encrypt / change ciphertext leaf).
            capsule = build_capsule(
                intent=intent,
                normalized=normalized,
                commitment_record=commitment_rec,
                passphrase=passphrase,
                forge_version=version,
                method_manifest_digest=mm_digest,
                artifact_root=None,
                kdf=kdf_arg or ("auto" if prefer_for_seal else "pbkdf2-sha256"),
            )
            ct_digest = ciphertext_digest(capsule)

        root_info = build_sigil_root(
            {
                "intent_commitment": pub_commit["value"],
                "intent_digest": digest,
                "method_manifest_digest": mm_digest,
                "canonical_glyph_digest": glyph_digest,
                "forge_manifest_digest": mf_digest,
                "ciphertext_digest": ct_digest,
            }
        )
        sigil_root = root_info["sigil_root"]
        if capsule is not None:
            capsule.setdefault("public_bindings", {})["artifact_root"] = sigil_root
            (staging / "intent-capsule.json").write_text(
                _json.dumps(capsule, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            artifacts["intent_capsule"] = str(final_dir / "intent-capsule.json")

        (staging / "artifact-root.json").write_text(
            _json.dumps(root_info, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        artifacts["forge_manifest"] = str(final_dir / "forge-manifest.json")
        artifacts["method_manifest"] = str(final_dir / METHOD_NAME)
        artifacts["artifact_root"] = str(final_dir / "artifact-root.json")

        # SF11 / v2 carrier bind: inject root into SVG metadata + PNG LSB (after root known)
        try:
            from sigil_forge.stego_envelope import pack_sf11
            from sigil_forge.stego_svg import inject_sigil_root

            svg_path = staging / "glyph.svg"
            if svg_path.is_file():
                svg_text = svg_path.read_text(encoding="utf-8")
                svg_path.write_text(
                    inject_sigil_root(svg_text, sigil_root), encoding="utf-8"
                )
            png_path = staging / "glyph.png"
            if png_path.is_file():
                from sigil_forge.stego_png import embed_lsb, read_rgb_png, write_rgb_png

                raw_png = png_path.read_bytes()
                w, h, rgb = read_rgb_png(raw_png)
                clean = write_rgb_png(w, h, rgb)
                payload = pack_sf11(intent_digest=digest, sigil_root=sigil_root)
                png_path.write_bytes(embed_lsb(clean, payload))
        except Exception:  # noqa: BLE001 — carriers optional; root still in packet
            pass

        packet = build_packet(
            mode=mode,
            intent_digest=digest,
            channels=channels,
            methods=methods,
            artifacts=artifacts,
            crypto=crypto,
            verify_cmd=verify_cmd,
            normalized_intent=normalized if include_normalized else None,
            sealed_blob=sealed_blob if passphrase else None,
            include_normalized=include_normalized,
            ontology=ontology,
            provenance=provenance,
            interop=interop_block,
        )
        packet["schema_version"] = packet.get("schema_version") or SCHEMA_VERSION
        # Proof-of-Intent public surfaces (additive)
        packet["intent_commitment"] = pub_commit
        packet["compatibility"] = {"intent_digest": digest}
        packet["sigil_root"] = sigil_root

        # ZK companion commitment (fixed-width preimage for circuits)
        from sigil_forge.proofs.zk_commit import zk_commit

        zk_rec = zk_commit(normalized, commitment_rec["nonce"])
        packet["intent_commitment_zk"] = {
            "scheme": zk_rec["scheme"],
            "value": zk_rec["value"],
            "intent_len": zk_rec["intent_len"],
            "max_intent_bytes": zk_rec["max_intent_bytes"],
        }
        if capsule is not None:
            capsule.setdefault("public_bindings", {})["intent_commitment_zk"] = zk_rec[
                "value"
            ]
            # rewrite capsule file with zk binding (public only)
            (staging / "intent-capsule.json").write_text(
                _json.dumps(capsule, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        # Proof generation (optional; never fails the forge for missing Noir/zkVM)
        proof_block: dict[str, Any] = {
            "mode": proof_mode,
            "status": "skipped",
            "detail": "proof mode none",
        }
        if proof_mode in ("commitment", "zk-knowledge") and passphrase and capsule:
            proofs_dir = staging / "proofs"
            proofs_dir.mkdir(parents=True, exist_ok=True)
            public_inputs = {
                "intent_commitment": pub_commit["value"],
                "intent_commitment_zk": zk_rec["value"],
                "sigil_root": sigil_root,
                "forge_version": version,
                "intent_len": zk_rec["intent_len"],
            }
            from sigil_forge.proofs.local_knowledge import LocalCapsuleProvider
            from sigil_forge.proofs.manifest import write_proof_manifest
            from sigil_forge.proofs.noir_provider import NoirProvider

            # Always write local capsule knowledge attestation when sealed
            local = LocalCapsuleProvider().prove(
                {"capsule": capsule, "passphrase": passphrase},
                public_inputs,
                out_dir=proofs_dir,
            )
            write_proof_manifest(proofs_dir, local)
            proof_block = {
                "mode": proof_mode,
                "status": local.status,
                "provider": local.provider,
                "proof_kind": local.proof_kind,
                "detail": local.detail,
                "proof_path": local.proof_path,
            }
            artifacts["proofs_dir"] = str(final_dir / "proofs")

            if proof_mode == "zk-knowledge":
                noir = NoirProvider()
                nres = noir.prove(
                    {
                        "normalized_intent": normalized,
                        "nonce": commitment_rec["nonce"],
                    },
                    public_inputs,
                    out_dir=proofs_dir,
                )
                # Prefer noir manifest when generated; keep local attestation file too
                write_proof_manifest(
                    proofs_dir,
                    nres,
                    extra={
                        "local_attestation": local.to_dict(),
                    },
                )
                proof_block = {
                    "mode": proof_mode,
                    "status": nres.status,
                    "provider": nres.provider,
                    "proof_kind": nres.proof_kind,
                    "detail": nres.detail,
                    "proof_path": nres.proof_path,
                    "local_attestation_status": local.status,
                }
        elif proof_mode == "zk-forge":
            # Restricted forge_core zkVM path (risc0 adapter; skip if unavailable)
            proofs_dir = staging / "proofs"
            proofs_dir.mkdir(parents=True, exist_ok=True)
            public_inputs = {
                "intent_digest": digest,
                "intent_commitment": pub_commit["value"],
                "intent_commitment_zk": zk_rec["value"],
                "sigil_root": sigil_root,
                "forge_version": version,
                "square_name": square_name,
                "kamea_encoding": enc,
            }
            from sigil_forge.proofs.manifest import write_proof_manifest
            from sigil_forge.proofs.risc0_provider import Risc0Provider

            r0 = Risc0Provider()
            rres = r0.prove(
                {
                    "normalized_intent": normalized,
                    "forge_config": core.to_public_dict(),
                },
                public_inputs,
                out_dir=proofs_dir,
            )
            write_proof_manifest(proofs_dir, rres)
            proof_block = {
                "mode": proof_mode,
                "status": rres.status,
                "provider": rres.provider,
                "proof_kind": rres.proof_kind,
                "detail": rres.detail,
                "proof_path": rres.proof_path,
            }
            artifacts["proofs_dir"] = str(final_dir / "proofs")
        elif proof_mode == "zk-knowledge" and not passphrase:
            proof_block = {
                "mode": proof_mode,
                "status": "failed",
                "detail": "zk-knowledge requires passphrase for capsule witness",
            }
        elif proof_mode == "commitment" and not passphrase:
            proof_block = {
                "mode": proof_mode,
                "status": "skipped",
                "detail": "commitment surfaces present; capsule skipped (no passphrase)",
            }

        packet["proof"] = proof_block

        # Validate before promote — incomplete runs never leave a public run dir.
        schema_path = skill_root() / "schemas" / "forge-packet.schema.json"
        try:
            validate_packet(packet, schema_path=schema_path)
        except Exception as exc:  # noqa: BLE001
            if "structural" in str(exc).lower():
                raise
            if not schema_path.is_file():
                validate_packet(packet, schema_path=None)
            else:
                raise

        write_packet_files(packet, staging)

        if write_receipt:
            from sigil_forge.receipt import (
                append_receipt_log,
                build_run_receipt,
                write_receipt_file,
            )

            version = "0.0.0"
            vpath = skill_root() / "VERSION"
            if vpath.is_file():
                version = vpath.read_text(encoding="utf-8").strip() or version
            # verify_ok filled after promote when caller re-verifies; leave None
            receipt = build_run_receipt(packet, skill_version=version, verify_ok=None)
            write_receipt_file(receipt, staging / "run-receipt.json")
            try:
                append_receipt_log(receipt)
            except OSError:
                pass

        # Promote staging → final, onto the empty folder claimed at the start.
        try:
            os.rename(staging, final_dir)
        except OSError:
            # Windows cannot rename onto an existing folder, even an empty one.
            # Move the contents in instead, so the claim is never given up.
            for entry in sorted(staging.iterdir()):
                os.rename(entry, final_dir / entry.name)
            os.rmdir(staging)
        staging = None  # ownership transferred
        return packet
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
            try:
                os.rmdir(final_dir)  # release the claim; only ever empty here
            except OSError:
                pass
