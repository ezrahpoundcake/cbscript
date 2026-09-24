#!/usr/bin/env python3
"""Tests for mc_target.py and the pack.mcmeta it drives.  Run: python3 test_mc_target.py"""
import io
import json
import os
import unittest
import zipfile

import mc_target


class _Env(unittest.TestCase):
	def setUp(self):
		self._was = os.environ.pop('CBSCRIPT_MC', None)

	def tearDown(self):
		os.environ.pop('CBSCRIPT_MC', None)
		if self._was is not None:
			os.environ['CBSCRIPT_MC'] = self._was


class TestPackFormat(_Env):

	def test_unset_is_1_21_1_as_it_always_was(self):
		self.assertEqual(mc_target.version(), (1, 21, 1))
		self.assertEqual(mc_target.pack_format(), 48)

	def test_each_target_gets_its_own_number(self):
		for mc, fmt in (('1.21.1', 48), ('1.21', 48), ('1.21.2', 57), ('1.21.3', 57), ('1.21.4', 61)):
			os.environ['CBSCRIPT_MC'] = mc
			self.assertEqual(mc_target.pack_format(), fmt, mc)

	def test_a_newer_minecraft_gets_the_newest_number_known(self):
		os.environ['CBSCRIPT_MC'] = '1.21.9'
		self.assertEqual(mc_target.pack_format(), 61)

	def test_garbage_is_the_default_not_a_crash(self):
		os.environ['CBSCRIPT_MC'] = 'latest'
		self.assertEqual(mc_target.pack_format(), 48)

	def test_the_written_mcmeta_carries_the_targets_number(self):
		# The real writer, not the helper: this is the line that said 48 for every target.
		import mcworld
		os.environ['CBSCRIPT_MC'] = '1.21.4'
		w = mcworld.mcworld.__new__(mcworld.mcworld)
		buf = io.BytesIO()
		w.zip = zipfile.ZipFile(buf, 'w')
		w.write_mcmeta('t')
		w.zip.close()
		meta = json.loads(zipfile.ZipFile(buf).read('pack.mcmeta'))
		self.assertEqual(meta['pack']['pack_format'], 61)


if __name__ == '__main__':
	unittest.main()
