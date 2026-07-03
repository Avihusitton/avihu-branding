#!/usr/bin/env python3
"""
tal-branding-team :: em-dash guard (PostToolUse backstop)

Deterministic, system-level enforcement of STYLE_GUIDE.md section 10.7.1
("NO em-dashes. EVER. ANYWHERE."). This is the machine backstop to the agents'
own Final Proofread Gate, not a replacement for it.

It runs after Write / Edit / MultiEdit and scans the text the tool is writing
for the long-dash family that is the AI fingerprint in Hebrew and English:

    U+2012 figure dash       (no glyph in this file on purpose)
    U+2013 en dash
    U+2014 em dash
    U+2015 horizontal bar

Hebrew-aware by design: it deliberately does NOT flag the plain hyphen-minus
(U+002D) or the Hebrew maqaf (U+05BE, the legitimate Hebrew joiner). Those are
correct punctuation and must pass.

Behavior:
  - found a flagged dash  -> exit 2, write an actionable message to stderr that
                             Claude reads and acts on (replace with '-' / rewrite).
  - clean                 -> exit 0.
  - not a write tool,
    no text, exempt file,
    or any internal error -> exit 0 (fail open). A backstop must never break a
                             legitimate workflow because of its own bug.

The plugin's own files are exempt (this script, the hooks README, the style
guide that documents the rule), so editing the plugin never self-triggers.
Real brand deliverables are written to the user's working directory, outside
the plugin root, and are always scanned.
"""

import json
import os
import sys

# code point -> human name. Written as escapes so this source file stays glyph-clean.
FLAGGED = {
    "\u2012": "figure dash",
    "\u2013": "en dash",
    "\u2014": "em dash",
    "\u2015": "horizontal bar",
}

WRITE_TOOLS = ("Write", "Edit", "MultiEdit")


def new_text(tool_name, tool_input):
    """Return only the text this tool is authoring (not pre-existing file content)."""
    if tool_name == "Write":
        return tool_input.get("content", "") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string", tool_input.get("new_str", "")) or ""
    if tool_name == "MultiEdit":
        parts = []
        for edit in tool_input.get("edits", []) or []:
            edit = edit or {}
            parts.append(edit.get("new_string", edit.get("new_str", "")) or "")
        return "\n".join(parts)
    return ""


def is_plugin_own_file(file_path):
    """True if file_path lives inside this plugin (exempt: it documents the rule)."""
    if not file_path:
        return False
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.abspath(file_path)
    return target == plugin_root or target.startswith(plugin_root + os.sep)


def main():
    # JSON from Claude Code is always UTF-8. Decode explicitly so the guard does
    # not depend on the hook environment's locale (a non-UTF-8 locale could
    # otherwise mis-decode and let a dash through). errors="replace" keeps it safe.
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    if not raw.strip():
        return 0

    data = json.loads(raw)
    tool_name = data.get("tool_name", "")
    if tool_name not in WRITE_TOOLS:
        return 0

    tool_input = data.get("tool_input", {}) or {}
    if is_plugin_own_file(tool_input.get("file_path", "")):
        return 0

    text = new_text(tool_name, tool_input)
    if not text:
        return 0

    # Fast path: nothing flagged -> allow immediately.
    if not (set(text) & set(FLAGGED)):
        return 0

    # Collect occurrences with context so Claude can find and fix each one.
    hits = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for col, ch in enumerate(line, 1):
            if ch in FLAGGED:
                hits.append((line_no, col, ch, line.strip()))

    found = sorted({h[2] for h in hits}, key=ord)
    out = [
        "tal-branding-team em-dash guard: forbidden long dash in written text.",
        "STYLE_GUIDE.md section 10.7.1 - no em-dashes (or en-dashes) anywhere, ever.",
        "Found: " + ", ".join(f"{FLAGGED[c]} (U+{ord(c):04X})" for c in found),
    ]
    for line_no, col, _ch, ctx in hits[:5]:
        snippet = ctx[:80]
        out.append(f"  near line {line_no}, col {col}: ...{snippet}...")
    if len(hits) > 5:
        out.append(f"  (+{len(hits) - 5} more)")
    out.append(
        "Fix: replace each with a plain hyphen '-' (U+002D) or rewrite so no dash "
        "is needed, then re-save. The Hebrew maqaf and plain hyphens are fine."
    )
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
