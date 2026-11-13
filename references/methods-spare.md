# Methods: Spare family

Spare is a **method family**, not only vowel-stripping monograms.

| Mode | Determinism | Status |
|------|-------------|--------|
| `letter_monogram` | deterministic | **shipped** (default) |
| `pictorial` | assisted | registered, geometry deferred |
| `automatic_form` | assisted | registered, geometry deferred |
| `alphabet_of_desire` | corpus_backed | deferred |
| `phonetic_mantric` | assisted | registered, geometry deferred |
| `hybrid` | assisted | deferred |

## letter_monogram (default)

1. Keep a–z only  
2. Strip vowels `aeiouy`  
3. Unique first-seen order  
4. Place on a circle as monogram polyline  

CLI: `--spare-mode letter_monogram` (default).

## Assisted modes

`--spare-mode pictorial` (etc.) emits **digest-bound seed artifacts** with:

```yaml
determinism: assisted
semantic_verification: NOT_COMPUTABLE
```

They are **not** silent aliases of letter_monogram geometry.

## Authority

No efficacy claims. Proposal-only creative outputs.
