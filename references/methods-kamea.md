# Methods: Kamea (planetary magic squares)

Version: **v0.4** — pluggable encodings with provenance

## Planetary tables

| Key | Planet | Order | Magic constant |
|-----|--------|-------|----------------|
| `saturn` | Saturn | 3×3 | 15 |
| `jupiter` | Jupiter | 4×4 | 34 |
| `mars` | Mars | 5×5 | 65 |
| `sol` | Sol/Sun | 6×6 | 111 |
| `venus` | Venus | 7×7 | 175 |
| `mercury` | Mercury | 8×8 | 260 |
| `luna` | Luna | 9×9 | 369 |

Tables are hardcoded Agrippa/Western placements in `src/sigil_forge/kamea.py`.

## Encodings (required provenance)

Default for name-derived paths: **`hebrew_gematria`**.

| Encoding id | Meaning | Historical status |
|-------------|---------|-------------------|
| `hebrew_gematria` | Latin→Hebrew minimal transliteration; absolute gematria; reduce into 1..n² | historically_aligned (default) |
| `latin_extended` | A=1..Z=26 then reduce into square | modern_adaptation |
| `latin_mod9_v1` | Legacy A–Z → 1–9 only (compatibility) | **not** full Agrippan fidelity |

### latin_mod9_v1 (legacy)

```
1: A J S   2: B K T   …   9: I R
```

Only cells 1–9 can appear. Preserved for reproducibility; do **not** market as complete Agrippan name-path practice.

### hebrew_gematria (default)

1. Transliterate latin → Hebrew (documented digraph map in code).
2. Assign traditional gematria values (א=1 … ת=400).
3. Reduce each value into 1..n² via digit-sum / range mod (`reduction_operations[]`).
4. Plot path through those cells.

### Provenance fields (always on packet)

```text
encoding_system
transliteration_system
original_numeric_sequence
reduced_numeric_sequence
reduction_operations[]
square
path
claimed_historical_status
```

CLI:

```bash
python3 scripts/sigil_forge.py construct \
  --intent "Michael" --square jupiter \
  --kamea-encoding hebrew_gematria --out out/sf

python3 scripts/sigil_forge.py construct \
  --intent "…" --kamea-encoding latin_mod9_v1 --out out/sf
```

## Kamea path vs planetary seal

| Artifact | Class | Construction |
|----------|-------|--------------|
| `kamea_path` | name_path | Intent/name letters → numbers → cells |
| `planetary_seal` | planetary_character | Connect 1→n² on the table (Agrippan seal reconstruction) |

Use `--planetary-seal` for the latter; never treat them as interchangeable.
