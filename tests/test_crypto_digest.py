from sigil_forge.crypto_payload import intent_digest
from sigil_forge.normalize import normalize_intent


def test_digest_stable():
    n = normalize_intent("I maintain calm focus")
    d1 = intent_digest(n)
    d2 = intent_digest(n)
    assert d1 == d2
    assert len(d1) == 64
    assert d1 == d1.lower()


def test_digest_changes_with_intent():
    a = intent_digest(normalize_intent("alpha intent here"))
    b = intent_digest(normalize_intent("beta intent here"))
    assert a != b
