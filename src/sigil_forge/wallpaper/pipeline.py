"""Full forge-run → wallpaper pipeline (background env + immutable glyph composite)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wallpaper.composite import (
    composite_glyph_on_background,
    write_wallpaper_png,
)
from wallpaper.embed import embed_binding
from wallpaper.prompt import build_background_prompt
from wallpaper.providers import enrich_prompt_package, resolve_background
from wallpaper.seed import file_sha256
from wallpaper.spec import SCHEMA_VERSION, build_wallpaper_spec, load_forge_run
from wallpaper.verify_wallpaper import verify_wallpaper


def build_wallpaper(
    run_dir: Path | str,
    *,
    surface: str = "phone_lock",
    mode: str = "focus",
    intensity: str = "balanced",
    placement: str | None = None,
    symbolic_theme: str = "neutral",
    visual_direction: str = "dark architectural minimalism",
    style_preset: str | None = None,
    background_method: str = "procedural",
    background_path: Path | str | None = None,
    provider: str | None = None,
    provider_command: str | None = None,
    model: str | None = None,
    require_ai: bool = False,
    embedded_payload: str = "auto",
    out_name: str | None = None,
    passphrase: str | None = None,
    intent: str | None = None,
    kdf: str | None = "auto",
) -> dict[str, Any]:
    """Build one wallpaper for a surface from an existing forge run directory.

    **Product (v0.13):** the wallpaper PNG is the end deliverable. When a
    passphrase is available, intent + method provenance are sealed into SF12
    LSB vault (``embedded_payload=auto|vault``). Corpus geometry stays in the
    immutable glyph composite.

    Returns summary with paths and receipt status.
    """
    run_dir = Path(run_dir)
    forge = load_forge_run(run_dir)
    spec = build_wallpaper_spec(
        run_dir,
        surface=surface,
        mode=mode,
        intensity=intensity,
        placement=placement,
        symbolic_theme=symbolic_theme,
        visual_direction=visual_direction,
        background_method=background_method,
        embedded_payload=embedded_payload,
    )

    wp_dir = run_dir / "wallpaper"
    wp_dir.mkdir(parents=True, exist_ok=True)
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    w, h = spec["canvas"]["width"], spec["canvas"]["height"]
    seed = int(spec["generation"]["seed"])
    complexity = float(spec["presentation"]["background_complexity"])
    theme = str(spec["presentation"]["symbolic_theme"])

    # Prompts (for AI path; always written for provenance)
    prompt_pkg = build_background_prompt(spec, style_preset=style_preset)
    bg_role = f"background-{surface}"
    bg_file = wp_dir / f"background-{surface}.png"
    prompt_pkg = enrich_prompt_package(
        prompt_pkg,
        width=w,
        height=h,
        seed=seed,
        surface=surface,
        out_hint=str(bg_file),
    )
    prompt_path = wp_dir / f"background-prompt-{surface}.json"
    prompt_path.write_text(json.dumps(prompt_pkg, indent=2) + "\n", encoding="utf-8")
    spec["generation"]["prompt_path"] = str(prompt_path)

    # Background via offline procedural / operator / host AI provider
    bg = resolve_background(
        background_method=background_method,
        width=w,
        height=h,
        seed=seed,
        complexity=complexity,
        theme=theme,
        surface=surface,
        prompt_path=prompt_path,
        bg_file=bg_file,
        background_path=background_path,
        provider=provider,
        provider_command=provider_command,
        model=model,
        require_ai=require_ai,
    )
    rgb = bg.rgb
    spec["generation"]["background_method"] = bg.background_method
    spec["generation"]["provider"] = bg.provider
    spec["generation"]["model"] = bg.model
    if bg.command_ran:
        spec["generation"]["provider_command"] = bg.command_ran
    if bg.source_path:
        spec["generation"]["background_source"] = bg.source_path
    if bg.notes:
        spec.setdefault("notes", []).extend(bg.notes)

    bg_sha = write_wallpaper_png(bg_file, w, h, rgb)

    # Composite canonical glyph (immutable SVG paths → uniform transform)
    glyph_svg = forge["glyph_svg"].read_text(encoding="utf-8")
    # Privacy: ensure intent not in SVG text for scan baseline
    composed = composite_glyph_on_background(
        rgb,
        w,
        h,
        glyph_svg=glyph_svg,
        cx=float(spec["composition"]["x"]),
        cy=float(spec["composition"]["y"]),
        scale=float(spec["composition"]["scale"]),
        opacity=float(spec["presentation"]["glyph_opacity"]),
        glow=float(spec["presentation"].get("glow_strength") or 0),
    )

    out_name = out_name or f"{surface.replace('_', '-')}.png"
    out_file = wp_dir / out_name
    out_sha = write_wallpaper_png(out_file, w, h, composed)

    # Spec digest for embedding
    import hashlib

    spec_for_hash = {k: v for k, v in spec.items() if k != "artifacts"}
    spec_digest = hashlib.sha256(
        json.dumps(spec_for_hash, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    packet = forge["packet"]
    embed_mode = (spec["privacy"].get("embedded_payload") or embedded_payload or "auto")
    embed_mode = str(embed_mode).strip().lower()
    if embed_mode == "auto":
        # Product default: sealed vault when passphrase present, else SF11 public
        embed_mode = "vault" if passphrase else (
            "sf11" if packet.get("sigil_root") else "intent_digest"
        )

    sealed_blob = None
    vault_status = "skipped"
    if embed_mode == "vault":
        if not passphrase:
            vault_status = "failed_no_passphrase"
            # Fall back to public SF11 so wallpaper still binds digests
            embed_mode = "sf11" if packet.get("sigil_root") else "intent_digest"
        else:
            from wallpaper.vault import build_vault_document, seal_vault

            version = "0.0.0"
            try:
                from paths import skill_root

                vpath = skill_root() / "VERSION"
                if vpath.is_file():
                    version = vpath.read_text(encoding="utf-8").strip() or version
            except Exception:
                pass
            vault_doc = build_vault_document(
                packet=packet,
                intent=intent,
                wallpaper_spec=spec,
                wallpaper_spec_digest=spec_digest,
                skill_version=version,
            )
            sealed_blob = seal_vault(vault_doc, passphrase, kdf=kdf)
            vault_status = "sealed"

    emb = embed_binding(
        out_file,
        intent_digest=spec["source"]["intent_digest"],
        wallpaper_spec_digest=spec_digest,
        source_glyph_digest=spec["source"]["glyph_digest"],
        mode=embed_mode,
        sigil_root=packet.get("sigil_root"),
        sealed_blob=sealed_blob,
    )
    if emb:
        out_sha = emb
        if vault_status == "sealed":
            vault_status = "embedded"

    # Artifacts list
    artifacts = [
        {"role": bg_role, "path": str(bg_file), "sha256": bg_sha},
        {"role": f"wallpaper-{surface}", "path": str(out_file), "sha256": out_sha},
        {
            "role": "background_prompt",
            "path": str(prompt_path),
            "sha256": file_sha256(str(prompt_path)),
        },
    ]
    spec["artifacts"] = artifacts
    spec["privacy"]["embedded_payload"] = embed_mode
    spec["privacy"]["vault_status"] = vault_status
    spec["privacy"]["product"] = "wallpaper"

    spec_path = wp_dir / f"wallpaper-spec-{surface}.json"
    spec_path.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Forbidden phrases: normalized intent if present in packet
    forbidden = []
    ni = packet.get("normalized_intent")
    if ni and len(ni) >= 8:
        forbidden.append(ni)
    if intent and len(intent) >= 8:
        forbidden.append(intent)

    receipt = verify_wallpaper(
        spec=spec,
        output_path=out_file,
        background_path=bg_file,
        source_glyph_path=forge["glyph_svg"],
        forbidden_phrases=forbidden,
    )
    # Proof-of-Intent binding fields (additive; never plaintext intent)
    packet_ic = packet.get("intent_commitment") or {}
    if isinstance(packet_ic, dict):
        receipt["intent_commitment"] = packet_ic.get("value") or packet_ic.get(
            "commitment"
        )
    else:
        receipt["intent_commitment"] = None
    receipt["intent_digest"] = packet.get("intent_digest") or spec["source"].get(
        "intent_digest"
    )
    receipt["sigil_root"] = packet.get("sigil_root")
    receipt["embedded_payload"] = embed_mode
    receipt["vault_status"] = vault_status
    receipt["product"] = "wallpaper"
    if emb:
        receipt["output_digest"] = out_sha
        for a in artifacts:
            if a.get("role", "").startswith("wallpaper-"):
                a["sha256"] = out_sha

    receipt_path = receipts_dir / f"wallpaper-receipt-{surface}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "ok": receipt.get("status") == "verified",
        "surface": surface,
        "product": "wallpaper",
        "wallpaper": str(out_file),
        "background": str(bg_file),
        "background_method": bg.background_method,
        "provider": bg.provider,
        "prompt": str(prompt_path),
        "spec": str(spec_path),
        "receipt": str(receipt_path),
        "receipt_status": receipt.get("status"),
        "geometry_preserved": receipt.get("geometry_preserved"),
        "intent_commitment": receipt.get("intent_commitment"),
        "sigil_root": receipt.get("sigil_root"),
        "embedded_payload": embed_mode,
        "vault_status": vault_status,
        "notes": list(bg.notes),
        "schema_version": SCHEMA_VERSION,
    }



def build_wallpapers_for_run(
    run_dir: Path | str,
    surfaces: list[str] | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    surfaces = surfaces or ["phone_lock", "phone_home", "desktop"]
    return [build_wallpaper(run_dir, surface=s, **kwargs) for s in surfaces]
