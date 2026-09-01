#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python scripts/sigil_forge.py` without install
sys.path.insert(0, str(Path(__file__).resolve().parent))


def cmd_help(_: argparse.Namespace) -> int:
    print(
        "sigil-forge — multi-channel intent sigils (Hermes skill)\n"
        "commands: construct | verify | verify-proof | inspect | wallpaper | wizard | open | learn | ledger | "
        "policy | doctor | eval | check | help\n"
        "Product: wallpaper PNG with SF12 sealed vault (intent + methods in-image).\n"
        "See SKILL.md, QUICKSTART.md, references/hermes-runtime-contract.md\n"
        "Wallpaper product: references/wallpaper-framework.md\n"
        "PoI (on demand): references/proof-of-intent.md"
    )
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    """Smoke-check skill tree: required files, schemas, imports, dry construct."""
    import importlib
    import tempfile

    from paths import skill_root

    root = skill_root()
    required = [
        "VERSION",
        "SKILL.md",
        "QUICKSTART.md",
        "install.sh",
        "scripts/paths.py",
        "scripts/sigil_forge.py",
        "scripts/construct.py",
        "scripts/verify.py",
        "scripts/forge_core.py",
        "scripts/normalize.py",
        "scripts/safety.py",
        "scripts/spare.py",
        "scripts/kamea.py",
        "scripts/fuse.py",
        "scripts/svg_export.py",
        "scripts/stego_svg.py",
        "scripts/stego_png.py",
        "scripts/layout_raster.py",
        "scripts/prompt_polish.py",
        "scripts/bind_runes.py",
        "scripts/rose_cross.py",
        "scripts/receipt.py",
        "scripts/ontology.py",
        "scripts/planetary_seals.py",
        "scripts/wallpaper/pipeline.py",
        "scripts/wallpaper/providers.py",
        "scripts/wallpaper/vault.py",
        "scripts/wizard.py",
        "scripts/planetary_corpus.py",
        "scripts/plate_strokes.py",
        "scripts/policy_lint.py",
        "scripts/crypto_domains.py",
        "scripts/commitment.py",
        "scripts/derivation.py",
        "scripts/artifact_root.py",
        "scripts/forge_manifest.py",
        "scripts/intent_capsule.py",
        "scripts/stego_envelope.py",
        "scripts/inspect_artifact.py",
        "scripts/proofs/__init__.py",
        "scripts/proofs/registry.py",
        "scripts/proofs/base.py",
        "scripts/proofs/zk_commit.py",
        "scripts/proofs/local_knowledge.py",
        "scripts/proofs/noir_provider.py",
        "scripts/proofs/risc0_provider.py",
        "scripts/proofs/verify_run.py",
        "scripts/proofs/manifest.py",
        "references/planetary-character-corpus.json",
        "references/planetary-plate-strokes.json",
        "references/hermes-runtime-contract.md",
        "references/proof-of-intent.md",
        "schemas/wallpaper-spec.schema.json",
        "schemas/wallpaper-receipt.schema.json",
        "schemas/intent-capsule.schema.json",
        "schemas/artifact-root.schema.json",
        "schemas/forge-manifest.schema.json",
        "schemas/proof-manifest.schema.json",
        "scripts/validate_hermes_skill.py",
        "scripts/crypto_payload.py",
        "scripts/packet.py",
        "schemas/forge-packet.schema.json",
        "schemas/construction-result.schema.json",
        "schemas/channel-manifest.schema.json",
    ]
    missing = [p for p in required if not (root / p).is_file()]

    # Schemas must be valid JSON objects
    schemas_ok = True
    schema_errors: list[str] = []
    for rel in (
        "schemas/forge-packet.schema.json",
        "schemas/construction-result.schema.json",
        "schemas/channel-manifest.schema.json",
        "schemas/intent-capsule.schema.json",
        "schemas/artifact-root.schema.json",
        "schemas/forge-manifest.schema.json",
        "schemas/proof-manifest.schema.json",
    ):
        path = root / rel
        if not path.is_file():
            schemas_ok = False
            schema_errors.append(f"{rel}: missing")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                schemas_ok = False
                schema_errors.append(f"{rel}: not an object")
        except (OSError, json.JSONDecodeError) as exc:
            schemas_ok = False
            schema_errors.append(f"{rel}: {exc}")

    # Import core scripts modules (incl. pure forge_core + proof providers)
    modules = (
        "paths",
        "construct",
        "verify",
        "forge_core",
        "normalize",
        "safety",
        "spare",
        "kamea",
        "fuse",
        "svg_export",
        "stego_svg",
        "stego_png",
        "layout_raster",
        "prompt_polish",
        "bind_runes",
        "rose_cross",
        "receipt",
        "ontology",
        "planetary_seals",
        "planetary_corpus",
        "plate_strokes",
        "wizard",
        "crypto_payload",
        "crypto_domains",
        "commitment",
        "derivation",
        "artifact_root",
        "forge_manifest",
        "intent_capsule",
        "stego_envelope",
        "inspect_artifact",
        "packet",
        "policy_lint",
        "proofs.registry",
        "proofs.zk_commit",
        "proofs.risc0_provider",
    )
    module_errors: list[str] = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            module_errors.append(f"{name}: {exc}")
    modules_ok = not module_errors

    # Hermes SKILL.md frontmatter (packaging gate, incl. ≤60-char description)
    hermes_ok = False
    hermes_errors: list[str] = []
    description_chars = 0
    try:
        from validate_hermes_skill import MAX_DESCRIPTION, validate as validate_hermes

        hermes_report = validate_hermes(root / "SKILL.md")
        hermes_ok = bool(hermes_report.get("ok"))
        hermes_errors = list(hermes_report.get("errors") or [])
        description_chars = int(hermes_report.get("description_chars") or 0)
        if description_chars > MAX_DESCRIPTION:
            hermes_ok = False
            msg = (
                f"description length {description_chars} > {MAX_DESCRIPTION}"
            )
            if msg not in hermes_errors:
                hermes_errors.append(msg)
    except Exception as exc:  # noqa: BLE001
        hermes_errors = [str(exc)]
        hermes_ok = False

    # Dry construct + verify into a temp directory (no persistent out/)
    construct_ok = False
    verify_ok = False
    poi_ok = False
    construct_error: str | None = None
    try:
        from construct import run as construct_run
        from verify import run as verify_run

        with tempfile.TemporaryDirectory(prefix="sigil-forge-check-") as tmp:
            # write_receipt=False: never append skill-root receipt logs during check
            # (install post-check must not pollute ~/.hermes/skills/sigil-forge/out/)
            packet = construct_run(
                "I maintain calm focus while shipping Sigil-Forge",
                mode="creative",
                out_root=Path(tmp),
                square="saturn",
                write_receipt=False,
            )
            svg = Path(packet["artifacts"]["svg"])
            if not svg.is_file():
                raise RuntimeError("dry construct did not write glyph.svg")
            if not packet.get("intent_digest"):
                raise RuntimeError("dry construct missing intent_digest")
            # Proof-of-Intent surfaces always present from v0.12+
            if not packet.get("intent_commitment"):
                raise RuntimeError("dry construct missing intent_commitment")
            if not packet.get("sigil_root"):
                raise RuntimeError("dry construct missing sigil_root")
            run_dir = Path(packet["artifacts"]["run_dir"])
            if not (run_dir / "forge-manifest.json").is_file():
                raise RuntimeError("dry construct missing forge-manifest.json")
            construct_ok = True
            poi_ok = True
            v = verify_run(svg)
            verify_ok = bool(v.get("ok")) and v.get("intent_digest") == packet[
                "intent_digest"
            ]
            if not verify_ok:
                construct_error = f"verify failed: {v}"
    except Exception as exc:  # noqa: BLE001
        construct_error = str(exc)
        construct_ok = False
        verify_ok = False
        poi_ok = False

    ok = (
        not missing
        and schemas_ok
        and modules_ok
        and hermes_ok
        and construct_ok
        and verify_ok
        and poi_ok
    )
    print(
        json.dumps(
            {
                "ok": ok,
                "root": str(root),
                "missing": missing,
                "schemas_ok": schemas_ok,
                "schema_errors": schema_errors,
                "modules_ok": modules_ok,
                "module_errors": module_errors,
                "hermes_ok": hermes_ok,
                "hermes_errors": hermes_errors,
                "description_chars": description_chars,
                "description_ok": bool(description_chars) and description_chars <= 60,
                "construct_ok": construct_ok,
                "verify_ok": verify_ok,
                "poi_ok": poi_ok,
                "construct_error": construct_error,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if ok else 1


def cmd_construct(args: argparse.Namespace) -> int:
    from construct import resolve_passphrase, run as construct_run

    # Explicit --passphrase wins over SIGIL_FORGE_PASSPHRASE when both set.
    passphrase = resolve_passphrase(args.passphrase)
    try:
        packet = construct_run(
            args.intent,
            mode=args.mode,
            out_root=Path(args.out) if args.out else None,
            passphrase=passphrase,
            square=args.square,
            seal_packet=bool(args.seal_packet),
            write_polish=bool(getattr(args, "polish", False)),
            polish_style=getattr(args, "polish_style", None),
            write_receipt=not bool(getattr(args, "no_receipt", False)),
            kamea_encoding=getattr(args, "kamea_encoding", None),
            spare_mode=getattr(args, "spare_mode", None) or "letter_monogram",
            planetary_seal=bool(getattr(args, "planetary_seal", False)),
            planetary_seal_kind=getattr(args, "planetary_seal_kind", None)
            or "traditional_seal",
            planetary_geometry=getattr(args, "planetary_geometry", None) or "auto",
            prefer_argon2=bool(getattr(args, "argon2", False)),
            kdf=getattr(args, "kdf", None),
            proof=getattr(args, "proof", None) or "none",
            interop=bool(getattr(args, "interop", False)),
            phonetic=bool(getattr(args, "phonetic", False))
            or (getattr(args, "spare_mode", None) == "phonetic_mantric"),
        )
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1

    wallpaper_results = None
    if bool(getattr(args, "wallpaper", False)):
        run_dir = packet.get("artifacts", {}).get("run_dir")
        if not run_dir:
            print(
                json.dumps({"ok": False, "error": "construct missing run_dir for --wallpaper"}),
                file=sys.stderr,
            )
            return 1
        try:
            wallpaper_results = _run_wallpapers(Path(run_dir), args)
        except Exception as exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": f"wallpaper after construct failed: {exc}",
                        "intent_digest": packet.get("intent_digest"),
                        "run_id": packet.get("artifacts", {}).get("run_id"),
                    }
                ),
                file=sys.stderr,
            )
            return 1
        if not all(r.get("ok") for r in wallpaper_results):
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "wallpaper verification failed",
                        "intent_digest": packet["intent_digest"],
                        "run_id": packet.get("artifacts", {}).get("run_id"),
                        "wallpapers": wallpaper_results,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1

    # Print compact summary to stdout (full packet on --json)
    if args.json:
        if wallpaper_results is not None:
            packet = dict(packet)
            packet["wallpapers"] = wallpaper_results
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        summary: dict = {
            "ok": True,
            "intent_digest": packet["intent_digest"],
            "run_id": packet.get("artifacts", {}).get("run_id"),
            "svg": packet.get("artifacts", {}).get("svg"),
            "packet": packet.get("artifacts", {}).get("packet_json"),
            "channels_applied": [
                c["id"]
                for c in packet.get("channels", [])
                if c.get("status") == "applied"
            ],
        }
        if wallpaper_results is not None:
            summary["wallpapers"] = wallpaper_results
        print(json.dumps(summary, indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from verify import run as verify_run

    result = verify_run(
        Path(args.artifact),
        expected_digest=getattr(args, "expected_digest", None),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    """Inspect public carrier for digest / sigil_root (no plaintext intent)."""
    from inspect_artifact import inspect_path

    result = inspect_path(args.artifact)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


def cmd_verify_proof(args: argparse.Namespace) -> int:
    """Verify proof-of-intent artifacts for a forge run (no plaintext intent out)."""
    from construct import resolve_passphrase
    from proofs.verify_run import verify_proof_run

    passphrase = resolve_passphrase(getattr(args, "passphrase", None))
    result = verify_proof_run(args.run, passphrase=passphrase)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("verified") else 1


def cmd_open(args: argparse.Namespace) -> int:
    """Decrypt sealed packet, capsule, or wallpaper SF12 vault (product carrier)."""
    from construct import resolve_passphrase
    from crypto_payload import open_intent

    path = Path(args.packet)
    if not path.is_file():
        print(json.dumps({"ok": False, "error": f"not found: {path}"}), file=sys.stderr)
        return 1
    passphrase = resolve_passphrase(args.passphrase)
    if not passphrase:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "passphrase required (--passphrase or SIGIL_FORGE_PASSPHRASE)",
                }
            ),
            file=sys.stderr,
        )
        return 1

    # Wallpaper product: SF12 sealed vault inside PNG LSB
    if getattr(args, "wallpaper", False) or path.suffix.lower() == ".png":
        if getattr(args, "wallpaper", False) or path.suffix.lower() == ".png":
            try:
                from wallpaper.vault import open_wallpaper_vault

                # Only treat as vault when --wallpaper or SF12 probe succeeds
                if getattr(args, "wallpaper", False):
                    result = open_wallpaper_vault(path, passphrase)
                    if args.json:
                        print(json.dumps(result, indent=2, sort_keys=True))
                    else:
                        print(result.get("intent") or result.get("normalized_intent") or "")
                    return 0
            except Exception as exc:  # noqa: BLE001
                if getattr(args, "wallpaper", False):
                    print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
                    return 1
                # fall through for non-wallpaper png opens that are not vaults

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        # last chance: png vault without --wallpaper flag
        if path.suffix.lower() == ".png":
            try:
                from wallpaper.vault import open_wallpaper_vault

                result = open_wallpaper_vault(path, passphrase)
                if args.json:
                    print(json.dumps(result, indent=2, sort_keys=True))
                else:
                    print(result.get("intent") or result.get("normalized_intent") or "")
                return 0
            except Exception as exc2:  # noqa: BLE001
                print(json.dumps({"ok": False, "error": str(exc2)}), file=sys.stderr)
                return 1
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1

    # Capsule mode: open intent-capsule.json sealed witness
    if getattr(args, "capsule", False):
        from intent_capsule import open_capsule

        try:
            witness = open_capsule(data, passphrase)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
            return 1
        intent_text = witness.get("intent") or witness.get("normalized_intent") or ""
        if args.json:
            # Authorized disclosure only — never log elsewhere
            print(
                json.dumps(
                    {
                        "ok": True,
                        "source": "intent_capsule",
                        "intent": witness.get("intent"),
                        "normalized_intent": witness.get("normalized_intent"),
                        "intent_digest": (data.get("compatibility") or {}).get(
                            "intent_digest"
                        ),
                        "commitment": data.get("commitment"),
                        "public_bindings": data.get("public_bindings"),
                    },
                    indent=2,
                )
            )
        else:
            print(intent_text)
        return 0

    sealed = data.get("sealed_intent")
    if not isinstance(sealed, dict):
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        "packet has no sealed_intent "
                        "(construct without seal? use --capsule for intent-capsule.json)"
                    ),
                }
            ),
            file=sys.stderr,
        )
        return 1
    try:
        text = open_intent(sealed, passphrase)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "source": "forge_packet",
                    "intent": text,
                    "intent_digest": data.get("intent_digest"),
                },
                indent=2,
            )
        )
    else:
        print(text)
    return 0


def cmd_learn(args: argparse.Namespace) -> int:
    """Append a PROPOSED learning-ledger observation (never auto-canon)."""
    from receipt import append_ledger, build_ledger_entry

    channels = []
    if args.channels:
        channels = [c.strip() for c in args.channels.split(",") if c.strip()]
    entry = build_ledger_entry(
        class_name=args.entry_class,
        summary=args.summary,
        run_id=args.run_id,
        intent_digest=args.digest,
        channels=channels,
    )
    try:
        path = append_ledger(entry, Path(args.ledger) if args.ledger else None)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "canon_status": "PROPOSED",
                "ledger": str(path),
                "entry": entry,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    """List / export PROPOSED ledger entries or human-gated promote to proposals."""
    from receipt import (
        default_canon_proposals_path,
        default_ledger_path,
        export_proposed,
        promote_entry,
        read_ledger,
    )

    ledger_cmd = getattr(args, "ledger_cmd", None) or "list"
    path = Path(args.ledger) if getattr(args, "ledger", None) else default_ledger_path()
    limit = int(getattr(args, "limit", 20) or 20)

    if ledger_cmd in ("list", "export"):
        if ledger_cmd == "export":
            entries = export_proposed(limit=limit, ledger_path=path)
        else:
            entries = read_ledger(path, limit=limit)
        print(
            json.dumps(
                {
                    "ok": True,
                    "ledger": str(path),
                    "count": len(entries),
                    "entries": entries,
                    "mode": ledger_cmd,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if ledger_cmd == "promote":
        out = (
            Path(args.out)
            if getattr(args, "out", None)
            else default_canon_proposals_path()
        )
        try:
            proposal = promote_entry(
                int(args.index),
                confirm=str(getattr(args, "i_confirm", "") or ""),
                ledger_path=path,
                out_path=out,
                limit=limit,
            )
        except (ValueError, TypeError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "ok": True,
                    "ledger": str(path),
                    "proposals": str(out),
                    "canon_status": "HUMAN_PROMOTED",
                    "proposal": proposal,
                    "note": "Learning ledger unchanged (PROPOSED); references/ not mutated",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print(
        json.dumps(
            {"ok": False, "error": f"unknown ledger subcommand: {ledger_cmd}"},
            indent=2,
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return 2


def cmd_policy(args: argparse.Namespace) -> int:
    """Lint text for efficacy claims and authority-seal requests (CI / agents)."""
    from policy_lint import detect_authority_seal_request, lint_efficacy_text

    if getattr(args, "policy_cmd", None) != "check":
        print(
            json.dumps(
                {"ok": False, "error": "unknown policy subcommand"},
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    if args.text is not None:
        text = args.text
    elif args.file is not None:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        print(
            json.dumps(
                {"ok": False, "error": "policy check requires --text or --file"},
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    eff = lint_efficacy_text(text)
    auth, fam = detect_authority_seal_request(text)
    ok = not eff and not auth
    print(
        json.dumps(
            {
                "ok": ok,
                "efficacy_hits": eff,
                "authority_seal_request": auth,
                "authority_family": fam,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if ok else 1


def cmd_doctor(_: argparse.Namespace) -> int:
    """Environment + skill health (superset of check for operators)."""
    import importlib
    import platform

    from crypto_payload import argon2_available
    from paths import skill_root

    root = skill_root()
    missing = [
        p
        for p in (
            "VERSION",
            "SKILL.md",
            "QUICKSTART.md",
            "scripts/construct.py",
            "scripts/forge_core.py",
            "scripts/kamea.py",
            "scripts/proofs/registry.py",
            "references/hermes-runtime-contract.md",
            "references/proof-of-intent.md",
            "schemas/sigil-method.schema.json",
            "schemas/intent-capsule.schema.json",
            "schemas/proof-manifest.schema.json",
            "references/source-manifest.yaml",
        )
        if not (root / p).is_file()
    ]
    module_errors: list[str] = []
    for name in (
        "construct",
        "forge_core",
        "kamea",
        "ontology",
        "planetary_seals",
        "phonetic",
        "proofs.registry",
    ):
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            module_errors.append(f"{name}: {exc}")

    proof_providers: list[dict] = []
    try:
        from proofs.registry import list_providers

        proof_providers = list_providers()
    except Exception as exc:  # noqa: BLE001
        module_errors.append(f"proofs.registry.list_providers: {exc}")

    hermes_ok = False
    hermes_errors: list[str] = []
    description_chars = 0
    try:
        from validate_hermes_skill import MAX_DESCRIPTION, validate as validate_hermes

        hr = validate_hermes(root / "SKILL.md")
        hermes_ok = bool(hr.get("ok"))
        hermes_errors = list(hr.get("errors") or [])
        description_chars = int(hr.get("description_chars") or 0)
        if description_chars > MAX_DESCRIPTION:
            hermes_ok = False
            msg = f"description length {description_chars} > {MAX_DESCRIPTION}"
            if msg not in hermes_errors:
                hermes_errors.append(msg)
    except Exception as exc:  # noqa: BLE001
        hermes_errors = [str(exc)]

    report: dict = {
        "ok": not missing and not module_errors and hermes_ok,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "skill_root": str(root),
        "version": (root / "VERSION").read_text(encoding="utf-8").strip()
        if (root / "VERSION").is_file()
        else None,
        "argon2_available": argon2_available(),
        "layout_raster": True,
        "missing": missing,
        "module_errors": module_errors,
        "hermes_ok": hermes_ok,
        "hermes_errors": hermes_errors,
        "description_chars": description_chars,
        "description_ok": bool(description_chars) and description_chars <= 60,
        "proof_providers": proof_providers,
        "packaging": "hermes-skill",
        "hermes_skill_dir_env": __import__("os").environ.get("HERMES_SKILL_DIR"),
    }
    try:
        from layout_raster import layout_to_png_bytes

        png = layout_to_png_bytes([(10.0, 10.0), (90.0, 90.0)], [])
        report["layout_raster_bytes"] = len(png)
    except Exception as exc:  # noqa: BLE001
        report["layout_raster"] = False
        report["layout_raster_error"] = str(exc)
        report["ok"] = False
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


def _wallpaper_kwargs(args: argparse.Namespace) -> dict:
    """Shared kwargs for wallpaper pipeline from CLI namespace."""
    from construct import resolve_passphrase

    # Wallpaper presentation mode: wallpaper cmd uses --mode; construct uses --wp-mode
    # (construct already owns --mode for creative|practice framing).
    wp_mode = getattr(args, "wp_mode", None) or getattr(args, "mode", None) or "focus"
    # When construct --mode is creative/practice, ignore it for wallpapers
    if wp_mode in ("creative", "practice"):
        wp_mode = getattr(args, "wp_mode", None) or "focus"
    embed = getattr(args, "embed", None) or "auto"
    return {
        "mode": wp_mode,
        "intensity": getattr(args, "intensity", "balanced") or "balanced",
        "placement": getattr(args, "placement", None),
        "symbolic_theme": getattr(args, "theme", None) or "neutral",
        "visual_direction": getattr(args, "style", None)
        or "dark architectural minimalism",
        "style_preset": getattr(args, "preset", None),
        "background_method": getattr(args, "background_method", None) or "procedural",
        "background_path": Path(args.background) if getattr(args, "background", None) else None,
        "provider": getattr(args, "provider", None),
        "provider_command": getattr(args, "provider_command", None),
        "model": getattr(args, "model", None),
        "require_ai": bool(getattr(args, "require_ai", False)),
        "embedded_payload": embed,
        "passphrase": resolve_passphrase(getattr(args, "passphrase", None)),
        "intent": getattr(args, "intent", None),
        "kdf": getattr(args, "kdf", None) or "auto",
    }


def _run_wallpapers(run_dir: Path, args: argparse.Namespace) -> list[dict]:
    from wallpaper.pipeline import build_wallpaper, build_wallpapers_for_run

    kwargs = _wallpaper_kwargs(args)
    if getattr(args, "surface", None):
        return [
            build_wallpaper(
                run_dir,
                surface=str(args.surface).replace("-", "_"),
                **kwargs,
            )
        ]
    surfaces = [
        s.strip().replace("-", "_")
        for s in (getattr(args, "surfaces", None) or "").split(",")
        if s.strip()
    ]
    if not surfaces:
        surfaces = ["phone_lock", "phone_home", "desktop"]
    return build_wallpapers_for_run(run_dir, surfaces=surfaces, **kwargs)


def cmd_wallpaper(args: argparse.Namespace) -> int:
    """Compose device wallpapers from a verified forge run (immutable glyph)."""
    run_dir = Path(args.run)
    try:
        results = _run_wallpapers(run_dir, args)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    ok = all(r.get("ok") for r in results)
    print(json.dumps({"ok": ok, "results": results}, indent=2, sort_keys=True))
    return 0 if ok else 1


def cmd_wizard(args: argparse.Namespace) -> int:
    """Hermes-facing guided forge wizard (step runner + apply)."""
    from wizard import (
        apply_answers,
        create_session,
        default_answers,
        interactive_answers,
        load_answers_file,
        load_session,
        next_step,
        save_session,
        session_next,
        validate_answers,
        wizard_script,
    )

    path = getattr(args, "path", None) or "full"

    if getattr(args, "list_corpus", False):
        from planetary_corpus import list_corpus_summary, load_corpus

        data = load_corpus()
        print(
            json.dumps(
                {
                    "corpus_id": data.get("corpus_id"),
                    "source_tradition": data.get("source_tradition"),
                    "planets": list_corpus_summary(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if getattr(args, "session_new", False):
        try:
            doc = create_session(path=path if path in ("quick", "full") else "quick")
        except ValueError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
            return 1
        # Immediately return first next-step for agent loop
        nxt = next_step(doc.get("answers") or {}, path=doc["path"])
        nxt["session_id"] = doc["session_id"]
        print(json.dumps({"ok": True, "session": doc, "next": nxt}, indent=2, sort_keys=True))
        return 0

    if getattr(args, "defaults", False):
        print(
            json.dumps(
                {"path": path, "answers": default_answers()},
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if getattr(args, "script", False) or (
        not getattr(args, "next", False)
        and not getattr(args, "apply", None)
        and not getattr(args, "answers_json", None)
        and not getattr(args, "interactive", False)
        and not getattr(args, "session", None)
        and not getattr(args, "validate_only", False)
    ):
        print(json.dumps(wizard_script(path=path), indent=2, sort_keys=True))
        return 0

    # Load / merge answers
    answers: dict = {}
    session_id = getattr(args, "session", None)

    if getattr(args, "answers_json", None):
        try:
            answers = json.loads(args.answers_json)
            if not isinstance(answers, dict):
                raise ValueError("answers-json must be an object")
        except (json.JSONDecodeError, ValueError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
            return 1
    elif getattr(args, "apply", None) and not getattr(args, "next", False):
        try:
            answers = load_answers_file(args.apply)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
            return 1
    elif session_id and not getattr(args, "next", False) and not getattr(args, "interactive", False):
        try:
            doc = load_session(session_id)
            answers = dict(doc.get("answers") or {})
            path = doc.get("path") or path
        except (OSError, ValueError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
            return 1

    if getattr(args, "next", False):
        try:
            if session_id:
                # merge answers_json into session if provided
                merge = answers if answers else None
                if getattr(args, "apply", None) and not answers:
                    merge = load_answers_file(args.apply)
                out = session_next(session_id, merge_answers=merge, path=path)
            else:
                if getattr(args, "apply", None) and not answers:
                    answers = load_answers_file(args.apply)
                out = next_step(answers, path=path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
            return 1
        print(json.dumps(out, indent=2, sort_keys=True))
        if out.get("refused"):
            return 1
        return 0

    if getattr(args, "interactive", False):
        answers = interactive_answers(path=path)
        if session_id:
            try:
                save_session(session_id, answers, path=path)
            except ValueError as exc:
                print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
                return 1

    if getattr(args, "validate_only", False):
        report = validate_answers(answers, path=path)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["ok"] else 1

    # apply
    if not answers and getattr(args, "apply", None):
        try:
            answers = load_answers_file(args.apply)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
            return 1
    if not answers:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "no answers; use --apply FILE, --answers-json, --interactive, or --next",
                }
            ),
            file=sys.stderr,
        )
        return 1

    result = apply_answers(
        answers,
        out_root=Path(args.out) if getattr(args, "out", None) else None,
        passphrase=getattr(args, "passphrase", None),
        path=path,
    )
    if session_id and result.get("ok"):
        try:
            save_session(session_id, result.get("answers") or answers, path=path)
        except ValueError:
            pass
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


def cmd_eval(_: argparse.Namespace) -> int:
    """Offline behavioral evals for method corpus honesty."""
    import tempfile

    from construct import run as construct_run
    from policy_lint import lint_efficacy_text
    from receipt import append_learning_entry
    from safety import check_intent

    cases: list[dict] = []
    ok_all = True

    def rec(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok_all
        cases.append({"name": name, "ok": passed, "detail": detail})
        if not passed:
            ok_all = False

    # refuse harmful
    ok_h, _ = check_intent("I will murder my neighbor tomorrow")
    rec("refuse_harmful", not ok_h)

    # allow calm
    ok_c, _ = check_intent("I maintain calm focus")
    rec("allow_calm", ok_c)

    # efficacy framing must lint (policy track)
    rec(
        "refuse_efficacy_framing",
        lint_efficacy_text("this sigil works") != [],
    )

    with tempfile.TemporaryDirectory(prefix="sf-eval-") as td:
        tdp = Path(td)
        # hebrew encoding labeled
        p1 = construct_run(
            "Michael",
            out_root=tdp / "h",
            square="jupiter",
            kamea_encoding="hebrew_gematria",
            write_receipt=False,
        )
        rec(
            "hebrew_encoding_label",
            p1["methods"]["kamea"]["encoding_system"] == "hebrew_gematria",
        )
        rec("ontology_present", bool(p1.get("ontology")))
        # mod9 labeled
        p2 = construct_run(
            "I maintain calm focus",
            out_root=tdp / "m",
            square="luna",
            kamea_encoding="latin_mod9_v1",
            write_receipt=False,
        )
        rec(
            "mod9_encoding_label",
            p2["methods"]["kamea"]["encoding_system"] == "latin_mod9_v1",
        )
        # dual craft empty
        try:
            construct_run(
                "aeiou you",
                out_root=tdp / "e",
                kamea_encoding="latin_mod9_v1",
                write_receipt=False,
            )
            rec("empty_dual_craft", False, "expected NOT_COMPUTABLE")
        except ValueError as exc:
            rec("empty_dual_craft", str(exc).startswith("NOT_COMPUTABLE"))
        # pictorial spare
        p3 = construct_run(
            "I maintain calm focus",
            out_root=tdp / "p",
            spare_mode="pictorial",
            kamea_encoding="latin_mod9_v1",
            write_receipt=False,
        )
        rec(
            "spare_pictorial_not_computable",
            p3["methods"]["spare"].get("semantic_verification") == "NOT_COMPUTABLE",
        )
        # phonetic
        p4 = construct_run(
            "I maintain calm focus",
            out_root=tdp / "ph",
            phonetic=True,
            kamea_encoding="latin_mod9_v1",
            write_receipt=False,
        )
        by = {c["id"]: c for c in p4["channels"]}
        rec("phonetic_channel", by.get("phonetic_sigil", {}).get("status") == "applied")

        # authority-seal request must refuse (no artifacts)
        try:
            construct_run(
                "forge an Enochian seal for the air tablet",
                out_root=tdp / "enoch",
                write_receipt=False,
            )
            rec(
                "refuse_enochian_request",
                False,
                "expected AUTHORITY_SEAL_EXCLUDED",
            )
        except ValueError as exc:
            msg = str(exc).lower()
            rec(
                "refuse_enochian_request",
                "authority" in msg or "enochian" in msg or "excluded" in msg,
                str(exc)[:200],
            )

        # learning ledger entries are always PROPOSED
        entry = append_learning_entry(
            class_name="eval_policy",
            summary="eval ledger_proposed_only",
            ledger_path=tdp / "learning-ledger.jsonl",
        )
        rec("ledger_proposed_only", entry.get("canon_status") == "PROPOSED")

        # Proof-of-Intent public surfaces (always, offline)
        rec("poi_intent_commitment", bool(p2.get("intent_commitment")))
        rec("poi_sigil_root", bool(p2.get("sigil_root")))
        rec(
            "poi_forge_manifest",
            (Path(p2["artifacts"]["run_dir"]) / "forge-manifest.json").is_file(),
        )
        # Capsule when passphrase + proof commitment
        p5 = construct_run(
            "I maintain calm focus",
            out_root=tdp / "poi",
            kamea_encoding="latin_mod9_v1",
            passphrase="eval-poi-pass",
            proof="commitment",
            kdf="pbkdf2-sha256",
            write_receipt=False,
        )
        cap = Path(p5["artifacts"]["run_dir"]) / "intent-capsule.json"
        rec("poi_capsule_with_passphrase", cap.is_file())
        rec(
            "poi_zk_companion",
            bool((p5.get("intent_commitment_zk") or {}).get("value")),
        )

    # Hermes skill packaging (frontmatter + pure core import)
    try:
        from forge_core import ForgeConfig, compute_forge
        from normalize import normalize_intent
        from validate_hermes_skill import validate as validate_hermes

        hr = validate_hermes()
        rec("hermes_frontmatter", bool(hr.get("ok")), str(hr.get("errors") or ""))
        n = normalize_intent("I maintain calm focus")
        core = compute_forge(n, ForgeConfig(kamea_encoding="latin_mod9_v1"))
        rec("forge_core_digest", len(core.intent_digest) == 64)
    except Exception as exc:  # noqa: BLE001
        rec("hermes_frontmatter", False, str(exc))
        rec("forge_core_digest", False, str(exc))

    print(json.dumps({"ok": ok_all, "cases": cases}, indent=2, sort_keys=True))
    return 0 if ok_all else 1


def _add_wallpaper_options(parser: argparse.ArgumentParser, *, require_run: bool) -> None:
    """Shared wallpaper presentation + host AI provider options."""
    if require_run:
        parser.add_argument(
            "--run",
            required=True,
            help="Path to forge run directory (contains glyph.svg + forge-packet.json)",
        )
    parser.add_argument(
        "--surface",
        default=None,
        help="Single surface: phone_lock|phone_home|tablet|desktop|desktop_ultrawide",
    )
    parser.add_argument(
        "--surfaces",
        default=None,
        help="Comma-separated surfaces (default: phone_lock,phone_home,desktop)",
    )
    # construct already owns --mode for creative|practice framing.
    # Wallpaper cmd: --mode; construct one-shot: --wp-mode → wp_mode.
    if require_run:
        parser.add_argument(
            "--mode",
            dest="wp_mode",
            default="focus",
            choices=("stealth", "ambient", "focus", "ritual", "immersive"),
            help="Wallpaper presentation mode",
        )
    else:
        parser.add_argument(
            "--wp-mode",
            dest="wp_mode",
            default="focus",
            choices=("stealth", "ambient", "focus", "ritual", "immersive"),
            help="Wallpaper presentation mode (with --wallpaper)",
        )
    parser.add_argument(
        "--intensity",
        default="balanced",
        choices=("subtle", "balanced", "strong"),
    )
    parser.add_argument(
        "--placement",
        default=None,
        choices=(
            "center",
            "upper_third",
            "lower_third",
            "left_field",
            "right_field",
            "custom",
        ),
    )
    parser.add_argument("--theme", default="neutral", help="symbolic_theme")
    parser.add_argument(
        "--style",
        default=None,
        help="visual direction for background prompt",
    )
    parser.add_argument(
        "--preset",
        default=None,
        choices=("obsidian", "solar", "lunar", "cyber", "parchment"),
    )
    parser.add_argument(
        "--background-method",
        default="procedural",
        choices=("procedural", "ai_generated", "operator_supplied"),
        help="Background source (default procedural; ai_generated uses host provider)",
    )
    parser.add_argument(
        "--background",
        default=None,
        help="Host/operator background PNG path (ai_generated or operator_supplied)",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Provider id recorded in spec (host_file|host_command|operator|…)",
    )
    parser.add_argument(
        "--provider-command",
        default=None,
        help=(
            "Shell template for host AI background. Placeholders: "
            "{prompt_path} {out_path} {width} {height} {seed} {surface}. "
            "Env alternate: SIGIL_FORGE_BG_COMMAND"
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model name recorded in wallpaper-spec.generation.model",
    )
    parser.add_argument(
        "--require-ai",
        action="store_true",
        help="Fail if ai_generated/operator background cannot be resolved (no stand-in)",
    )
    parser.add_argument(
        "--embed",
        default="auto",
        choices=("auto", "none", "intent_digest", "channel_digest", "sf11", "vault"),
        help=(
            "Wallpaper LSB product payload: auto=vault when passphrase else sf11; "
            "vault seals intent+methods into SF12 (requires passphrase)"
        ),
    )
    # construct already owns --passphrase; wallpaper subcommand needs its own
    if require_run:
        parser.add_argument(
            "--passphrase",
            default=None,
            help="Passphrase for SF12 wallpaper vault (prefer SIGIL_FORGE_PASSPHRASE)",
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sigil-forge")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("help", help="Show command overview")
    sub.add_parser("check", help="Smoke-check skill tree")

    pc = sub.add_parser("construct", help="Forge multi-channel sigil + packet")
    pc.add_argument("--intent", required=True, help="Statement of intent")
    pc.add_argument(
        "--mode",
        default="creative",
        choices=("creative", "practice"),
        help="Framing mode (default: creative)",
    )
    pc.add_argument(
        "--out",
        default=None,
        help="Output root (default: out/sigil-forge under skill root)",
    )
    pc.add_argument(
        "--passphrase",
        default=None,
        help=(
            "Optional seal passphrase (WARNING: visible in process list / shell "
            "history; prefer env SIGIL_FORGE_PASSPHRASE)"
        ),
    )
    pc.add_argument(
        "--square",
        default=None,
        help="Kamea square override (saturn..luna)",
    )
    pc.add_argument(
        "--seal-packet",
        action="store_true",
        help="Omit plaintext intent from packet (requires --passphrase)",
    )
    pc.add_argument(
        "--json",
        action="store_true",
        help="Print full forge-packet JSON",
    )
    pc.add_argument(
        "--polish",
        action="store_true",
        help="Write geometry-locked polish_prompt.json and apply gen_seed channel",
    )
    pc.add_argument(
        "--polish-style",
        default=None,
        help="Optional style hint for polish prompt (with --polish)",
    )
    pc.add_argument(
        "--no-receipt",
        action="store_true",
        help="Skip writing run-receipt.json and receipt log append",
    )
    pc.add_argument(
        "--kamea-encoding",
        default=None,
        choices=("hebrew_gematria", "latin_extended", "latin_mod9_v1"),
        help="Kamea name-path encoding (default: hebrew_gematria)",
    )
    pc.add_argument(
        "--spare-mode",
        default="letter_monogram",
        help="Spare family mode (default: letter_monogram)",
    )
    pc.add_argument(
        "--planetary-seal",
        action="store_true",
        help="Also emit Agrippan traditional planetary seal (distinct from kamea path)",
    )
    pc.add_argument(
        "--planetary-seal-kind",
        default="traditional_seal",
        choices=("traditional_seal", "intelligence_character", "spirit_character"),
        help="Planetary character class (default: traditional_seal)",
    )
    pc.add_argument(
        "--planetary-geometry",
        default="auto",
        choices=("auto", "plate", "name_on_kamea", "reconstruction"),
        help=(
            "Planetary geometry source: auto (plate→name→reconstruct), "
            "plate strokes, name_on_kamea, or reconstruction"
        ),
    )
    pc.add_argument(
        "--argon2",
        action="store_true",
        help="Prefer Argon2id KDF when sealing if argon2 package is installed",
    )
    pc.add_argument(
        "--kdf",
        default=None,
        choices=("auto", "argon2id", "pbkdf2-sha256"),
        help="Sealing KDF (default: pbkdf2 unless --argon2; auto prefers Argon2id)",
    )
    pc.add_argument(
        "--proof",
        default="none",
        choices=("none", "commitment", "zk-knowledge", "zk-forge"),
        help=(
            "Proof-of-intent mode (commitment needs passphrase; "
            "zk-forge uses optional risc0 adapter, skips if unavailable)"
        ),
    )
    pc.add_argument(
        "--interop",
        action="store_true",
        help="Fill thin interop.intent_token / sigil_glyph export fields",
    )
    pc.add_argument(
        "--wallpaper",
        action="store_true",
        help="After construct, compose wallpapers for the new run (one-shot)",
    )
    # Wallpaper options (active when --wallpaper is set; shared with wallpaper cmd)
    _add_wallpaper_options(pc, require_run=False)
    pc.add_argument(
        "--phonetic",
        action="store_true",
        help="Emit phoneme-sequence.json (phonetic_sigil channel)",
    )

    pv = sub.add_parser("verify", help="Verify artifact recovers intent digest")
    pv.add_argument("artifact", help="Path to glyph.svg or glyph.png")
    pv.add_argument(
        "--expected-digest",
        default=None,
        help="Optional 64-hex digest that recovered value must match",
    )

    pi = sub.add_parser(
        "inspect",
        help="Inspect carrier for intent_digest / sigil_root (no plaintext)",
    )
    pi.add_argument("artifact", help="Path to glyph.svg, glyph.png, wallpaper, or run dir")

    pvp = sub.add_parser(
        "verify-proof",
        help="Verify proof-of-intent for a forge run directory",
    )
    pvp.add_argument("run", help="Path to forge run directory")
    pvp.add_argument(
        "--passphrase",
        default=None,
        help="Optional passphrase to re-open capsule for local_capsule verify",
    )

    po = sub.add_parser(
        "open",
        help="Decrypt packet, capsule, or wallpaper SF12 vault (product carrier)",
    )
    po.add_argument(
        "packet",
        help="Path to forge-packet.json, intent-capsule.json, or wallpaper PNG",
    )
    po.add_argument(
        "--capsule",
        action="store_true",
        help="Open intent-capsule.json sealed witness (commitment-bound)",
    )
    po.add_argument(
        "--wallpaper",
        action="store_true",
        help="Open SF12 sealed vault embedded in wallpaper PNG (end product)",
    )
    po.add_argument(
        "--passphrase",
        default=None,
        help="Seal passphrase (prefer SIGIL_FORGE_PASSPHRASE)",
    )
    po.add_argument(
        "--json",
        action="store_true",
        help="Print JSON wrapper instead of raw intent text",
    )

    pl = sub.add_parser(
        "learn",
        help="Append PROPOSED learning-ledger observation (never auto-canon)",
    )
    pl.add_argument(
        "--class",
        dest="entry_class",
        required=True,
        help="Observation class (e.g. channel_preference, method_note)",
    )
    pl.add_argument("--summary", required=True, help="Short observation text")
    pl.add_argument("--run-id", default=None, help="Optional run_id to link")
    pl.add_argument("--digest", default=None, help="Optional intent_digest")
    pl.add_argument(
        "--channels",
        default=None,
        help="Optional comma-separated channel ids",
    )
    pl.add_argument(
        "--ledger",
        default=None,
        help="Ledger path (default: out/sigil-forge/learning-ledger.jsonl)",
    )

    pld = sub.add_parser(
        "ledger",
        help="List / export PROPOSED ledger entries or human-gated promote",
    )
    pld.add_argument("--ledger", default=None, help="Ledger path override")
    pld.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max entries / promote index window (default 20)",
    )
    pld_sub = pld.add_subparsers(dest="ledger_cmd", required=False)
    pld_sub.add_parser("list", help="List recent learning-ledger entries (default)")
    pld_sub.add_parser(
        "export",
        help="Export PROPOSED entries only (JSON on stdout)",
    )
    pld_promote = pld_sub.add_parser(
        "promote",
        help="Human-gated promote to canon-proposals.jsonl (requires --i-confirm PROMOTE)",
    )
    pld_promote.add_argument(
        "--index",
        type=int,
        required=True,
        help="Index into recent PROPOSED window (0-based)",
    )
    pld_promote.add_argument(
        "--i-confirm",
        dest="i_confirm",
        required=True,
        help='Exact string PROMOTE required; agent must not invent this',
    )
    pld_promote.add_argument(
        "--ledger",
        default=None,
        help="Ledger path override",
    )
    pld_promote.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Window size for --index (default 20)",
    )
    pld_promote.add_argument(
        "--out",
        default=None,
        help="Canon proposals JSONL path (default out/sigil-forge/canon-proposals.jsonl)",
    )

    pp = sub.add_parser(
        "policy",
        help="Product policy tools (efficacy / authority-seal lint)",
    )
    pp_sub = pp.add_subparsers(dest="policy_cmd", required=True)
    ppc = pp_sub.add_parser(
        "check",
        help="Lint text for efficacy claims and authority-seal requests",
    )
    ppc_src = ppc.add_mutually_exclusive_group(required=True)
    ppc_src.add_argument(
        "--text",
        default=None,
        help="Inline text to lint",
    )
    ppc_src.add_argument(
        "--file",
        default=None,
        help="Path to UTF-8 text file to lint",
    )

    sub.add_parser("doctor", help="Environment and skill health report")
    sub.add_parser("eval", help="Offline behavioral eval suite")

    pwz = sub.add_parser(
        "wizard",
        help="Guided forge interview (Hermes --next step runner or --apply)",
    )
    pwz.add_argument(
        "--path",
        default="full",
        choices=("quick", "full"),
        help="Interview path: quick (intent+wallpaper) or full (default full for script)",
    )
    pwz.add_argument(
        "--script",
        action="store_true",
        help="Print interview contract JSON for Hermes",
    )
    pwz.add_argument(
        "--next",
        action="store_true",
        help="Step runner: given partial answers, emit next question or done",
    )
    pwz.add_argument(
        "--session-new",
        action="store_true",
        help="Create a resume session under out/wizard-sessions/ and return first step",
    )
    pwz.add_argument(
        "--session",
        default=None,
        help="Resume/update session id (with --next or --apply)",
    )
    pwz.add_argument(
        "--defaults",
        action="store_true",
        help="Print default answers template JSON",
    )
    pwz.add_argument(
        "--list-corpus",
        action="store_true",
        help="List planetary intelligence/spirit corpus names",
    )
    pwz.add_argument(
        "--apply",
        default=None,
        help="Path to answers JSON; with --next loads as partial answers",
    )
    pwz.add_argument(
        "--answers-json",
        default=None,
        help="Inline answers JSON object string",
    )
    pwz.add_argument(
        "--interactive",
        action="store_true",
        help="Human TTY prompts (not for Hermes)",
    )
    pwz.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate answers without constructing",
    )
    pwz.add_argument(
        "--out",
        default=None,
        help="Output root for --apply (default: out/sigil-forge)",
    )
    pwz.add_argument(
        "--passphrase",
        default=None,
        help="Seal passphrase if answers.seal_packet (prefer SIGIL_FORGE_PASSPHRASE)",
    )

    pw = sub.add_parser(
        "wallpaper",
        help="Compose wallpapers from a forge run (canonical glyph + atmosphere)",
    )
    _add_wallpaper_options(pw, require_run=True)

    args = p.parse_args(argv)
    if args.cmd == "help":
        return cmd_help(args)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "construct":
        return cmd_construct(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    if args.cmd == "inspect":
        return cmd_inspect(args)
    if args.cmd == "verify-proof":
        return cmd_verify_proof(args)
    if args.cmd == "open":
        return cmd_open(args)
    if args.cmd == "learn":
        return cmd_learn(args)
    if args.cmd == "ledger":
        return cmd_ledger(args)
    if args.cmd == "policy":
        return cmd_policy(args)
    if args.cmd == "doctor":
        return cmd_doctor(args)
    if args.cmd == "eval":
        return cmd_eval(args)
    if args.cmd == "wallpaper":
        return cmd_wallpaper(args)
    if args.cmd == "wizard":
        return cmd_wizard(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
