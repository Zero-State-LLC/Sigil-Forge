from sigil_forge.kamea import letter_to_number, select_square, plot_path, KAMEA_SQUARES


def test_saturn_square_is_3x3_magic():
    s = KAMEA_SQUARES["saturn"]
    assert len(s) == 3 and all(len(r) == 3 for r in s)
    assert sorted(x for row in s for x in row) == list(range(1, 10))


def test_letter_to_number_agrippa():
    assert letter_to_number("a") == 1
    assert letter_to_number("j") == 1
    assert letter_to_number("t") == 2


def test_select_square_override():
    assert select_square("abc", override="mars") == "mars"


def test_select_square_from_digest():
    name = select_square("00" * 32)
    assert name in KAMEA_SQUARES


def test_plot_path_nonempty():
    pts = plot_path(list("mntclfs"), "saturn")
    assert len(pts) >= 1
    assert all(len(p) == 2 for p in pts)
