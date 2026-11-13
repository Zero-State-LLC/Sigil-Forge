"""Storyboard: an ordered set of ordinary forge runs, an index, and a sheet.

Each intent ("frame") is forged by ``construct.run`` unchanged. Two files tie
the runs together, both under ``<out_root>/storyboards/``:

- ``storyboard-<board_id>.json``, the index: public digests only.
- ``storyboard-<board_id>.svg``, the sheet: one SVG that embeds every frame's
  ``glyph.svg`` byte for byte, in order. It is a carrier for the whole board:
  each embedded glyph still holds its own digest and root, so the board can
  be checked from the sheet alone, without the run folders or the index.

Neither file holds plaintext intent, normalized intent, a commitment nonce or
a passphrase. ``board_root`` commits to the ordered frames (digest, root and
glyph bytes), so reordering, swapping or editing a frame changes it.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import shutil
import stat
import tempfile
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
ROOT_DOMAIN = "sigil-forge-storyboard-root/1"
SHEET_VERSION = 1
SHEET_CELL = 100  # one frame's square, in sheet units
SHEET_GAP = 6
SHEET_MAX_COLUMNS = 4
# Limits for reading a sheet or index someone else may have written.
MAX_SHEET_BYTES = 8 * 1024 * 1024
MAX_FRAME_SVG_BYTES = 512 * 1024
MAX_INDEX_BYTES = 256 * 1024
_HEX64 = re.compile(r"[0-9a-f]{64}")
_HEX16 = re.compile(r"[0-9a-f]{16}")
_RUN_DIR = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_BOARD_META = re.compile(r"<sf:board>([A-Za-z0-9+/=]{1,65536})</sf:board>")
_FRAME_IMAGE = re.compile(
    r'<image data-sf-frame="(\d{1,2})" [^<>]*?href="data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)"/>'
)


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


def board_id_for(intent_digests: list[str]) -> str:
    """Board id: hash of the ordered intent digests (order matters)."""
    return hashlib.sha256("\n".join(intent_digests).encode("utf-8")).hexdigest()[:16]


def board_root_for(frames: list[dict[str, Any]]) -> str:
    """Commitment to the ordered frames: digest, root and exact glyph bytes."""
    canon = [
        [int(f["index"]), f["intent_digest"], f["sigil_root"], f["glyph_sha256"]] for f in frames
    ]
    blob = ROOT_DOMAIN + "\n" + json.dumps(canon, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_sheet_svg(board_id: str, board_root: str, frames: list[dict[str, Any]], glyphs: list[bytes]) -> str:
    """One SVG holding every frame's glyph, byte for byte, in a grid.

    Each glyph is embedded as a base64 ``data:`` image, so its own stego
    channels survive untouched and it can be taken back out and verified.
    """
    n = len(frames)
    cols = min(SHEET_MAX_COLUMNS, math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)
    step = SHEET_CELL + SHEET_GAP
    width = cols * step + SHEET_GAP
    height = rows * step + SHEET_GAP
    meta = {
        "v": SHEET_VERSION,
        "board_id": board_id,
        "board_root": board_root,
        "frames": [
            {"i": f["index"], "d": f["intent_digest"], "r": f["sigil_root"], "g": f["glyph_sha256"]}
            for f in frames
        ],
    }
    payload = base64.b64encode(
        json.dumps(meta, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    lines = [
        '<svg xmlns:sf="https://sigil-forge.local/ns" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="100%" height="100%">',
        "  <metadata>",
        f"    <sf:board>{payload}</sf:board>",
        "  </metadata>",
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#f7f4ef"/>',
    ]
    for k, (frame, glyph) in enumerate(zip(frames, glyphs)):
        x = SHEET_GAP + (k % cols) * step
        y = SHEET_GAP + (k // cols) * step
        data = base64.b64encode(glyph).decode("ascii")
        lines.append(
            f'  <image data-sf-frame="{frame["index"]}" x="{x}" y="{y}" '
            f'width="{SHEET_CELL}" height="{SHEET_CELL}" '
            f'href="data:image/svg+xml;base64,{data}"/>'
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


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

    # Run folders already here are never removed by rollback, even if a run in
    # the same clock second reuses one's name.
    existed_before = {p.name for p in root.iterdir() if p.is_dir()}
    created: list[Path] = []
    # path -> what was there before this call (None: nothing), for rollback
    previous: dict[Path, bytes | None] = {}
    made_sb_dir: Path | None = None
    glyphs: list[bytes] = []
    frames: list[dict[str, Any]] = []
    try:
        for i, intent in enumerate(intents, start=1):
            packet = construct.run(intent, out_root=root, **construct_kwargs)
            run_dir = Path(packet["artifacts"]["run_dir"])
            if run_dir.name not in existed_before:
                created.append(run_dir)
            glyph = (run_dir / "glyph.svg").read_bytes()
            glyphs.append(glyph)
            frames.append(
                {
                    "index": i,
                    "run_id": packet["artifacts"]["run_id"],
                    "run_dir": run_dir.relative_to(root).as_posix(),
                    "intent_digest": packet["intent_digest"],
                    "sigil_root": packet.get("sigil_root"),
                    "glyph_sha256": hashlib.sha256(glyph).hexdigest(),
                }
            )
        board_id = board_id_for([f["intent_digest"] for f in frames])
        board_root = board_root_for(frames)
        sheet = build_sheet_svg(board_id, board_root, frames, glyphs)
        sb_dir = root / "storyboards"
        if not sb_dir.exists():
            made_sb_dir = sb_dir
        if default_location:
            ensure_private_dir(sb_dir)
        else:
            sb_dir.mkdir(parents=True, exist_ok=True)
        sheet_path = sb_dir / f"storyboard-{board_id}.svg"
        index_path = sb_dir / f"storyboard-{board_id}.json"
        index = {
            "schema": SCHEMA,
            "board_id": board_id,
            "board_root": board_root,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "forge_version": _forge_version(),
            "frames": frames,
            "sheet": {
                "path": sheet_path.name,
                "sha256": hashlib.sha256(sheet.encode("utf-8")).hexdigest(),
            },
        }
        # Re-running the same intents replaces that board's two files. Keep
        # what was there so a failure puts the earlier board back intact.
        for target in (sheet_path, index_path):
            previous[target] = target.read_bytes() if target.is_file() else None
        write_private_text(sheet_path, sheet)
        write_private_text(
            index_path, json.dumps(index, indent=2, sort_keys=True) + "\n"
        )
    except BaseException:
        for d in created:
            shutil.rmtree(d, ignore_errors=True)
        for target, before in previous.items():
            try:
                if before is None:
                    target.unlink(missing_ok=True)
                else:
                    write_private_text(target, before.decode("utf-8"))
            except OSError:
                pass
        if made_sb_dir is not None:
            try:
                made_sb_dir.rmdir()  # only if this call made it and it is empty
            except OSError:
                pass
        raise
    return {**index, "index_path": str(index_path), "sheet_path": str(sheet_path)}


# ---------------------------------------------------------------- verification


def _read_regular(path: Path, limit: int) -> bytes:
    """Read at most ``limit`` bytes of a regular file, without following a link.

    Refuses symlinks, FIFOs, devices and anything larger than ``limit``. The
    checks are made on the opened file, so nothing can be swapped in between
    the check and the read, and a FIFO cannot block the caller.
    """
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    if path.is_symlink():
        raise OSError("symlink")
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise OSError("not a regular file")
        if info.st_size > limit:
            raise OSError("larger than the limit")
        chunks, total = [], 0
        while total <= limit:
            chunk = os.read(fd, min(1 << 16, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total > limit:
            raise OSError("larger than the limit")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _why(exc: Exception) -> str:
    """Our own refusal text, or just the error's class: never a path or file content."""
    if isinstance(exc, OSError) and exc.errno is None and exc.args:
        return str(exc.args[0])
    return type(exc).__name__


def _result(source: Path, kind: str) -> dict[str, Any]:
    return {
        "ok": False,
        "source": str(source),
        "kind": kind,
        "board_id": None,
        "board_root": None,
        "anchored": False,
        "frame_count": 0,
        "frames": [],
        "detail": "",
    }


def _verify_glyph_bytes(glyph: bytes, work: Path, index: int) -> dict[str, Any]:
    """Run the ordinary glyph verifier on embedded or on-disk glyph bytes."""
    from sigil_forge.verify import run as verify_run

    path = work / f"frame-{int(index):02d}.svg"
    path.write_bytes(glyph)
    try:
        got = verify_run(path)
    except (ValueError, OSError, KeyError, TypeError):
        # Not UTF-8, not SVG, or otherwise unreadable as a glyph.
        got = {}
    return {
        "index": index,
        "ok": bool(got.get("ok")),
        "intent_digest": got.get("intent_digest"),
        "sigil_root": got.get("sigil_root"),
        "glyph_sha256": hashlib.sha256(glyph).hexdigest(),
    }


def _check_board(out: dict[str, Any], frames: list[dict[str, Any]], claimed: dict[str, Any]) -> list[str]:
    """Recompute id and root from verified frames and compare with what was claimed."""
    problems = [f"frame {f['index']}: glyph does not verify" for f in frames if not f["ok"]]
    if any(not f["intent_digest"] or not f["sigil_root"] for f in frames):
        problems.append("a frame carries no digest or no root")
        return problems
    digests = [f["intent_digest"] for f in frames]
    if len(set(digests)) != len(digests):
        problems.append("the same frame appears twice")
    out["board_id"] = board_id_for(digests)
    out["board_root"] = board_root_for(frames)
    if claimed.get("board_id") != out["board_id"]:
        problems.append("board_id does not match the frames")
    if claimed.get("board_root") is not None and claimed["board_root"] != out["board_root"]:
        problems.append("board_root does not match the frames")
    return problems


def _check_expected(out: dict[str, Any], expected_root: str | None) -> list[str]:
    """Compare with a root the caller got from somewhere they trust."""
    if expected_root is None:
        return []
    if not isinstance(expected_root, str) or not _HEX64.fullmatch(expected_root.lower()):
        return ["expected root is not 64 hex characters"]
    if out["board_root"] != expected_root.lower():
        return ["board_root is not the expected root"]
    out["anchored"] = True
    return []


def verify_sheet(sheet_path: Path | str, *, expected_root: str | None = None) -> dict[str, Any]:
    """Check a storyboard sheet on its own: no index, no run folders needed.

    A sheet must be exactly what ``build_sheet_svg`` writes for its frames.
    Anything else in the file (a comment hiding the frames, an extra image
    drawn over them, a script) makes it differ and fails, so what a viewer
    shows is what was checked.
    """
    path = Path(sheet_path)
    out = _result(path, "sheet")
    try:
        text = _read_regular(path, MAX_SHEET_BYTES).decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        out["detail"] = f"cannot read sheet: {_why(exc)}"
        return out

    metas = _BOARD_META.findall(text)
    images = _FRAME_IMAGE.findall(text)
    if len(metas) != 1:
        out["detail"] = "sheet must hold exactly one board record"
        return out
    if not (MIN_FRAMES <= len(images) <= MAX_FRAMES) or text.count("<image") != len(images):
        out["detail"] = f"sheet must hold {MIN_FRAMES} to {MAX_FRAMES} well-formed frame images"
        return out
    try:
        meta = json.loads(base64.b64decode(metas[0], validate=True))
        claimed_frames = meta["frames"]
        if not isinstance(meta, dict) or meta.get("v") != SHEET_VERSION:
            raise ValueError("unsupported board record")
        if not isinstance(claimed_frames, list):
            raise ValueError("unsupported board record")
        glyphs = []
        for k, (number, data) in enumerate(images, start=1):
            if int(number) != k:
                raise ValueError("frames are not numbered in order")
            if len(data) > MAX_FRAME_SVG_BYTES * 4 // 3 + 4:
                raise ValueError("an embedded frame is larger than the limit")
            glyphs.append(base64.b64decode(data, validate=True))
    except (ValueError, KeyError, TypeError) as exc:
        out["detail"] = f"malformed sheet: {exc}"
        return out

    with tempfile.TemporaryDirectory(prefix="sigil-forge-sheet-") as tmp:
        frames = [_verify_glyph_bytes(g, Path(tmp), k) for k, g in enumerate(glyphs, start=1)]
    out["frames"] = frames
    out["frame_count"] = len(frames)
    problems = _check_board(out, frames, meta)
    if len(claimed_frames) != len(frames):
        problems.append("board record lists a different number of frames")
    else:
        for f, c in zip(frames, claimed_frames):
            if not isinstance(c, dict) or (c.get("i"), c.get("d"), c.get("r"), c.get("g")) != (
                f["index"], f["intent_digest"], f["sigil_root"], f["glyph_sha256"],
            ):
                problems.append(f"frame {f['index']}: board record does not match the embedded glyph")
    if meta.get("board_root") is None:
        problems.append("board record has no board_root")
    if not problems:
        canonical = build_sheet_svg(out["board_id"], out["board_root"], frames, glyphs)
        if text != canonical:
            problems.append("sheet holds content beyond its frames and record")
    if not problems:
        problems += _check_expected(out, expected_root)
    out["detail"] = "; ".join(problems) or "ok"
    out["ok"] = not problems
    return out


def verify_index(index_path: Path | str, *, expected_root: str | None = None) -> dict[str, Any]:
    """Check a storyboard index against its run folders and, if present, its sheet.

    The index is treated as untrusted input: run folders must be plain names
    beside the ``storyboards`` folder, never absolute paths or ``..``.
    """
    path = Path(index_path)
    out = _result(path, "index")
    try:
        index = json.loads(_read_regular(path, MAX_INDEX_BYTES).decode("utf-8"))
        if not isinstance(index, dict):
            raise ValueError("not a storyboard index")
        listed = index["frames"]
        if index.get("schema") != SCHEMA or not isinstance(listed, list):
            raise ValueError("not a storyboard index")
        if not (MIN_FRAMES <= len(listed) <= MAX_FRAMES):
            raise ValueError("frame count out of range")
        for k, f in enumerate(listed, start=1):
            # ``type(...) is int``: 1.0 and True both equal 1 and must not pass.
            if not isinstance(f, dict) or type(f.get("index")) is not int or f["index"] != k:
                raise ValueError("frames are not numbered in order")
            if not isinstance(f.get("run_dir"), str) or not _RUN_DIR.fullmatch(f["run_dir"]):
                raise ValueError(f"frame {k}: run_dir is not a plain folder name")
            for key in ("intent_digest", "sigil_root"):
                if not isinstance(f.get(key), str) or not _HEX64.fullmatch(f[key]):
                    raise ValueError(f"frame {k}: {key} is not a digest")
        if not isinstance(index.get("board_id"), str) or not _HEX16.fullmatch(index["board_id"]):
            raise ValueError("board_id is malformed")
    except (OSError, UnicodeDecodeError) as exc:
        out["detail"] = f"cannot read index: {_why(exc)}"
        return out
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        out["detail"] = f"malformed index: {exc}"
        return out

    root = path.resolve().parent.parent
    problems: list[str] = []
    frames: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="sigil-forge-board-") as tmp:
        for f in listed:
            k = f["index"]
            glyph_path = root / f["run_dir"] / "glyph.svg"
            try:
                if (root / f["run_dir"]).is_symlink():
                    raise OSError("symlink")
                glyph = _read_regular(glyph_path, MAX_FRAME_SVG_BYTES)
            except OSError:
                problems.append(f"frame {k}: glyph.svg is missing or unreadable")
                frames.append({"index": k, "ok": False, "intent_digest": None,
                               "sigil_root": None, "glyph_sha256": None})
                continue
            got = _verify_glyph_bytes(glyph, Path(tmp), k)
            frames.append(got)
            for key in ("intent_digest", "sigil_root"):
                if got[key] != f[key]:
                    problems.append(f"frame {k}: {key} differs from the index")
            if f.get("glyph_sha256") is not None and got["glyph_sha256"] != f["glyph_sha256"]:
                problems.append(f"frame {k}: glyph.svg changed since the index was written")
    out["frames"] = frames
    out["frame_count"] = len(frames)
    if not any(f["intent_digest"] is None for f in frames):
        problems += _check_board(out, frames, index)
    legacy = index.get("board_root") is None
    out["legacy_index"] = legacy
    sheet = index.get("sheet")
    if isinstance(sheet, dict):
        name = sheet.get("path")
        if not isinstance(name, str) or name != f"storyboard-{index['board_id']}.svg":
            problems.append("index names an unexpected sheet file")
        else:
            sheet_path = path.parent / name
            try:
                actual = hashlib.sha256(_read_regular(sheet_path, MAX_SHEET_BYTES)).hexdigest()
            except OSError:
                problems.append("sheet is missing or unreadable")
            else:
                if actual != sheet.get("sha256"):
                    problems.append("sheet changed since the index was written")
                got_sheet = verify_sheet(sheet_path)
                if not got_sheet["ok"]:
                    problems.append(f"sheet does not verify: {got_sheet['detail']}")
                elif got_sheet["board_root"] != out["board_root"]:
                    problems.append("sheet and run folders disagree on board_root")
    elif sheet is not None:
        problems.append("index names an unexpected sheet file")
    elif not legacy:
        problems.append("index has a board_root but names no sheet")
    if legacy and expected_root is not None:
        problems.append("index has no board_root, so it cannot match an expected root")
    elif not problems:
        problems += _check_expected(out, expected_root)
    out["detail"] = "; ".join(problems) or (
        "ok (index written before board_root existed: frames checked, no root to compare)"
        if legacy else "ok"
    )
    out["ok"] = not problems
    return out


def verify_storyboard(path: Path | str, *, expected_root: str | None = None) -> dict[str, Any]:
    """Verify a storyboard from its index (``.json``) or its sheet (``.svg``).

    Without ``expected_root`` this proves the board is internally consistent:
    its frames belong together and are unchanged since it was written. It does
    not prove it is the board a particular person made, because anyone can
    build a new consistent board. Pass the ``board_root`` you were given
    through a channel you trust to prove that; the result then has
    ``anchored: true``.
    """
    p = Path(path)
    if not p.exists():
        out = _result(p, "unknown")
        out["detail"] = "file not found"
        return out
    is_sheet = p.suffix.lower() == ".svg"
    try:
        if is_sheet:
            return verify_sheet(p, expected_root=expected_root)
        return verify_index(p, expected_root=expected_root)
    except Exception as exc:  # noqa: BLE001 - untrusted input must never crash the verifier
        out = _result(p, "sheet" if is_sheet else "index")
        out["detail"] = f"verification error: {type(exc).__name__}"
        return out
