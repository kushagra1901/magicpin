"""
conversation_handlers.py — multi-turn logic for the /v1/reply harness.

Targets the three "open challenges" from challenge-brief.md §12 that the
replay test (§8) specifically scores:

  1. Detect auto-replies vs. real merchant replies, and don't burn turns on them.
  2. Detect explicit intent ("yes", "let's do it", "chalo") and route straight
     to action instead of re-qualifying (the brief's Pattern D anti-pattern).
  3. Know when to stop — after a hard decline, or after repeated unanswered
     nudges / repeated auto-replies.

respond(state, merchant_message) -> {"action": "send"|"wait"|"end", ...}
matches challenge-testing-brief.md §2.3 exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ConversationState:
    conversation_id: str
    merchant_id: str | None = None
    customer_id: str | None = None
    turns: list[tuple[str, str]] = field(default_factory=list)  # [("bot"/"merchant"/"customer", text)]
    unanswered_nudges: int = 0
    auto_reply_strikes: int = 0


# ---------------------------------------------------------------------------
# Auto-reply detection
# ---------------------------------------------------------------------------

_AUTO_REPLY_PHRASES = [
    "thank you for contacting",
    "we will get back to you",
    "hamari team tak pahuncha",
    "automated assistant",
    "this is an automated",
    "aapki jaankari ke liye",
    "we are currently unavailable",
    "abhi available nahi",
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def is_auto_reply(state: ConversationState, message: str) -> bool:
    norm = _normalize(message)
    # Signal 1: matches a known canned-reply phrase.
    if any(p in norm for p in _AUTO_REPLY_PHRASES):
        return True
    # Signal 2: same message verbatim, seen 2+ times already from this side
    # ("same message verbatim 3+ times = auto-reply" per brief §12 hint —
    # we trip slightly earlier, at the 2nd repeat, to save turns).
    prior_same_side = [t for role, t in state.turns if role in ("merchant", "customer")]
    if prior_same_side.count(norm) >= 1 and norm in [_normalize(t) for t in prior_same_side]:
        # count occurrences using normalized comparison
        occurrences = sum(1 for t in prior_same_side if _normalize(t) == norm)
        if occurrences >= 2:
            return True
    return False


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

_ACCEPT_WORDS = [
    "yes", "yep", "yeah", "ok", "okay", "sure", "go ahead", "let's do it",
    "lets do it", "start", "join", "haan", "chalo", "theek hai", "kar do",
    "kar dijiye", "reply yes",
]
_DECLINE_WORDS = [
    "no", "not interested", "stop", "nahi", "band karo", "unsubscribe",
    "leave me alone", "don't message", "dont message",
]
_ASK_TIME_WORDS = [
    "later", "busy", "call you back", "not now", "give me time",
    "thodi der", "abhi nahi", "baad mein",
]


def detect_intent(message: str) -> str:
    norm = _normalize(message)
    if any(w in norm for w in _DECLINE_WORDS):
        return "decline"
    if any(w in norm for w in _ACCEPT_WORDS):
        return "accept"
    if any(w in norm for w in _ASK_TIME_WORDS):
        return "wait"
    return "unclear"


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

MAX_UNANSWERED_NUDGES = 3


def respond(state: ConversationState, merchant_message: str) -> dict:
    # 1. Auto-reply: try exactly once more with a lighter-weight nudge, then exit.
    if is_auto_reply(state, merchant_message):
        state.auto_reply_strikes += 1
        if state.auto_reply_strikes == 1:
            return {
                "action": "send",
                "body": "Samajh gayi — before this goes to your team, want to take 2 minutes yourself? It's a quick fix.",
                "cta": "open_ended",
                "rationale": "First auto-reply detected; one lightweight nudge before disengaging.",
            }
        return {
            "action": "end",
            "rationale": "Second auto-reply in this conversation; disengaging to avoid wasting turns (per anti-pattern guidance).",
        }

    intent = detect_intent(merchant_message)

    # 2. Explicit accept: route to action immediately, no re-qualification.
    if intent == "accept":
        state.unanswered_nudges = 0
        return {
            "action": "send",
            "body": "Great — starting now. I'll have the first draft ready in a moment; I'll share it here as soon as it's done.",
            "cta": "none",
            "rationale": "Merchant gave explicit affirmative intent; routed directly to action instead of asking another qualifying question.",
        }

    # 3. Explicit decline: exit gracefully, no further nudging.
    if intent == "decline":
        return {
            "action": "end",
            "rationale": "Merchant signaled not interested / opted out; exiting the conversation gracefully.",
        }

    # 4. Asked for time: back off, don't nudge again immediately.
    if intent == "wait":
        return {
            "action": "wait",
            "wait_seconds": 3600,
            "rationale": "Merchant asked for time; backing off an hour before re-engaging.",
        }

    # 5. Unclear / curveball reply: answer once more, but cap total nudges.
    state.unanswered_nudges += 1
    if state.unanswered_nudges > MAX_UNANSWERED_NUDGES:
        return {
            "action": "end",
            "rationale": f"{MAX_UNANSWERED_NUDGES} unanswered nudges without a clear signal; exiting gracefully rather than spamming.",
        }
    return {
        "action": "send",
        "body": "No worries — happy to explain more, or just say the word and I'll go ahead.",
        "cta": "open_ended",
        "rationale": "Reply didn't carry a clear accept/decline signal; offered one more low-friction path forward.",
    }
