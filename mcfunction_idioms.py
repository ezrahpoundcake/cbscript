"""Recognise Minecraft-command (mcfunction) syntax written where CBScript is expected.

WHY THIS EXISTS
---------------
A .cbscript file contains two languages. Lines beginning with ``/`` are raw Minecraft
commands passed through verbatim (see ``scriptlex.t_COMMAND``); everything else is
CBScript, which has its own statement, condition and expression grammar. The two look
similar enough that anyone -- human or model -- fluent in mcfunction writes mcfunction
into CBScript positions, and the parser can only answer with the token it choked on:

    Syntax error at line 9 column 36. Unexpected GT symbol ">" in state 158.

That names the symptom. It does not say "``matches`` is Minecraft selector syntax; in
CBScript compare the score directly", which is the sentence that actually fixes it.

Measured motivation: of a sample of real model-authored packs that failed to compile,
every failure was one of the families below rather than a novel grammar mistake. The
detectors are therefore driven by the *vanilla command vocabulary* and the *selector
argument grammar* -- not by the handful of errors that happened to be observed first --
so an idiom nobody has hit yet is still recognised.

THE BOUNDARY, which every detector must respect
-----------------------------------------------
* a ``/`` line is Minecraft by definition -- NEVER lint it;
* inside ``@e[...]`` selector brackets, selector-argument syntax is correct -- ``tag=``,
  ``scores={...}``, ``limit=`` and ``distance=`` belong there;
* a comment or a string literal is not code.

Anything a detector cannot place confidently is left alone. A linter that cries wolf on
valid CBScript gets switched off, which costs more than the errors it catches.

USE
---
``lint(text)``                  -> [Finding], a standalone pre-compile pass.
``explain(text, lineno, ...)``  -> str | None, a hint appended to a parser error.

The two differ in nerve, deliberately. ``lint`` runs when nothing is known to be wrong,
so it reports only unambiguous idioms. ``explain`` runs when the parser has already
failed, so a weaker signal is worth surfacing -- there IS an error on that line.
"""

import re

try:  # keep the keyword list in ONE place: the lexer owns it.
    from scriptlex import keywords as _CBS_KEYWORDS
except Exception:  # pragma: no cover - the linter must never break the compiler
    _CBS_KEYWORDS = ()

CBS_KEYWORDS = frozenset(_CBS_KEYWORDS)

# The vanilla command verbs. Kept as data so a new command is one line, and so the
# detector generalises past whichever idioms were observed first.
MC_COMMANDS = frozenset("""
advancement attribute ban bossbar clear clone damage data datapack debug
defaultgamemode difficulty effect enchant execute experience fill fillbiome
forceload gamemode gamerule give help item jfr kick kill list locate loot me
msg particle place playsound publish random recipe reload ride say schedule
scoreboard seed setblock setidletimeout setworldspawn spawnpoint spectate
spreadplayers stopsound summon tag team teammsg teleport tellraw tick time
tp trigger warden_spawn_tracker weather whitelist worldborder xp
""".split())

# Verbs that are ALSO CBScript keywords. CBScript wins -- flagging these would fire on
# perfectly good code (`title @a "..."`, `remove ...`), which is how a linter earns its
# way into someone's ignore list.
AMBIGUOUS = MC_COMMANDS & CBS_KEYWORDS

# Selector arguments. Correct inside @e[...]; a mistake anywhere else.
SELECTOR_ARGS = frozenset("""
type tag team scores nbt advancements predicate limit sort gamemode name
distance x y z dx dy dz x_rotation y_rotation level
""".split())

_COMMENT = re.compile(r"(^|\s)(#|//).*$")
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
_SELECTOR_BRACKETS = re.compile(r"@[a-z]+\s*\[[^\]]*\]?", re.I)


class Finding(object):
    """One recognised idiom. ``hint`` is the sentence that fixes it."""

    def __init__(self, line, text, idiom, hint):
        self.line = line
        self.text = text
        self.idiom = idiom
        self.hint = hint

    def __repr__(self):
        return "Finding(line=%d, idiom=%r)" % (self.line, self.idiom)

    def format(self):
        return "line %d: %s\n    %s\n    %s" % (
            self.line, self.text.strip(), self.idiom, self.hint)


def _is_raw_command(line):
    """A ``/`` line is Minecraft by definition -- mirrors scriptlex.t_COMMAND."""
    return line.lstrip().startswith("/")


def _strip_noise(line):
    """Blank out comments, strings and selector brackets.

    Selector brackets are blanked rather than removed so columns are preserved and so
    ``tag=``/``scores={...}`` inside a selector -- where they are CORRECT -- cannot be
    mistaken for the same text loose in a statement.
    """
    line = _COMMENT.sub("", line)
    line = _STRING.sub(lambda m: " " * len(m.group(0)), line)
    line = _SELECTOR_BRACKETS.sub(lambda m: " " * len(m.group(0)), line)
    return line


def _first_word(code):
    m = re.match(r"\s*([a-z_][a-z0-9_]*)\b", code, re.I)
    return m.group(1) if m else None


# --------------------------------------------------------------------------------
# Detectors. Each takes (code, raw_line) and returns (idiom, hint) or None.
# `code` has comments/strings/selectors blanked; `raw_line` is the original.
# --------------------------------------------------------------------------------

def _d_bare_command(code, raw):
    """A Minecraft command written as a CBScript statement, with no leading ``/``."""
    word = _first_word(code)
    if word is None or word in CBS_KEYWORDS or word not in MC_COMMANDS:
        return None
    return ("`%s` is a Minecraft command, not a CBScript statement." % word,
            "Raw commands pass through verbatim only when the line starts with `/`. "
            "Write `/%s ...`, or express it in CBScript." % word)


def _d_execute_chain(code, raw):
    """``execute ... run ...`` written as a CBScript control structure."""
    if not re.search(r"\bexecute\b", code):
        return None
    if not re.search(r"\brun\b", code):
        return None
    return ("`execute ... run ...` is Minecraft command syntax.",
            "CBScript has its own chain: `as @e[...] at @s` then the body, then `end`. "
            "There is no `execute` and no `run`. (A literal `/execute ... run ...` line "
            "is fine -- it just needs the leading `/`.)")


def _d_matches(code, raw):
    """``matches`` -- the mcfunction score-range idiom -- in a CBScript condition."""
    if not re.search(r"\bmatches\b", code):
        return None
    return ("`matches` is Minecraft selector/score syntax.",
            "In CBScript compare the score directly: `if @s.my_score == 0`, "
            "`>= 5`, `< 10`. Ranges like `matches 1..` become two comparisons.")


def _d_comparison_equals(code, raw):
    """A single ``=`` where a condition needs ``==``.

    Only fires in a condition context. ``@s.score = 5`` is a perfectly good CBScript
    ASSIGNMENT, so flagging a bare ``=`` everywhere would be wrong.
    """
    # NOT anchored at line start: a CBScript chain puts the condition mid-line,
    # e.g. `as @e[tag=x] at @s if @s.cd = 1`. Anchoring here is what made this
    # detector miss the exact shape it was written for.
    m = re.search(r"\b(if|unless|while)\b(.*)$", code, re.I)
    if not m:
        return None
    rest = m.group(2)
    # ignore ==, <=, >=, != ; look for a lone =
    if not re.search(r"(?<![=<>!+\-*/%])=(?!=)", rest):
        return None
    return ("`=` is assignment in CBScript; a condition needs `==`.",
            "Minecraft selectors use a single `=` (`scores={x=1}`), so this reads as "
            "correct. In a CBScript `%s` write `==`." % m.group(1))


def _d_loose_selector_arg(code, raw):
    """A selector argument loose in a statement instead of inside ``@e[...]``."""
    for arg in sorted(SELECTOR_ARGS):
        # `arg=` or `arg={` with nothing but whitespace/word chars before it
        m = re.search(r"(?<![\w\[.])%s\s*=" % re.escape(arg), code)
        if not m:
            continue
        if arg in CBS_KEYWORDS:
            continue
        return ("`%s=` is a selector argument." % arg,
                "It belongs inside the brackets of a selector -- `@e[%s=...]` -- not "
                "loose in a CBScript statement." % arg)
    return None


def _d_store(code, raw):
    """``store result|success`` -- an execute subcommand, not CBScript."""
    if not re.search(r"\bstore\s+(result|success)\b", code):
        return None
    return ("`store result`/`store success` is an `execute` subcommand.",
            "Assign in CBScript instead (`@s.score = ...`), or write the whole thing "
            "as a raw `/execute store ...` line.")


def _d_scoreboard_score_access(code, raw):
    """Reading a score the mcfunction way rather than ``@s.name``."""
    if re.search(r"\bscores\s*=\s*\{", code):
        return ("`scores={...}` is selector syntax.",
                "CBScript reads a per-entity score as `@s.name` and a global as a bare "
                "name. Use `scores={...}` only inside a selector's brackets.")
    return None



BLOCK_OPENERS = frozenset(
    "clock function reset define macro if unless while for switch case as at".split())


def _d_block_delimiter(code, raw):
    """A block opened with a Python `:` or a C `{` instead of CBScript's `end`.

    Not an mcfunction idiom, but the same root cause -- fluency in another language
    leaking in -- and it recurs across models, so it belongs beside the others.
    """
    word = _first_word(code)
    if word is None or word not in BLOCK_OPENERS:
        return None
    stripped = code.rstrip()
    if stripped.endswith(":"):
        return ("A CBScript block is not opened with `:`.",
                "Write the header on its own (`%s ...`), then the body, then `end` on "
                "a line of its own. There is no colon." % word)
    if stripped.endswith("{"):
        return ("A CBScript block is not delimited by `{ }`.",
                "Write the header (`%s ...`), then the body, then `end`. Braces are "
                "only NBT/JSON inside a raw `/` command." % word)
    return None


DETECTORS = (
    _d_bare_command,
    _d_execute_chain,
    _d_matches,
    _d_comparison_equals,
    _d_loose_selector_arg,
    _d_store,
    _d_scoreboard_score_access,
    _d_block_delimiter,
)

# Detectors confident enough to report with no parse error in hand. The rest are
# suggestive and only run once the parser has already failed on that line.
CONFIDENT = frozenset(
    (_d_bare_command, _d_execute_chain, _d_matches, _d_store,
     _d_scoreboard_score_access, _d_block_delimiter))


def _findings_for_line(lineno, raw, detectors):
    if _is_raw_command(raw) or not raw.strip():
        return []
    code = _strip_noise(raw)
    if not code.strip():
        return []
    out = []
    for det in detectors:
        got = det(code, raw)
        if got:
            out.append(Finding(lineno, raw, got[0], got[1]))
    return out


def lint(text):
    """Standalone pre-compile pass. Returns the confident findings only."""
    findings = []
    for i, raw in enumerate(text.split("\n"), start=1):
        findings.extend(_findings_for_line(i, raw, CONFIDENT))
    return findings


def explain(text, lineno):
    """Explain a parse failure at ``lineno``, if an mcfunction idiom accounts for it.

    Returns a single hint string, or None. The parser has already failed here, so the
    full detector set runs -- including the weaker ones that would be too eager in a
    standalone pass.

    The reported line is checked first, then the two lines above it: a block-structure
    error is commonly reported at the `end` that closes a body whose real mistake was
    a line or two earlier.
    """
    lines = text.split("\n")
    for probe in (lineno, lineno - 1, lineno - 2):
        if probe < 1 or probe > len(lines):
            continue
        found = _findings_for_line(probe, lines[probe - 1], DETECTORS)
        if found:
            f = found[0]
            where = "" if probe == lineno else " (line %d)" % probe
            return "%s%s %s" % (f.idiom, where, f.hint)
    return None
