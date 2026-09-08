"""Hermes-facing forge wizard — guided interview → construct kwargs.

Modes:
  - ``script``: interview contract (paths, steps, agent rules)
  - ``next``: step runner — partial answers → next question / done
  - ``validate`` / ``apply``: check answers JSON and run construct
  - ``session``: save/load resume files under out/wizard-sessions/
  - ``interactive``: human TTY prompts

Paths:
  - ``quick``: intent (+ optional mode/wallpaper) — defaults fill the rest
  - ``full``: complete interview

The skill stays offline-first; the wizard never invents geometry.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paths import default_out_dir, skill_root
from policy_lint import detect_authority_seal_request
from safety import check_intent

WIZARD_VERSION = "2.1.0"
PATHS = ("quick", "full")

# Ordered interview steps for Hermes agents and interactive CLI.
STEPS: list[dict[str, Any]] = [
    {
        "id": "intent",
        "prompt": (
            "State your intent in present tense (e.g. \"I maintain calm focus\"). "
            "Avoid harm, coercion, or empty noise."
        ),
        "type": "text",
        "required": True,
        "example": "I maintain calm focus while shipping",
        "help": (
            "Present-tense statements forge cleanly. Consonants matter for Spare "
            "reduction — all-vowel noise may be NOT_COMPUTABLE. No violence, "
            "self-harm, or non-consensual control."
        ),
        "why": "The intent is the only semantic input; everything else is craft encoding.",
        "skip_ok": False,
        "paths": ["quick", "full"],
    },
    {
        "id": "mode",
        "prompt": (
            "Framing mode: creative (default focus tool) or practice "
            "(practitioner tone, still no efficacy claims)."
        ),
        "type": "choice",
        "choices": ["creative", "practice"],
        "default": "creative",
        "help": (
            "Creative = journaling/habit cue language. Practice = personal-use "
            "tone. Construction geometry is identical either way."
        ),
        "why": "Tone only — never changes digests or channels.",
        "skip_ok": True,
        "paths": ["quick", "full"],
    },
    {
        "id": "kamea_encoding",
        "prompt": (
            "Kamea name-path encoding: hebrew_gematria (default, historically aligned), "
            "latin_extended, or latin_mod9_v1 (compatibility)."
        ),
        "type": "choice",
        "choices": ["hebrew_gematria", "latin_extended", "latin_mod9_v1"],
        "default": "hebrew_gematria",
        "help": (
            "hebrew_gematria maps letters via Hebrew values (best fidelity for names). "
            "latin_extended uses A=1..Z=26. latin_mod9_v1 is the old 1–9 digital map "
            "for compatibility only."
        ),
        "why": "Encoding is labeled in the packet so craft history stays honest.",
        "skip_ok": True,
        "paths": ["full"],
    },
    {
        "id": "square",
        "prompt": "Planetary kamea square (auto = digest-derived), or saturn..luna.",
        "type": "choice",
        "choices": [
            "auto",
            "saturn",
            "jupiter",
            "mars",
            "sol",
            "venus",
            "mercury",
            "luna",
        ],
        "default": "auto",
        "help": (
            "auto picks a square from the intent digest. Override when you want a "
            "specific planetary table (Saturn 3×3 … Luna 9×9)."
        ),
        "why": "Square size changes path geometry; still not an efficacy claim.",
        "skip_ok": True,
        "paths": ["full"],
    },
    {
        "id": "planetary_seal",
        "prompt": (
            "Optional planetary character (distinct from intent kamea path): "
            "none, traditional_seal, intelligence_character, or spirit_character."
        ),
        "type": "choice",
        "choices": [
            "none",
            "traditional_seal",
            "intelligence_character",
            "spirit_character",
        ],
        "default": "none",
        "help": (
            "none = skip. traditional_seal = successive path on the kamea (+ plate frame). "
            "intelligence/spirit = Agrippan named characters (plate strokes by default). "
            "Not Goetic or Enochian authority seals."
        ),
        "why": "Separate artifact class from the intent monogram/kamea path.",
        "skip_ok": True,
        "paths": ["full"],
    },
    {
        "id": "planetary_geometry",
        "prompt": (
            "Planetary geometry source: auto (plate → name_on_kamea → reconstruction), "
            "plate, name_on_kamea, or reconstruction."
        ),
        "type": "choice",
        "choices": ["auto", "plate", "name_on_kamea", "reconstruction"],
        "default": "auto",
        "help": (
            "plate = multi-stroke scholarly digitizations (default). "
            "name_on_kamea = draw the intelligence/spirit name on the square. "
            "reconstruction = simple successive/odds-evens fallbacks."
        ),
        "why": "Controls fidelity label in the packet provenance.",
        "skip_ok": True,
        "paths": ["full"],
        "when": {"planetary_seal": {"neq": "none"}},
    },
    {
        "id": "spare_mode",
        "prompt": "Spare family mode for intent compression.",
        "type": "choice",
        "choices": [
            "letter_monogram",
            "pictorial",
            "automatic_drawing",
            "mantric_alphabet",
            "phonetic_mantric",
        ],
        "default": "letter_monogram",
        "help": (
            "letter_monogram is the only fully geometry-computable default. "
            "pictorial/automatic_drawing are provenance-only (semantic NOT_COMPUTABLE). "
            "phonetic_mantric pairs with the phonetic carrier."
        ),
        "why": "Spare family is multi-method; we refuse to fake freehand geometry.",
        "skip_ok": True,
        "paths": ["full"],
    },
    {
        "id": "phonetic",
        "prompt": "Also emit phoneme-sequence JSON carrier?",
        "type": "bool",
        "default": False,
        "help": "Optional mantric/phonetic channel JSON — not audio synthesis.",
        "why": "Parallel carrier for spoken forms; skip unless you want it.",
        "skip_ok": True,
        "paths": ["full"],
    },
    {
        "id": "polish",
        "prompt": "Write geometry-locked polish_prompt.json for host image tools?",
        "type": "bool",
        "default": False,
        "help": (
            "Does not call an image API. Writes a prompt package so a host tool "
            "may restyle atmosphere only — master glyph stays verify source."
        ),
        "why": "Optional aesthetics handoff; offline forge does not need it.",
        "skip_ok": True,
        "paths": ["full"],
    },
    {
        "id": "wallpaper",
        "prompt": "Compose a device wallpaper after forge (immutable glyph + atmosphere)?",
        "type": "bool",
        "default": False,
        "help": (
            "Composites the canonical glyph over procedural (or host AI) atmosphere. "
            "Never AI-redraws the sigil topology."
        ),
        "why": "Presentation carrier — optional.",
        "skip_ok": True,
        "paths": ["quick", "full"],
    },
    {
        "id": "wp_surface",
        "prompt": "Wallpaper surface (if wallpaper=yes).",
        "type": "choice",
        "choices": [
            "phone_lock",
            "phone_home",
            "tablet",
            "desktop",
            "desktop_ultrawide",
        ],
        "default": "phone_lock",
        "help": "Device canvas + safe zones (clock/icons).",
        "why": "Layout is surface-aware, not a naive crop.",
        "skip_ok": True,
        "paths": ["quick", "full"],
        "when": {"wallpaper": True},
    },
    {
        "id": "wp_mode",
        "prompt": "Wallpaper presentation mode.",
        "type": "choice",
        "choices": ["stealth", "ambient", "focus", "ritual", "immersive"],
        "default": "focus",
        "help": "Controls glyph opacity/scale emphasis (stealth quieter, immersive stronger).",
        "why": "Presentation intensity only.",
        "skip_ok": True,
        "paths": ["quick", "full"],
        "when": {"wallpaper": True},
    },
    {
        "id": "wp_theme",
        "prompt": "Wallpaper symbolic theme (e.g. mercurial, lunar, neutral).",
        "type": "text",
        "default": "neutral",
        "help": "Atmosphere bias for procedural/AI background (saturnine, jovian, mercurial, …).",
        "why": "Background mood — not the glyph geometry.",
        "skip_ok": True,
        "paths": ["quick", "full"],
        "when": {"wallpaper": True},
    },
    {
        "id": "seal_packet",
        "prompt": "Seal plaintext intent out of the public packet? (requires passphrase env)",
        "type": "bool",
        "default": False,
        "help": (
            "If yes, set SIGIL_FORGE_PASSPHRASE (prefer env over --passphrase). "
            "Public glyph still holds digest only."
        ),
        "why": "Privacy for operators who want ciphertext in the packet.",
        "skip_ok": True,
        "paths": ["full"],
    },
    {
        "id": "proof",
        "prompt": (
            "Proof-of-Intent mode? (none = commitment+root only; "
            "commitment = sealed capsule; zk-knowledge = optional Noir + local attestation)"
        ),
        "type": "choice",
        "choices": ["none", "commitment", "zk-knowledge", "zk-forge"],
        "default": "none",
        "help": (
            "Provenance only — not efficacy. commitment/zk-knowledge need "
            "SIGIL_FORGE_PASSPHRASE for the intent capsule. zk-forge skips if "
            "risc0 guest unavailable. See references/proof-of-intent.md."
        ),
        "why": "Optional privacy binding + optional knowledge attestation.",
        "skip_ok": True,
        "paths": ["full"],
    },
    {
        "id": "kdf",
        "prompt": "Key derivation for seal/capsule (auto prefers Argon2id when installed).",
        "type": "choice",
        "choices": ["auto", "argon2id", "pbkdf2-sha256"],
        "default": "auto",
        "help": "auto → Argon2id if argon2-cffi present, else PBKDF2. Offline-safe either way.",
        "why": "Seal strength policy; does not change glyph geometry.",
        "skip_ok": True,
        "paths": ["full"],
        "when": {
            # ask when sealing packet or any proof mode that needs a capsule
            "_poi_or_seal": True,
        },
    },
]


def _normalize_path(path: str | None) -> str:
    p = (path or "full").strip().lower()
    if p not in PATHS:
        raise ValueError(f"unknown path {path!r}; allowed: {', '.join(PATHS)}")
    return p


def steps_for_path(path: str = "full") -> list[dict[str, Any]]:
    p = _normalize_path(path)
    if p == "quick":
        return [s for s in STEPS if "quick" in (s.get("paths") or [])]
    # full: every step that lists full (all craft steps do)
    return [s for s in STEPS if "full" in (s.get("paths") or ["full"])]


def wizard_script(path: str = "full") -> dict[str, Any]:
    """Agent-facing interview script (Hermes reads this and asks the user)."""
    p = _normalize_path(path)
    return {
        "wizard_version": WIZARD_VERSION,
        "skill": "sigil-forge",
        "path": p,
        "paths": {
            "quick": "intent + optional mode/wallpaper; defaults fill the rest",
            "full": "complete interview (expert options)",
        },
        "purpose": (
            "Guide an operator from intent to a verified multi-channel sigil "
            "without inventing geometry or claiming efficacy."
        ),
        "agent_rules": [
            "Use wizard --next as the step runner: one question per turn.",
            "Default path is quick for new users; full only if they want craft options.",
            "After each user answer, merge into answers and call --next again.",
            "When next.done is true, run wizard --apply (or offer verify after apply).",
            "Run safety on intent early; refuse harmful intents with no artifacts.",
            "Never invent monogram/kamea paths — only call scripts via construct/wizard apply.",
            "Do not claim the sigil works or replaces professional help.",
            "Wallpapers never AI-redraw the canonical glyph.",
            "Load references/wizard.md only when guiding; progressive disclosure.",
            "Proof-of-Intent: load references/proof-of-intent.md when proof!=none; "
            "never put commitment nonce in public media; no efficacy claims.",
        ],
        "loop": {
            "start": "python3 scripts/sigil_forge.py wizard --next --path quick",
            "continue": (
                "python3 scripts/sigil_forge.py wizard --next --path quick "
                "--answers-json '{...}'  # or --session ID"
            ),
            "finish": (
                "python3 scripts/sigil_forge.py wizard --apply answers.json "
                "--out out/sigil-forge"
            ),
        },
        "steps": steps_for_path(p),
        "apply": {
            "cli": "python3 scripts/sigil_forge.py wizard --apply answers.json --out out/sigil-forge",
            "answers_schema": "flat object keyed by step id; optional path field",
        },
        "defaults_template": default_answers(),
        "session": {
            "create": "python3 scripts/sigil_forge.py wizard --session-new --path quick",
            "dir": "out/wizard-sessions/",
        },
    }


def default_answers() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for step in STEPS:
        if "default" in step:
            out[step["id"]] = step["default"]
    return out


def _coerce_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(v)


def _when_match(got: Any, need: Any) -> bool:
    """Evaluate when clause value. Supports eq (default) and {neq: x}."""
    if isinstance(need, dict):
        if "neq" in need:
            return got != need["neq"]
        if "eq" in need:
            return got == need["eq"]
        return False
    if isinstance(need, bool):
        return _coerce_bool(got) is need
    return got == need


def _step_active(step: dict[str, Any], answers: dict[str, Any]) -> bool:
    when = step.get("when")
    if not when:
        return True
    for k, need in when.items():
        # Synthetic: kdf only when seal or proof needs passphrase material
        if k == "_poi_or_seal":
            seal = _coerce_bool(answers.get("seal_packet"))
            proof = (answers.get("proof") or "none").strip().lower()
            needs = seal or proof in ("commitment", "zk-knowledge")
            if need and not needs:
                return False
            if not need and needs:
                return False
            continue
        if not _when_match(answers.get(k), need):
            return False
    return True


def _merged_view(raw: dict[str, Any] | None) -> dict[str, Any]:
    return {**default_answers(), **(raw or {})}


def _answered(step: dict[str, Any], answers: dict[str, Any]) -> bool:
    sid = step["id"]
    if sid not in answers:
        return False
    val = answers[sid]
    if val is None:
        return False
    if isinstance(val, str) and val.strip() == "" and step.get("required"):
        return False
    return True


def active_steps(answers: dict[str, Any] | None = None, path: str = "full") -> list[dict[str, Any]]:
    view = _merged_view(answers)
    return [s for s in steps_for_path(path) if _step_active(s, view)]


def next_step(
    answers: dict[str, Any] | None = None,
    *,
    path: str = "full",
) -> dict[str, Any]:
    """Return the next unanswered active step, or done payload.

    Early safety: if intent is present and fails check_intent, return refused.
    """
    p = _normalize_path(path)
    raw = dict(answers or {})
    # Strip non-answer keys
    raw.pop("path", None)
    raw.pop("session_id", None)

    intent = (raw.get("intent") or "").strip()
    if intent:
        ok_s, reason = check_intent(intent)
        if not ok_s:
            return {
                "ok": False,
                "done": True,
                "refused": True,
                "phase": "safety",
                "error": f"safety: {reason}",
                "path": p,
                "wizard_version": WIZARD_VERSION,
                "answers": raw,
                "agent_instruction": (
                    "Refuse clearly. Do not construct. No artifacts. Offer to rewrite intent."
                ),
            }
        hit, fam = detect_authority_seal_request(intent)
        if hit:
            return {
                "ok": False,
                "done": True,
                "refused": True,
                "phase": "authority_policy",
                "error": f"AUTHORITY_SEAL_EXCLUDED family={fam or 'authority_seal'}",
                "path": p,
                "wizard_version": WIZARD_VERSION,
                "answers": raw,
                "agent_instruction": (
                    "Refuse. Do not construct. Explain intent-sigil vs authority-seal. "
                    "Point to distinction-enochian.md. Offer a present-tense intent rewrite."
                ),
            }

    steps = active_steps(raw, p)
    total = len(steps)
    answered_ids = [s["id"] for s in steps if _answered(s, raw)]
    pending = [s for s in steps if not _answered(s, raw)]

    progress = {
        "answered": len(answered_ids),
        "total_active": total,
        "answered_ids": answered_ids,
        "remaining_ids": [s["id"] for s in pending],
        "percent": int(round(100.0 * len(answered_ids) / total)) if total else 100,
    }

    if not pending:
        # Fill defaults for remaining inactive / skipped
        filled = validate_answers(raw, path=p)
        return {
            "ok": filled["ok"],
            "done": True,
            "refused": False,
            "path": p,
            "wizard_version": WIZARD_VERSION,
            "progress": progress,
            "answers": filled["answers"],
            "errors": filled.get("errors") or [],
            "warnings": filled.get("warnings") or [],
            "agent_instruction": (
                "Interview complete. Confirm summary with user if helpful, then "
                "run wizard --apply (save answers JSON first)."
            ),
            "apply_hint": (
                "python3 scripts/sigil_forge.py wizard --apply answers.json --out out/sigil-forge"
            ),
        }

    step = pending[0]
    public_step = {
        k: step[k]
        for k in (
            "id",
            "prompt",
            "type",
            "choices",
            "default",
            "example",
            "help",
            "why",
            "skip_ok",
            "required",
        )
        if k in step
    }
    return {
        "ok": True,
        "done": False,
        "refused": False,
        "path": p,
        "wizard_version": WIZARD_VERSION,
        "progress": progress,
        "step": public_step,
        "suggested_default": step.get("default"),
        "can_skip": bool(step.get("skip_ok", True)) and not step.get("required"),
        "answers_so_far": raw,
        "agent_instruction": (
            f"Ask the user ONLY about step '{step['id']}'. Use prompt + help. "
            "Do not ask multiple questions. After they answer, merge into answers "
            "and call wizard --next again."
        ),
    }


def validate_answers(
    raw: dict[str, Any] | None,
    *,
    path: str = "full",
) -> dict[str, Any]:
    """Validate and normalize wizard answers. Returns {ok, answers, errors, warnings}."""
    p = _normalize_path(path if path else (raw or {}).get("path") or "full")
    raw = dict(raw or {})
    raw.pop("path", None)
    raw.pop("session_id", None)
    errors: list[str] = []
    warnings: list[str] = []
    answers: dict[str, Any] = {}

    # Progressive activation over path steps
    for step in steps_for_path(p):
        view = {**default_answers(), **raw, **answers}
        if not _step_active(step, view):
            continue
        sid = step["id"]
        if sid not in raw or raw[sid] in (None, ""):
            if step.get("required"):
                errors.append(f"missing required: {sid}")
                continue
            if "default" in step:
                answers[sid] = step["default"]
            continue
        val = raw[sid]
        if step["type"] == "bool":
            answers[sid] = _coerce_bool(val)
        elif step["type"] == "choice":
            s = str(val).strip()
            if s not in step["choices"]:
                errors.append(f"{sid}: {s!r} not in {step['choices']}")
            else:
                answers[sid] = s
        else:
            answers[sid] = str(val).strip()

    # Fill defaults for any full-path fields not in quick path so construct works
    for step in STEPS:
        sid = step["id"]
        if sid not in answers and "default" in step:
            answers[sid] = step["default"]

    # Drop inactive conditional fields from effective answers view
    merged = {**default_answers(), **answers}
    for step in STEPS:
        if not _step_active(step, merged):
            # keep defaults for construct kwargs mapping but note inactive
            pass

    intent = (answers.get("intent") or raw.get("intent") or "").strip()
    if intent:
        ok_s, reason = check_intent(intent)
        if not ok_s:
            errors.append(f"safety: {reason}")
        answers["intent"] = intent
    elif any(s.get("required") and s["id"] == "intent" for s in STEPS):
        if "missing required: intent" not in errors:
            errors.append("missing required: intent")

    # If planetary_seal is none, force geometry default
    if answers.get("planetary_seal", "none") == "none":
        answers["planetary_geometry"] = "auto"

    return {
        "ok": not errors,
        "answers": answers,
        "errors": errors,
        "warnings": warnings,
        "path": p,
        "wizard_version": WIZARD_VERSION,
    }


def answers_to_construct_kwargs(answers: dict[str, Any]) -> dict[str, Any]:
    """Map wizard answers to construct.run kwargs (+ wallpaper flags)."""
    seal_kind = answers.get("planetary_seal") or "none"
    planetary = seal_kind != "none"
    square = answers.get("square") or "auto"
    proof = (answers.get("proof") or "none").strip().lower()
    if proof not in ("none", "commitment", "zk-knowledge", "zk-forge"):
        proof = "none"
    kdf = (answers.get("kdf") or "auto").strip().lower()
    if kdf not in ("auto", "argon2id", "pbkdf2-sha256"):
        kdf = "auto"
    kwargs: dict[str, Any] = {
        "mode": answers.get("mode") or "creative",
        "kamea_encoding": answers.get("kamea_encoding") or "hebrew_gematria",
        "spare_mode": answers.get("spare_mode") or "letter_monogram",
        "planetary_seal": planetary,
        "planetary_seal_kind": seal_kind if planetary else "traditional_seal",
        "planetary_geometry": answers.get("planetary_geometry") or "auto",
        "phonetic": bool(answers.get("phonetic")),
        "write_polish": bool(answers.get("polish")),
        "seal_packet": bool(answers.get("seal_packet")),
        "square": None if square in (None, "", "auto") else square,
        "proof": proof,
        "kdf": kdf,
    }
    wallpaper = {
        "enabled": bool(answers.get("wallpaper")),
        "surface": answers.get("wp_surface") or "phone_lock",
        "mode": answers.get("wp_mode") or "focus",
        "theme": answers.get("wp_theme") or "neutral",
    }
    return {"intent": answers["intent"], "construct": kwargs, "wallpaper": wallpaper}


def apply_answers(
    answers: dict[str, Any],
    *,
    out_root: Path | str | None = None,
    passphrase: str | None = None,
    path: str = "full",
) -> dict[str, Any]:
    """Validate answers, construct forge packet, optional wallpaper."""
    from construct import resolve_passphrase, run as construct_run

    report = validate_answers(answers, path=path)
    if not report["ok"]:
        return {"ok": False, "phase": "validate", **report}

    mapped = answers_to_construct_kwargs(report["answers"])
    intent = mapped["intent"]
    ck = mapped["construct"]
    proof_mode = (ck.get("proof") or "none").strip().lower()
    needs_pass = bool(ck.get("seal_packet")) or proof_mode in (
        "commitment",
        "zk-knowledge",
    )
    if needs_pass:
        pp = resolve_passphrase(passphrase)
        if not pp:
            need = "seal_packet" if ck.get("seal_packet") else f"proof={proof_mode}"
            return {
                "ok": False,
                "phase": "validate",
                "errors": [
                    f"{need} requires --passphrase or SIGIL_FORGE_PASSPHRASE"
                ],
                "answers": report["answers"],
            }
        ck = {**ck, "passphrase": pp}
    elif passphrase:
        ck = {**ck, "passphrase": resolve_passphrase(passphrase)}

    try:
        packet = construct_run(
            intent,
            out_root=Path(out_root) if out_root else None,
            **ck,
        )
    except (ValueError, RuntimeError) as exc:
        return {
            "ok": False,
            "phase": "construct",
            "error": str(exc),
            "answers": report["answers"],
        }

    result: dict[str, Any] = {
        "ok": True,
        "phase": "construct",
        "path": report.get("path"),
        "answers": report["answers"],
        "intent_digest": packet.get("intent_digest"),
        "intent_commitment": packet.get("intent_commitment"),
        "sigil_root": packet.get("sigil_root"),
        "proof": packet.get("proof"),
        "run_id": (packet.get("artifacts") or {}).get("run_id"),
        "run_dir": (packet.get("artifacts") or {}).get("run_dir"),
        "svg": (packet.get("artifacts") or {}).get("svg"),
        "packet_path": (packet.get("artifacts") or {}).get("packet_json"),
        "intent_capsule": (packet.get("artifacts") or {}).get("intent_capsule"),
        "channels_applied": [
            c["id"]
            for c in packet.get("channels", [])
            if c.get("status") == "applied"
        ],
    }

    wp = mapped["wallpaper"]
    if wp.get("enabled"):
        from wallpaper.pipeline import build_wallpaper

        run_dir = packet.get("artifacts", {}).get("run_dir")
        try:
            wr = build_wallpaper(
                Path(run_dir),
                surface=wp["surface"],
                mode=wp["mode"],
                symbolic_theme=wp["theme"],
                background_method="procedural",
            )
            result["wallpaper"] = wr
            if not wr.get("ok"):
                result["ok"] = False
                result["phase"] = "wallpaper"
                result["error"] = "wallpaper verification failed"
        except Exception as exc:  # noqa: BLE001
            result["ok"] = False
            result["phase"] = "wallpaper"
            result["error"] = str(exc)

    result["next"] = [
        f"python3 scripts/sigil_forge.py verify {result.get('svg')}",
        "Review forge-packet.json methods + ontology for provenance",
    ]
    if result.get("svg"):
        result["next"].append(
            f"python3 scripts/sigil_forge.py inspect {result.get('svg')}"
        )
    if result.get("intent_capsule"):
        result["next"].append(
            "python3 scripts/sigil_forge.py open --capsule "
            f"{result['intent_capsule']} --json"
        )
    if result.get("run_dir") and proof_mode in ("commitment", "zk-knowledge"):
        result["next"].append(
            f"python3 scripts/sigil_forge.py verify-proof {result['run_dir']}"
        )
    return result


def interactive_answers(
    stdin=None,
    stdout=None,
    *,
    path: str = "full",
) -> dict[str, Any]:
    """Prompt a human on TTY; returns raw answers dict."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    p = _normalize_path(path)
    answers: dict[str, Any] = {}
    stdout.write(f"Sigil-Forge wizard [{p}] (Ctrl+C to abort)\n")
    stdout.write("Methods are craft + encoding — no efficacy claims.\n")
    stdout.write("Press Enter to accept defaults. Type 'done' after intent to use defaults.\n\n")
    while True:
        nxt = next_step(answers, path=p)
        if nxt.get("refused"):
            stdout.write(f"Refused: {nxt.get('error')}\n")
            return answers
        if nxt.get("done"):
            break
        step = nxt["step"]
        if step.get("help"):
            stdout.write(f"  ({step['help']})\n")
        default = step.get("default", "")
        hint = ""
        if step["type"] == "choice":
            hint = f" [{'|'.join(step['choices'])}]"
        elif step["type"] == "bool":
            hint = " [y/N]" if not default else " [Y/n]"
        if default not in ("", None) and step["type"] != "bool":
            prompt = f"{step['prompt']}{hint} (default: {default}): "
        else:
            prompt = f"{step['prompt']}{hint}: "
        stdout.write(prompt)
        stdout.flush()
        line = stdin.readline()
        if line == "":
            break
        line = line.strip()
        if line.lower() == "done" and answers.get("intent"):
            # Accept defaults for remaining
            break
        if not line and "default" in step:
            answers[step["id"]] = step["default"]
            continue
        if not line and step.get("required"):
            stdout.write("  required — try again\n")
            continue
        if step["type"] == "bool":
            if not line:
                answers[step["id"]] = bool(default)
            else:
                answers[step["id"]] = line.lower() in ("y", "yes", "1", "true")
        else:
            answers[step["id"]] = line
    return answers


def load_answers_file(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("answers file must be a JSON object")
    if "answers" in data and isinstance(data["answers"], dict):
        return data["answers"]
    return data


# --- Sessions -----------------------------------------------------------------

def session_dir() -> Path:
    d = default_out_dir().parent / "wizard-sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_session_id(session_id: str) -> str:
    s = (session_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{4,64}", s):
        raise ValueError("session id must be 4–64 chars [A-Za-z0-9_-]")
    return s


def session_path(session_id: str) -> Path:
    return session_dir() / f"{_safe_session_id(session_id)}.json"


def create_session(path: str = "quick") -> dict[str, Any]:
    p = _normalize_path(path)
    sid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    doc = {
        "session_id": sid,
        "wizard_version": WIZARD_VERSION,
        "path": p,
        "answers": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    session_path(sid).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def load_session(session_id: str) -> dict[str, Any]:
    sp = session_path(session_id)
    if not sp.is_file():
        # Read legacy package sessions without deleting or moving operator data.
        from paths import skill_root
        legacy = skill_root() / "out" / "wizard-sessions" / f"{_safe_session_id(session_id)}.json"
        if legacy.is_file():
            sp = legacy
    if not sp.is_file():
        raise FileNotFoundError(f"session not found: {session_id}")
    data = json.loads(sp.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("corrupt session file")
    return data


def save_session(
    session_id: str,
    answers: dict[str, Any],
    *,
    path: str | None = None,
) -> dict[str, Any]:
    try:
        doc = load_session(session_id)
    except FileNotFoundError:
        doc = {
            "session_id": _safe_session_id(session_id),
            "wizard_version": WIZARD_VERSION,
            "path": _normalize_path(path or "full"),
            "answers": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    doc["answers"] = dict(answers)
    if path:
        doc["path"] = _normalize_path(path)
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    doc["wizard_version"] = WIZARD_VERSION
    session_path(doc["session_id"]).write_text(
        json.dumps(doc, indent=2) + "\n", encoding="utf-8"
    )
    return doc


def session_next(
    session_id: str,
    *,
    merge_answers: dict[str, Any] | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """Load session, merge answers, compute next, persist."""
    doc = load_session(session_id)
    answers = dict(doc.get("answers") or {})
    if merge_answers:
        answers.update(merge_answers)
    p = _normalize_path(path or doc.get("path") or "full")
    doc = save_session(session_id, answers, path=p)
    nxt = next_step(answers, path=p)
    nxt["session_id"] = doc["session_id"]
    nxt["session_path"] = str(session_path(doc["session_id"]))
    return nxt
