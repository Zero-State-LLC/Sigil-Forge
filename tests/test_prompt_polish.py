from sigil_forge.prompt_polish import build_prompt


def test_seed_from_digest():
    p = build_prompt(
        {"intent_digest": "abcd" * 16, "stroke_count": 2},
        style="ink on parchment",
    )
    assert p["seed"] == int("abcdabcd", 16)
    assert "geometry" in p["prompt"].lower() or "sigil" in p["prompt"].lower()
    assert "do not add text" in p["negative"].lower() or "text" in p["negative"].lower()


def test_build_prompt_keys_and_geometry_lock():
    summary = {
        "intent_digest": "deadbeef" + "0" * 56,
        "stroke_count": 3,
        "bbox": {"x": 10.0, "y": 12.0, "width": 80.0, "height": 76.0},
    }
    p = build_prompt(summary, style=None)
    assert set(p.keys()) >= {"prompt", "negative", "seed", "geometry_lock"}
    assert p["seed"] == int("deadbeef", 16)
    assert isinstance(p["geometry_lock"], str)
    assert "stroke" in p["geometry_lock"].lower()
    assert "3" in p["geometry_lock"]
    assert "bbox" in p["geometry_lock"].lower() or "10" in p["geometry_lock"]
    assert "ink" not in p["prompt"].lower() or "parchment" not in p["prompt"].lower()


def test_style_included_when_provided():
    p = build_prompt(
        {"intent_digest": "12345678" + "f" * 56, "stroke_count": 1},
        style="ink on parchment",
    )
    assert "ink on parchment" in p["prompt"].lower()
    assert p["seed"] == int("12345678", 16)


def test_no_api_side_effects():
    """Builder is pure: returns dict only, never calls image APIs."""
    p = build_prompt({"intent_digest": "a" * 64, "stroke_count": 0}, None)
    assert isinstance(p, dict)
    assert "http" not in p["prompt"].lower()
    assert "api" not in p["negative"].lower()
