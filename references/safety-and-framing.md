# Safety and framing

Version: **v1** (policy lint + gates align with policy track; release tag is
owned separately)

## Core rules

1. **No supernatural efficacy claims** in creative or practice mode.
2. Methods are craft history, symbolic compression, and data embedding — not
   proof of metaphysics.
3. **Safety refusal runs before** normalize encode, stego, or packet write.
4. Intent text is **sensitive**: hash in run paths; no telemetry; no default
   plaintext in public SVG/PNG.
5. Steganography is for **operator sovereignty and multi-encoding**, not assisting
   covert harm.
6. Distinguish **Chaos/Spare intent sigils** from **Enochian / Goetic / authority
   seals** (placement and entity-authority systems). See `distinction-enochian.md`
   and `authority-seal-namespace.md`.

## Authority (Hermes)

- All creative outputs are **proposal-only**.
- The skill may craft symbols, embed data, and write **local** artifacts.
- The skill may **not** claim efficacy, contact third parties, spend money, or
  promote artifacts to “canon” without the human operator.
- Learning ledger lines stay `PROPOSED`. Human-gated promotion writes **operator-local**
  proposals only (`ledger promote --i-confirm PROMOTE`); never mutates
  `references/`. See `receipts-and-ledger.md`.

## Refusal categories (engine + agent)

`src/sigil_forge/safety.py` uses multi-word heuristics (prefer false negatives over
blocking mundane phrases like “kill process”). The **agent** still applies
judgment for edge cases the keyword gate misses.

Refuse (do not soft-build a “safe” version of the harmful form):

| Category | Examples of spirit (not exhaustive) |
|----------|-------------------------------------|
| Violence against others | Murder, kill person, shoot/stab person, poison person |
| Self-harm | Kill myself, suicide plans, self-harm |
| Non-consensual control | Force/make someone love/obey; control mind/will |
| Child exploitation | Any sexual or abusive intent involving minors |

Also refuse or rewrite:

- Empty / pure-noise intent after normalize
- Cultural or closed-practice material the operator forbids
- **Authority-seal requests** (Enochian, Goetic, Solomonic spirit seal, watchtower,
  authority seal, etc.) — hard-excluded from default `construct` / wizard; see
  `authority-seal-namespace.md`

On refusal: explain briefly, invite a constructive rewrite, **write no forge
artifacts**.

## Efficacy language policy

Efficacy claims are forbidden in framing, polish prompts, agent narrative, and
operator-facing copy. Shared helpers live in `src/sigil_forge/policy_lint.py`:

- `lint_efficacy_text(text) -> list[str]` — phrase hits
- `assert_no_efficacy(text, field=…)` — raises `efficacy_policy_violation`
- Applied on packet `framing_notes` and polish prompt fields

### Efficacy lint list (engine patterns)

Case-insensitive multi-word anchors (prefer fewer false positives):

| Pattern (spirit) | Example hit |
|------------------|-------------|
| `this sigil works` | “This sigil works every time” |
| `it will (manifest\|work\|cause)` | “It will manifest wealth” |
| `guarantee(s) result(s)` | “Guarantees results” |
| `prove(s) (that )?magic` | “Proves that magic is real” |
| `contact(s) spirit(s)` | “Contacts spirits” |
| `make(s) (him\|her\|them) (love\|obey)` | “Makes them obey” |
| `supernatural efficacy` | explicit phrase |
| `will (definitely\|certainly) (manifest\|come true)` | certainty claims |

Allowed craft language (examples): compress, encode, externalize, verify recovers
digest, historical method, symbolic carrier, optional personal practice notes.

The list is not exhaustive for agent speech — agents must still avoid efficacy
claims the regex misses.

### Policy check CLI

For CI, agents, and operators **before** construct:

```bash
python3 scripts/sigil_forge.py policy check --text "I maintain calm focus"
python3 scripts/sigil_forge.py policy check --file path/to/text.txt
```

Stdout JSON:

```json
{
  "ok": true,
  "efficacy_hits": [],
  "authority_seal_request": false,
  "authority_family": null
}
```

- Exit **0** if clean; **1** if efficacy hits and/or authority-seal request.
- Does not construct; safe for preflight and CI.

## Framing language

| Allowed | Forbidden |
|---------|-----------|
| Compress, encode, externalize, craft, verify | Works, manifests, guarantees results |
| Historical method, symbolic carrier | Proves magic, contacts spirits |
| Optional personal practice notes | Obligatory ritual that causes outcomes |
| Multi-channel stego for integrity/privacy | Covert harm, surveillance abuse |

Packet always includes mode-appropriate `framing_notes` without efficacy claims
(`src/sigil_forge/packet.py`).

## Privacy

| Asset | Default |
|-------|---------|
| Public SVG/PNG | Digest + stego bits; **no** plaintext intent |
| Forge packet | May include `normalized_intent` unless `--seal-packet` + passphrase |
| Run id | Timestamp + digest prefix |
| `references/` | Read-only during ordinary runs |

Debug modes that weaken privacy must be **explicit and labeled** (not default).

## Fail-closed construct errors

| Condition | Behavior |
|-----------|----------|
| Harmful intent | `ValueError` / refuse — no encode |
| Authority-seal request | `AUTHORITY_SEAL_EXCLUDED` — no encode; no silent substitute |
| Empty intent | Refuse; ask for clear present-tense statement |
| Invalid square | Error with allowed set; do not invent squares |
| Efficacy in framing/polish | `efficacy_policy_violation` — fail closed |
| Verify mismatch | Report failure; no integrity claim |
| Stego capacity | Skip remainder with reason; never claim full embed |

## Related

- Profiles: `profiles-creative.md`, `profiles-practice.md`
- Channels: `channels-and-steganography.md`
- Namespace: `authority-seal-namespace.md`
- Distinction: `distinction-enochian.md`
- Ledger / promote: `receipts-and-ledger.md`
- Runtime: `hermes-runtime-contract.md`
