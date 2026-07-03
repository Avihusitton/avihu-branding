#!/usr/bin/env python3
"""
tal-branding-team :: em-dash guard (Stop backstop)

Companion to check_dashes.py. That script guards text written to FILES
(PostToolUse). This one guards the CHAT REPLY (Stop), because these teams
produce most of their output in chat - a WhatsApp draft, a social caption the
owner copies straight out of the conversation - and never write it to a file.
Without this, the most visible output is the one place the file guard cannot see.

On Stop it reads the session transcript, takes the most recent assistant
message, and scans it for the long-dash family that is the AI fingerprint in
Hebrew and English:

    U+2012 figure dash       (no glyph in this file on purpose)
    U+2013 en dash
    U+2014 em dash
    U+2015 horizontal bar

The plain hyphen-minus (U+002D) and the Hebrew maqaf (U+05BE) are correct
punctuation and pass.

Behavior:
  - flagged dash in the reply -> exit 2, an actionable message to stderr that
                                 Claude reads and acts on (replace with '-' /
                                 rewrite), then sends the reply again.
  - clean, no transcript,
    already re-running because
    of this hook, or any
    internal error            -> exit 0 (fail open). A backstop must never trap
                                 a session because of its own bug.
"""

import json
import sys

# code point -> human name. Built from ordinals so this source file stays glyph-clean.
FLAGGED = {
    chr(0x2012): "figure dash",
    chr(0x2013): "en dash",
    chr(0x2014): "em dash",
    chr(0x2015): "horizontal bar",
}


def last_assistant_text(transcript_path):
    """Concatenate the text blocks of the most recent assistant turn in the JSONL transcript."""
    last = None
    with open(transcript_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") == "assistant":
                last = obj
    if not last:
        return ""
    content = last.get("message", {}).get("content", [])
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def main():
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    if not raw.strip():
        return 0

    data = json.loads(raw)

    # Only act on Stop. If some other event reaches this script, do nothing.
    event = data.get("hook_event_name", "")
    if event and event != "Stop":
        return 0

    # Loop guard: once we have already blocked and the model is re-running
    # because of this hook, let it stop. One corrective nudge, never a trap.
    if data.get("stop_hook_active") is True:
        return 0

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return 0

    text = last_assistant_text(transcript_path)
    if not text:
        return 0

    # Fast path: nothing flagged -> allow immediately.
    if not (set(text) & set(FLAGGED)):
        return 0

    found = sorted({c for c in text if c in FLAGGED}, key=ord)
    out = [
        "tal-branding-team em-dash guard: forbidden long dash in the chat reply.",
        "STYLE_GUIDE.md section 10.7.1 - no em-dashes (or en-dashes) anywhere, ever.",
        "Found: " + ", ".join(f"{FLAGGED[c]} (U+{ord(c):04X})" for c in found),
        "Fix: replace each with a plain hyphen '-' (U+002D) or rewrite so no dash "
        "is needed, then send the reply again. The Hebrew maqaf and plain hyphens are fine.",
    ]
    sys.stderr.write("\n".join(out) + "\n")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        # Never break a real workflow because the backstop itself failed.
        sys.exit(0)
