#!/usr/bin/env python3
"""Tests for component_syntax.py.  Run: python3 test_component_syntax.py"""
import os
import unittest

import component_syntax as cs


class Base(unittest.TestCase):
	def setUp(self):
		self._was = os.environ.pop('CBSCRIPT_MC', None)
		os.environ['CBSCRIPT_MC'] = '1.21.8'
		cs.reset_warnings()

	def tearDown(self):
		os.environ.pop('CBSCRIPT_MC', None)
		if self._was is not None:
			os.environ['CBSCRIPT_MC'] = self._was


class TestComponentSyntax(Base):

	def test_dyed_color_becomes_a_number(self):
		self.assertEqual(cs.fix_component_syntax('give @s leather_helmet[minecraft:dyed_color={rgb:9857238}] 1'),
			'give @s leather_helmet[minecraft:dyed_color=9857238] 1')
		self.assertEqual(cs.fix_component_syntax('give @s x[dyed_color={rgb:5,show_in_tooltip:false}]'),
			'give @s x[dyed_color=5]')

	def test_a_quoted_json_name_is_unquoted(self):
		self.assertEqual(cs.fix_component_syntax('''give @s stick[minecraft:custom_name='{"text":"Wand","italic":false}'] 1'''),
			'give @s stick[minecraft:custom_name={"text":"Wand","italic":false}] 1')
		self.assertEqual(cs.fix_component_syntax('''give @s stick[item_name='"Plain"'] 1'''),
			'give @s stick[item_name="Plain"] 1')

	def test_an_escaped_quote_inside_the_name_survives(self):
		self.assertEqual(cs.fix_component_syntax('''give @s stick[custom_name='{"text":"Moddy\\'s"}'] 1'''),
			'''give @s stick[custom_name={"text":"Moddy's"}] 1''')

	def test_lore_lines_are_unquoted(self):
		self.assertEqual(cs.fix_component_syntax('''give @s stick[lore=['{"text":"a"}','{"text":"b, c"}']] 1'''),
			'give @s stick[lore=[{"text":"a"},{"text":"b, c"}]] 1')

	def test_modifiers_become_a_list_and_the_hidden_line_moves(self):
		was = ('give @s stick[minecraft:attribute_modifiers={modifiers:[{type:"attack_damage",id:"a:b",amount:3,'
			'operation:"add_value",slot:"mainhand"}],show_in_tooltip:false}] 1')
		self.assertEqual(cs.fix_component_syntax(was),
			'give @s stick[minecraft:attribute_modifiers=[{type:"attack_damage",id:"a:b",amount:3,'
			'operation:"add_value",slot:"mainhand"}],minecraft:tooltip_display={hidden_components:'
			'["minecraft:attribute_modifiers"]}] 1')
		self.assertEqual(cs.fix_component_syntax('give @s x[attribute_modifiers={modifiers:[]}]'),
			'give @s x[attribute_modifiers=[]]')

	def test_the_new_spelling_is_left_alone(self):
		new = 'give @s stick[dyed_color=5,custom_name={"text":"W"},lore=[{"text":"a"}],attribute_modifiers=[]] 1'
		self.assertEqual(cs.fix_component_syntax(new), new)

	def test_plain_text_in_quotes_is_not_json_and_is_left_alone(self):
		cmd = "give @s stick[custom_name='Wand'] 1"
		self.assertEqual(cs.fix_component_syntax(cmd), cmd)

	def test_nothing_changes_on_an_older_target(self):
		os.environ['CBSCRIPT_MC'] = '1.21.4'
		old = '''give @s x[dyed_color={rgb:5},custom_name='{"text":"W"}'] 1'''
		self.assertEqual(cs.fix_component_syntax(old), old)


if __name__ == '__main__':
	unittest.main()
