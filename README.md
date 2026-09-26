# Vera-Plus — magicpin AI Challenge submission

## Approach

`bot.py` implements `compose(category, merchant, trigger, customer=None)` as a
**deterministic, grounded template composer** rather than a raw LLM call.
Each of the 18 trigger `kind`s seen in the dataset (plus a safe generic
fallback for any new kind a post-submission injection might add) has a
dedicated handler. Every handler pulls its "hook" fact from a specific field
in the four contexts — a real performance number, a real digest citation, a
real offer, a real signal — never an invented one.

**Why not an LLM prompt?** Half of the 30 canonical test triggers are
generated (not hand-authored) and ship with a placeholder payload
(`{"placeholder": true}`). An LLM asked to "compose a message for this
trigger" with no real payload will, by default, hallucinate specifics to
sound confident. The template engine instead falls back to whatever *is*
real on the merchant/category context (a performance delta, a stale-post
signal, a peer-CTR gap, a customer_aggregate count) — the same anti-hallucination
behavior the rubric's "no fabricated data" and "post-submission context
injection" tests are designed to catch. It also makes the bot free,
instant, and trivially reproducible (true `temperature=0` with no API
dependency at all), while staying LLM-pluggable: `compose_with_optional_polish()`
will route the grounded template output through Claude for a final phrasing
pass if `ANTHROPIC_API_KEY` + `VERA_LLM_POLISH=1` are set — but the graded
path never depends on that.

`conversation_handlers.py` covers the three "open challenges" the replay
test scores: auto-reply detection (canned-phrase match + verbatim-repeat
detection), intent-handoff (explicit "yes"/"chalo"/"let's do it" routes
straight to action instead of re-qualifying — the brief's Pattern D), and
graceful exit (hard decline, or 3 unanswered nudges / repeated auto-replies).

`bot.py` also exposes the 5 HTTP endpoints from the testing brief
(FastAPI), wrapping the same `compose()`/`respond()` functions with
in-memory, idempotent context storage and per-conversation anti-repetition.

## Trade-offs made

- **No live LLM in the graded path.** Faster, cheaper, and fully
  auditable, at the cost of the more fluid phrasing an LLM can produce.
  Mitigated with the optional polish hook, off by default.
- **Rule-based intent/auto-reply detection** (keyword + repeat-count
  heuristics) rather than an LLM classifier — transparent and fast, but
  will miss paraphrased auto-replies a classifier would catch. Given more
  time, this is the first thing I'd swap for a small classifier prompt.
- **Multi-turn state is in-memory only** (per the testing brief's
  allowance) — fine for a single test window, not production-durable.
- Category-specific emoji/vocabulary coverage is currently only tuned for
  the 5 shipped categories (dentists, salons, gyms, restaurants,
  pharmacies); a 6th category would need one more entry in
  `_CATEGORY_EMOJI` and would otherwise degrade gracefully to plain text.

## What additional context would have helped most

- A **canonical list of the merchant's own canned WhatsApp Business
  auto-reply text** (rather than inferring it from phrase-matching) would
  make auto-reply detection much more reliable.
- A **explicit "already-said" ledger** per conversation (beyond raw
  verbatim-body matching) would let the anti-repetition check catch
  paraphrased repeats, not just identical strings.

## Files

- `bot.py` — composer (`compose`) + optional LLM polish hook + FastAPI harness
- `conversation_handlers.py` — multi-turn reply logic (`respond`)
- `generate_submission.py` — regenerates `submission.jsonl` from any expanded dataset
- `submission.jsonl` — the 30 required test-pair outputs
