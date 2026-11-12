"""Storyboard: an ordered set of ordinary forge runs plus a public index.

Each intent ("frame") is forged by ``construct.run`` unchanged. The index
(``<out_root>/storyboards/storyboard-<board_id>.json``) ties the runs together
and holds public digests only: no plaintext intent, no normalized intent, no
commitment nonce, no passphrase.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sigil_forge import construct
from sigil_forge.normalize import normalize_intent
from sigil_forge.ontology import assert_not_entity_seal_request
from sigil_forge.paths import (
    default_out_dir,
    ensure_private_dir,
    skill_root,
    write_private_text,
)
from sigil_forge.safety import check_intent

SCHEMA = "sigil-forge-storyboard/1"
MIN_FRAMES = 1
MAX_FRAMES = 12


class StoryboardUsageError(ValueError):
    """Bad storyboard input (frame count, empty or duplicate intent)."""


def _precheck(intents: list[str]) -> None:
    """Refuse the whole board before anything is written.

    Applies exactly the checks ``construct.run`` applies, by calling the same
    functions (``check_intent`` then ``assert_not_entity_seal_request``).
    The refusal keeps construct's own error type and message; only a frame
    index prefix is added. The intent text is never echoed by this module.
    """
    if not (MIN_FRAMES <= len(intents) <= MAX_FRAMES):
        raise StoryboardUsageError(
            f"storyboard needs {MIN_FRAMES} to {MAX_FRAMES} intents, got {len(intents)}"
        )
    seen: dict[str, int] = {}
    for i, intent in enumerate(intents, start=1):
        if not isinstance(intent, str) or not intent.strip():
            raise StoryboardUsageError(f"frame {i}: intent is empty")
        ok, reason = check_intent(intent)
        if not ok:
            raise ValueError(f"frame {i}: {reason or 'refused: harmful intent'}")
        try:
            assert_not_entity_seal_request(intent)
        except ValueError as exc:
            raise ValueError(f"frame {i}: {exc}") from None
        norm = normalize_intent(intent)  # same normalization construct uses
        if norm in seen:
            raise StoryboardUsageError(
                f"frame {i}: duplicates frame {seen[norm]} (same intent twice)"
            )
        seen[norm] = i


def _forge_version() -> str:
    vpath = skill_root() / "VERSION"
    if vpath.is_file():
        return vpath.read_text(encoding="utf-8").strip() or "0.0.0"
    return "0.0.0"


def build_storyboard(
    intents: list[str],
    *,
    out_root: Path | None = None,
    **construct_kwargs: Any,
) -> dict[str, Any]:
    """Forge one run per intent and write a public index; return the index dict.

    All-or-nothing: every intent is checked first and a refusal anywhere
    aborts with nothing on disk. If a later frame fails for another reason,
    the run dirs this call created are removed and no index is written.

    Re-running the same storyboard overwrites the index for its ``board_id``
    (derived from the ordered intent digests); the runs get new run ids as
    usual, so the index then points at the newest runs.
    """
    intents = list(intents)
    _precheck(intents)

    if out_root is None:
        root = ensure_private_dir(default_out_dir())
        default_location = True
    else:
        root = Path(out_root)
        root.mkdir(parents=True, exist_ok=True)
        default_location = False
    construct_kwargs.pop("out_root", None)

    created: list[Path] = []
    frames: list[dict[str, Any]] = []
    try:
        for i, intent in enumerate(intents, start=1):
            packet = construct.run(intent, out_root=root, **construct_kwargs)
            run_dir = Path(packet["artifacts"]["run_dir"])
            created.append(run_dir)
            frames.append(
                {
                    "index": i,
                    "run_id": packet["artifacts"]["run_id"],
                    "run_dir": run_dir.relative_to(root).as_posix(),
                    "intent_digest": packet["intent_digest"],
                    "sigil_root": packet.get("sigil_root"),
                }
            )
        board_id = hashlib.sha256(
            "\n".join(f["intent_digest"] for f in frames).encode("utf-8")
        ).hexdigest()[:16]
        index = {
            "schema": SCHEMA,
            "board_id": board_id,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "forge_version": _forge_version(),
            "frames": frames,
        }
        sb_dir = root / "storyboards"
        if default_location:
            ensure_private_dir(sb_dir)
        else:
            sb_dir.mkdir(parents=True, exist_ok=True)
        index_path = sb_dir / f"storyboard-{board_id}.json"
        write_private_text(
            index_path, json.dumps(index, indent=2, sort_keys=True) + "\n"
        )
    except BaseException:
        for d in created:
            shutil.rmtree(d, ignore_errors=True)
        raise
    return {**index, "index_path": str(index_path)}
