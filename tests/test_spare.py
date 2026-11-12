from sigil_forge.spare import reduce_letters, letter_sequence
from sigil_forge.normalize import normalize_intent


def test_classic_reduction_drops_vowels_and_dupes():
    n = normalize_intent("I maintain calm focus")
    # i m a i n t a i n c a l m f o c u s
    # letters only, no vowels, first occurrence: m n t c l f s
    assert reduce_letters(n) == "mntclfs"


def test_letter_sequence_matches_reduce():
    n = normalize_intent("It is my will to remain calm")
    assert "".join(letter_sequence(n)) == reduce_letters(n)


def test_all_vowels_yields_empty():
    assert reduce_letters(normalize_intent("aeiou you")) == ""
