# Channels and steganography (v0.3)

Version: **v0.3** fixed channel set (unbounded research per run is a non-goal).

Every successful forge **attempts all channels** below. Each is recorded in the
forge packet as:

```json
{ "id": "<channel_id>", "status": "applied" | "skipped", "detail": "..." }
```

Order in `src/sigil_forge/construct.py` (`_CHANNEL_ORDER`):

1. `spare_monogram`  
2. `kamea_path`  
3. `kamea_square_choice`  
4. `bind_runes`  
5. `rose_cross_path`  
6. `planetary_seal` (opt-in)  
7. `intent_digest`  
8. `intent_commitment`  
9. `optional_ciphertext`  
10. `svg_metadata`  
11. `path_epsilon`  
12. `path_order`  
13. `metric_quantize`  
14. `png_lsb`  
15. `gen_seed`  
16. `phonetic_sigil` (opt-in)  


## A. Ancient / classical craft (visible structure)

| ID | Description | Skip reasons (examples) |
|----|-------------|-------------------------|
| `spare_monogram` | Reduced unique consonants → circular monogram polyline | `no_letters_after_reduction` |
| `kamea_path` | Letter→number path on selected kamea | `no_path_points` |
| `kamea_square_choice` | Planet/size: operator `--square` or digest mod 7 | Always applied when construct runs |
| `bind_runes` | Elder Futhark stick bind fused at center | `no_runes_after_mapping` |
| `rose_cross_path` | 22-slot rose letter path (latin reduction) | `no_rose_path_points` |

See `methods-bind-runes.md`, `methods-rose-cross.md`. Not Enochian seals.

## B. Modern cryptographic / digital craft

| ID | Description | Skip reasons |
|----|-------------|--------------|
| `intent_digest` | SHA-256 hex of **normalized** intent | Always applied on success |
| `optional_ciphertext` | AES-256-GCM of full intent under passphrase (PBKDF2-HMAC-SHA256 at 600,000 iterations by default, or Argon2id with optional `argon2-cffi`); stored in **local packet** as `sealed_intent` | `no_passphrase` |

**Privacy:** ciphertext is for the local forge packet. v1 public PNG LSB embeds a
**digest-only** payload — never partial ciphertext in the public raster.

## C. Steganography

Public-facing media carry digest / channel bits **without plaintext intent** by
default. Stego exists for operator sovereignty and multi-encoding — not covert harm.

| ID | Medium | What embeds | Notes |
|----|--------|-------------|-------|
| `svg_metadata` | SVG | Namespaced private metadata: receipt/digest/method bitmap | Not plaintext intent |
| `path_epsilon` | SVG geometry | ±EPS coordinate LSB-analogue from digest bits | Sub-visual; may skip if no floats |
| `path_order` | SVG structure | Construction-order / manifest binding (monogram group before kamea); order_token derived from digest | Not residual stroke-order encoding of spare letters |
| `metric_quantize` | SVG attrs | `data-sf-metric` digest nibble attributes on path groups (first 8 / next 8 hex) | Not free-form angle/length encoding |
| `png_lsb` | PNG | Digest-only LSB via layout_raster (+bind/rose) | Skipped: raster/embed failures only |
| `gen_seed` | (AI polish) | Seed derived from digest | `skipped(no_ai_polish)` until `--polish` |

Implementation: `src/sigil_forge/stego_svg.py`, `src/sigil_forge/stego_png.py`, `src/sigil_forge/layout_raster.py`.

## Capacity and failure modes

| Condition | Behavior |
|-----------|----------|
| Stego capacity exceeded | Apply max channels that fit; mark remainder `skipped(capacity)` — **never claim full embed** |
| No path floats | `path_epsilon` skipped |
| No raster backend | `png_lsb` skipped; forge still succeeds with SVG |
| PNG filter types unsupported | `png_lsb` skipped (`embed_failed:…`); no fake non-glyph PNG |
| Verify mismatch | Report failure; do not claim forged integrity |
| Harmful intent | Refuse **before** any embed |

## Privacy defaults

| Asset | Default content |
|-------|-----------------|
| Public SVG / PNG | Digest, stego payload, channel bitmap — **no plaintext intent** |
| Local forge packet | Plaintext `normalized_intent` unless `--seal-packet` + passphrase |
| Run directory name | Timestamp + short digest prefix (not full intent string) |

Construct runs a privacy assert on public SVG (phrase/spare-run leak checks with
length thresholds to avoid false positives on short intents).

## Verify

```bash
python3 scripts/sigil_forge.py verify path/to/glyph.svg
python3 scripts/sigil_forge.py verify path/to/glyph.png   # when png_lsb applied
```

Extract digest / channels; compare to packet. Never report stego success on an
artifact that fails verify.

## Related

- Method params: `methods-spare.md`, `methods-kamea.md`, `methods-bind-runes.md`, `methods-rose-cross.md`  
- Receipts / ledger: `receipts-and-ledger.md`  
- Crypto defaults: AES-GCM + PBKDF2-HMAC-SHA256, 600,000 iterations (stdlib only). Optional: Argon2id via `argon2-cffi` (`--kdf auto|argon2id`); a vetted AES-GCM backend via `cryptography` (`doctor` reports `aes_backend`)  
- Design §5: `docs/superpowers/specs/2026-08-07-sigil-forge-design.md`
