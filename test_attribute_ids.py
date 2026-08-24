#!/usr/bin/env python3
"""Tests for attribute_ids.py.  Run: python3 test_attribute_ids.py

A SEPARATE FILE, and the reason is worth knowing before adding to the other one: `unittest/` is a
Python 2 suite (`import new`, `lambda (x):`) and does not run on any Python this project's own
compiler uses — compile_once.py is python3. So the 120 tests in there cannot be executed here, which
is why nbt_case.py shipped without any. This file runs.
"""
import unittest

import attribute_ids
from attribute_ids import fix_attribute_ids


class TestAttributeIds(unittest.TestCase):

	def setUp(self):
		attribute_ids.reset_warnings()

	def test_short_name_is_corrected(self):
		self.assertEqual(
			fix_attribute_ids('attribute @s minecraft:scale base set 2.0'),
			'attribute @s minecraft:generic.scale base set 2.0')

	def test_the_authors_own_shape_is_kept(self):
		# A bare name stays bare, a namespaced one keeps its namespace. Both are valid to Brigadier,
		# and rewriting the shape as well as the name makes the correction harder to read.
		self.assertEqual(
			fix_attribute_ids('attribute @s scale base set 2.0'),
			'attribute @s generic.scale base set 2.0')

	def test_a_script_that_already_works_is_left_exactly_alone(self):
		# The property that makes correcting safe rather than a judgement call.
		for command in [
				'attribute @s minecraft:generic.scale base set 2.0',
				'attribute Dev generic.max_health base set 40',
				'attribute @e[tag=boss,limit=1] minecraft:generic.attack_damage base set 12']:
			self.assertEqual(fix_attribute_ids(command), command)

	def test_ids_inside_a_summon_attributes_list_are_corrected(self):
		# The other place the wish agent really writes them, measured in its own output.
		self.assertEqual(
			fix_attribute_ids(
				'summon zombie ~ ~ ~ {attributes:[{id:"minecraft:max_health",base:300},'
				'{id:"minecraft:scale",base:3.0}]}'),
			'summon zombie ~ ~ ~ {attributes:[{id:"minecraft:generic.max_health",base:300},'
			'{id:"minecraft:generic.scale",base:3.0}]}')

	def test_an_id_outside_an_attributes_list_is_not_touched(self):
		# Scope matters more than the table does — nbt_case.py's lesson, repeated. `id:` means
		# something different nearly everywhere else, and rewriting those breaks working scripts.
		for command in [
				'summon item ~ ~ ~ {Item:{id:"minecraft:scale",Count:1b}}',
				'say the scale of this attribute is enormous',
				'scoreboard objectives add scale dummy',
				'give @s minecraft:scale']:
			self.assertEqual(fix_attribute_ids(command), command)

	def test_an_attribute_we_do_not_know_is_left_to_the_author(self):
		# A modded attribute is theirs; guessing a prefix would be worse than leaving a name that at
		# least says what they meant.
		command = 'attribute @s somemod:spookiness base set 3'
		self.assertEqual(fix_attribute_ids(command), command)

	def test_every_short_name_is_unambiguous(self):
		# The guard that keeps the rewrite from ever being a GUESS. If a Minecraft ever gives two
		# prefixes the same short name, this fails rather than silently picking one of them.
		shorts = [q.split('.', 1)[1] for q in attribute_ids.QUALIFIED]
		self.assertEqual(len(shorts), len(set(shorts)))
		self.assertEqual(len(attribute_ids.BY_SHORT), len(attribute_ids.QUALIFIED))

	def test_every_known_attribute_is_prefixed(self):
		# The premise of the whole file. If this ever stops being true, the short form is a REAL id
		# on that version and this module must be deleted, not edited.
		for qualified in attribute_ids.QUALIFIED:
			self.assertTrue(qualified.startswith(('generic.', 'player.', 'zombie.')), qualified)

	def test_it_survives_rubbish(self):
		for command in ['', None, 'attribute', 'attribute @s', '{attributes:[]}']:
			fix_attribute_ids(command)

	def test_the_author_is_told_once_per_mistake_not_once_per_line(self):
		# Same discipline as nbt_case: a script with the same mistake in four places produces one
		# line of output, or the real errors are lost in the noise.
		import io
		import contextlib
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			for _ in range(4):
				fix_attribute_ids('attribute @s minecraft:scale base set 2.0')
		self.assertEqual(out.getvalue().count('Corrected.'), 1, out.getvalue())


if __name__ == '__main__':
	unittest.main()
