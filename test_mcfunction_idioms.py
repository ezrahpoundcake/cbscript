#!/usr/bin/env python3
"""Tests for the mcfunction-vs-CBScript idiom linter.

Two properties matter, and they pull against each other:

  1. it RECOGNISES Minecraft syntax written in a CBScript position;
  2. it stays SILENT on valid CBScript.

(2) is the one that decides whether the thing survives contact with users. A linter
that flags working code gets ignored, and then it catches nothing at all -- so the
false-positive tests below are not padding, they are the load-bearing half.

Run: python3 test_mcfunction_idioms.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcfunction_idioms as M  # noqa: E402


class TestRecognisesMcfunction(unittest.TestCase):
    """Each case is an idiom family, not a single observed error."""

    def _idiom(self, src, line=None):
        line = line if line is not None else len(src.strip().split("\n"))
        return M.explain(src, line)

    def test_bare_command_statement(self):
        hint = self._idiom("clock tick\n    scoreboard objectives add hp dummy\n", 2)
        self.assertIsNotNone(hint)
        self.assertIn("scoreboard", hint)

    def test_any_vanilla_command_not_just_the_observed_ones(self):
        # The point of driving this off the command vocabulary: a verb nobody has
        # hit yet is still recognised.
        for verb in ("summon", "particle", "playsound", "worldborder", "fillbiome"):
            hint = self._idiom("clock tick\n    %s foo bar\n" % verb, 2)
            self.assertIsNotNone(hint, "%s should be recognised" % verb)

    def test_matches_range_idiom(self):
        hint = self._idiom("clock tick\n    if @s.cd matches 0\n", 2)
        self.assertIn("matches", hint)

    def test_execute_run_chain(self):
        hint = self._idiom(
            "clock tick\n    execute as @e[tag=x] at @s run say hi\n", 2)
        self.assertIn("execute", hint)

    def test_single_equals_in_condition(self):
        hint = self._idiom("clock tick\n    if @s.cd = 0\n", 2)
        self.assertIn("==", hint)

    def test_single_equals_in_a_MID_LINE_condition(self):
        """A CBScript chain puts the condition mid-line.

        The first cut anchored the detector at line start and so missed exactly the
        shape it was written for -- a real miss against real model output.
        """
        hint = self._idiom(
            "clock tick\n    as @e[tag=wishmob] at @s if @s.cd = 1\n", 2)
        self.assertIsNotNone(hint)
        self.assertIn("==", hint)

    def test_store_result(self):
        hint = self._idiom("clock tick\n    store result score @s cd\n", 2)
        self.assertIsNotNone(hint)

    def test_block_opened_with_a_colon(self):
        hint = self._idiom("clock 60t:\n    say hi\n", 1)
        self.assertIn("end", hint)

    def test_block_opened_with_a_brace(self):
        hint = self._idiom("function burn {\n    say hi\n", 1)
        self.assertIn("end", hint)

    def test_error_reported_a_line_or_two_after_the_real_mistake(self):
        """Block errors surface at the `end`, not at the offending line."""
        src = "clock tick\n    if @s.cd matches 0\n        say hi\n    end\n"
        self.assertIsNotNone(M.explain(src, 4))


    def test_execute_subcommand_as_a_chain_step(self):
        """0/2 on the first production failures it saw; both were this shape."""
        for src in ("clock tick\n    as @s at @s positioned ^0 ^3.29 ^1.56\n",
                    "clock tick\n    as @e[tag=x] at @s positioned ~ ~1 ~\n"):
            hint = M.explain(src, 2)
            self.assertIsNotNone(hint, src)
            self.assertIn("positioned", hint)

    def test_cbscript_own_chain_keywords_are_not_flagged(self):
        # at/as/facing/rotated/align are CBScript keywords; only the ones it LACKS matter.
        self.assertEqual(M.lint(
            "clock tick\n    as @e[tag=x] at @s facing @p rotated ~ ~ align xyz\n"), [])

class TestSilentOnValidCBScript(unittest.TestCase):
    """The half that decides whether anyone leaves it switched on."""

    def _assert_clean(self, src):
        self.assertEqual(M.lint(src), [], "false positive on:\n%s" % src)

    def test_raw_command_lines_are_minecraft_by_definition(self):
        # Mirrors scriptlex.t_COMMAND: a `/` line passes through verbatim, so every
        # idiom above is CORRECT there and must never be flagged.
        self._assert_clean(
            'clock tick\n'
            '    /execute as @e[tag=x] at @s run damage @s 4 minecraft:on_fire\n'
            '    /scoreboard objectives add hp dummy\n'
            '    /execute store result score @s cd run data get entity @s Air\n')

    def test_selector_arguments_inside_brackets_are_correct(self):
        self._assert_clean(
            'clock tick\n'
            '    as @e[tag=wishmob,limit=1,sort=nearest,scores={cd=0}] at @s\n'
            '        @s.cd = 20\n'
            '    end\n')

    def test_cbscript_keywords_that_look_like_commands(self):
        # `title`, `remove`, `create`, `move`, `tell` are CBScript keywords AND
        # Minecraft-ish words. CBScript wins.
        self._assert_clean(
            'clock tick\n'
            '    title @a "hello"\n'
            '    tell @a "hi"\n')

    def test_assignment_is_not_a_broken_comparison(self):
        self._assert_clean('clock tick\n    @s.cd = 80\n    count = count + 1\n')

    def test_comments_and_strings_are_not_code(self):
        self._assert_clean(
            'clock tick\n'
            '    # summon a thing later; execute ... run ... goes here\n'
            '    tell @a "execute as @e run say matches"\n')

    def test_empty_and_header_only(self):
        self._assert_clean('')
        self._assert_clean('dir "."\ndesc "x"\n')


class TestNeverBreaksTheCompiler(unittest.TestCase):
    """The linter is advisory. It must not raise, whatever it is handed."""

    def test_survives_junk(self):
        for junk in ("", "\x00\x01", "if if if", "@@@[[[", "a" * 5000,
                     "/\n/\n/", "клок тик"):
            M.lint(junk)
            M.explain(junk, 1)
            M.explain(junk, 99999)
            M.explain(junk, -3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
