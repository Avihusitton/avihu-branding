# hooks/ - deterministic brand enforcement

This directory holds the plugin's system-level enforcement hooks: machine
backstops that run regardless of which agent is active, behind the agents' own
discipline. They do not replace the Final Proofread Gate in
`STYLE_GUIDE.md` section 10. They catch the one case a self-check can miss.

Claude Code auto-discovers `hooks/hooks.json` at the plugin root, so no entry in
`.claude-plugin/plugin.json` is needed. After adding or changing anything in
`hooks/`, run `/reload-plugins` or restart Claude Code (skill edits hot-reload,
hook edits do not).

## check_dashes.py - the em-dash guard

The product's core promise is text that reads human, not AI. The single most
reliable AI fingerprint, in Hebrew and English alike, is the long dash. The
style guide bans it absolutely (section 10.7.1: "NO em-dashes. EVER. ANYWHERE.").
Until now that ban was pure agent self-enforcement. This hook makes it
deterministic.

**Event:** `PostToolUse`, matching `Write | Edit | MultiEdit`.

**What it does:** scans only the text the tool is authoring (the new content of
a Write, the `new_string` of an Edit, every `new_string` of a MultiEdit) for the
long-dash family:

| Code point | Name            |
|------------|-----------------|
| U+2012     | figure dash     |
| U+2013     | en dash         |
| U+2014     | em dash         |
| U+2015     | horizontal bar  |

If it finds one, it exits `2` and writes an actionable message to stderr. Claude
reads that message and fixes the file (replace with a plain hyphen `-`, or
rewrite so no dash is needed). A clean write exits `0` and is silent.

**Hebrew-aware.** It never flags the plain hyphen-minus (U+002D) or the Hebrew
maqaf (U+05BE, the legitimate Hebrew joiner, as in "ל-50"). Those are correct
punctuation and pass untouched. Only the long-dash family above is caught.

**Scope.** The plugin's own files are exempt (this guard, this README, the style
guide that documents the rule), so working on the plugin never self-triggers.
Real brand deliverables are written to the user's working directory, outside the
plugin root, and are always scanned.

**Fail-open.** If the input is not a write, carries no text, targets a plugin
file, or anything unexpected happens, the hook exits `0`. A backstop must never
break a legitimate workflow because of its own bug. The agents' section 10 gate
remains the primary line of defense; this is the safety net under it.

**Requires** `python3` on the PATH (standard on macOS and Linux dev machines).
If absent, the hook simply no-ops and the agent-level gate still applies.

### Extending it

To flag more deterministic typographic tells, add entries to the `FLAGGED` map
in `check_dashes.py` (keep them as `\uXXXX` escapes so this source stays free of
the very glyphs it bans). Keep it deterministic and Hebrew-safe: only add
characters that are never legitimate in this product's output. Stylistic
"AI-slop" judgments (banned openings, manifesto cliches) stay with the agents -
they are not mechanically decidable and belong in the section 10 gate, not here.

### Testing locally

```sh
# clean text -> exit 0
printf '{"tool_name":"Write","tool_input":{"file_path":"/tmp/x.md","content":"שלום, מחיר 50 ש\"ח."}}' \
  | python3 hooks/check_dashes.py ; echo "exit=$?"

# em-dash present -> exit 2 with guidance on stderr
# (\xe2\x80\x94 is the UTF-8 for U+2014, so this snippet stays glyph-clean)
printf '{"tool_name":"Write","tool_input":{"file_path":"/tmp/x.md","content":"text \xe2\x80\x94 more"}}' \
  | python3 hooks/check_dashes.py ; echo "exit=$?"
```
