#!/usr/bin/env python3
"""port/mc26.2 (modding-from-a-mod #1593): what the compiler writes for Minecraft 26.x, and that a
1.21.x compile is unchanged.  Run: python3 test_mc26.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

import mc_target
import nbt_case

HERE = os.path.dirname(os.path.abspath(__file__))

SCRIPT = '''dir "x"
desc "26.2 dialect probe"

reset
    tell @a 'Hello! [Click me](call go)'
    /execute as @e[nbt={FallDistance:0f}] run say still
end

function go()
    /say went
end
'''


def compile_with(mc):
	"""Compile SCRIPT with the REAL compiler at CBSCRIPT_MC=mc; return every function's text joined."""
	with tempfile.TemporaryDirectory() as d:
		src = os.path.join(d, 'probe.cbscript')
		out = os.path.join(d, 'probe.zip')
		with open(src, 'w') as f:
			f.write(SCRIPT)
		env = dict(os.environ, CBSCRIPT_MC=mc)
		r = subprocess.run([sys.executable, os.path.join(HERE, 'compile_once.py'), src, '--out', out],
			capture_output=True, text=True, env=env, cwd=d)
		verdict = json.loads(r.stdout)
		assert verdict['ok'], verdict
		with zipfile.ZipFile(out) as z:
			return '\n'.join(z.read(n).decode() for n in z.namelist() if n.endswith('.mcfunction'))


class _Env(unittest.TestCase):
	def setUp(self):
		self._was = os.environ.pop('CBSCRIPT_MC', None)

	def tearDown(self):
		os.environ.pop('CBSCRIPT_MC', None)
		if self._was is not None:
			os.environ['CBSCRIPT_MC'] = self._was


class TestEra(_Env):
	def test_is_26(self):
		for mc, want in (('1.21.1', False), ('1.21.4', False), ('26.2', True), ('26.1.2', True)):
			os.environ['CBSCRIPT_MC'] = mc
			self.assertEqual(mc_target.is_26(), want, mc)


class TestNbtCase(_Env):
	def test_fall_distance_is_snake_case_on_26(self):
		os.environ['CBSCRIPT_MC'] = '26.2'
		self.assertEqual(nbt_case.fix_nbt_case('@e[nbt={FallDistance:0f}]'), '@e[nbt={fall_distance:0f}]')
		self.assertEqual(nbt_case.fix_nbt_case('@e[nbt={falldistance:0f}]'), '@e[nbt={fall_distance:0f}]')
		self.assertEqual(nbt_case.fix_nbt_case('@e[nbt={onground:1b}]'), '@e[nbt={OnGround:1b}]')

	def test_1_21_is_unchanged(self):
		os.environ['CBSCRIPT_MC'] = '1.21.4'
		self.assertEqual(nbt_case.fix_nbt_case('@e[nbt={falldistance:0f}]'), '@e[nbt={FallDistance:0f}]')


class TestCompiledOutput(unittest.TestCase):
	def test_26_2(self):
		text = compile_with('26.2')
		self.assertIn('gamerule max_command_sequence_length', text)
		self.assertNotIn('maxCommandChainLength', text)
		self.assertIn('"click_event":{"action":"run_command","command":', text)
		self.assertNotIn('clickEvent', text)
		self.assertIn('fall_distance', text)

	def test_1_21_4_is_what_it_always_was(self):
		text = compile_with('1.21.4')
		self.assertIn('gamerule maxCommandChainLength', text)
		self.assertIn('"clickEvent":{"action":"run_command","value":', text)
		self.assertIn('FallDistance', text)


if __name__ == '__main__':
	unittest.main()
