"""Content heuristics for cascading to explicit-only members.

The conversation- and reflection-analysers are *explicit-only*: their inputs
are semantically selected (a chat transcript, a reflective journal), so file
extension alone cannot route to them. These heuristics inspect the primary
document result — its text, path, and title line — and decide whether a
second pass is *plausible*.

They are deliberately tolerance-first: a false positive costs one extra,
clearly-labelled signal set that the human marker can discount; a false
negative simply means the member never runs. They never gate the primary
result.
"""

from __future__ import annotations

import re
from pathlib import PurePath

# "User:", "Assistant:", "You:", "ChatGPT said:", "Tutor:" … at line starts.
_ROLE_MARKER = re.compile(
    r"^\s*(user|assistant|system|human|ai|bot|you|me|tutor|student|teacher|"
    r"chatgpt|claude|copilot|gemini|q|a)\s*[:：]",
    re.IGNORECASE | re.MULTILINE,
)
_CHAT_NAME_CLUE = re.compile(r"\b(chat|conversation|transcript)\b", re.IGNORECASE)
_JOURNAL_NAME_CLUE = re.compile(r"\b(journal|reflect\w*|diary|log)\b", re.IGNORECASE)
_REFLECTIVE_CUE = re.compile(
    r"\b(i (learned|learnt|realised|realized|struggled|felt|noticed|thought|"
    r"think|would|will|need to|now realise|now realize|took away|found it)|"
    r"next time|in hindsight|going forward|looking back|my understanding)\b",
    re.IGNORECASE,
)

# Gates (tuned conservative — see module docstring on false-positive cost):
MIN_CHAT_ROLE_MARKERS = 2  # one "You:" is not a conversation
MIN_JOURNAL_WORDS = 150  # too thin to judge; short docs never cascade here
MIN_JOURNAL_CUES = 4
MIN_JOURNAL_FIRST_PERSON = 5


def _text_and_path(data: dict) -> tuple[str, str]:
    return str(data.get("text") or ""), str(data.get("file_path") or "")


def chat_likeness(data: dict) -> bool:
    """Plausibly a human–AI (or tutor–student) conversation transcript."""
    text, path = _text_and_path(data)
    if not text.strip():
        return False
    posix = path.replace("\\", "/").lower()
    # Folder convention wins outright: submissions/<id>/chat/…
    if re.search(r"/chat(s)?/|/conversation(s)?/", posix):
        return True
    markers = len(_ROLE_MARKER.findall(text))
    if markers >= MIN_CHAT_ROLE_MARKERS:
        return True
    # Name/title clues need corroboration from at least one role marker.
    if _CHAT_NAME_CLUE.search(PurePath(path).stem) and markers >= 1:
        return True
    first_line = text.strip().splitlines()[0].lower()
    return bool(_CHAT_NAME_CLUE.search(first_line) and markers >= 1)


def journal_likeness(data: dict) -> bool:
    """Plausibly a reflective journal (first-person + evaluative cues)."""
    text, path = _text_and_path(data)
    if _JOURNAL_NAME_CLUE.search(PurePath(path).stem):
        return True
    words = text.split()
    if len(words) < MIN_JOURNAL_WORDS:
        return False
    first_line = text.strip().splitlines()[0].lower()
    if _JOURNAL_NAME_CLUE.search(first_line):
        return True
    cues = len(_REFLECTIVE_CUE.findall(text))
    first_person = len(re.findall(r"\bI\b", text))
    return cues >= MIN_JOURNAL_CUES and first_person >= MIN_JOURNAL_FIRST_PERSON
