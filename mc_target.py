"""Which Minecraft this compile is for, and the facts that follow from it.

The mod ships ONE bundled compiler that serves both of its targets (a 1.21.4 build and a 1.21.1
compat build), so the version is a runtime fact rather than a branch: the Java side sets
CBSCRIPT_MC to the version it is compiling for. Unset means 1.21.1, the only version this compiler
knew before, so an old caller behaves exactly as it always did.
"""
import os

DEFAULT = '1.21.1'

# pack_format per release, newest first; a version takes the first row it reaches.
# 1.21/1.21.1 = 48, 1.21.2/1.21.3 = 57, 1.21.4 = 61. A newer Minecraft than the table knows gets
# the newest number it has, which that Minecraft reads as "made for an older version" and still loads.
PACK_FORMATS = (
	((1, 21, 4), 61),
	((1, 21, 2), 57),
	((0,), 48),
)


def version():
	"""The target as a tuple, e.g. (1, 21, 4). An unparseable value is treated as the default."""
	raw = os.environ.get('CBSCRIPT_MC', DEFAULT)
	try:
		return tuple(int(p) for p in raw.split('.')[:3])
	except ValueError:
		return tuple(int(p) for p in DEFAULT.split('.'))


def pack_format():
	v = version()
	for since, fmt in PACK_FORMATS:
		if v >= since:
			return fmt
	return PACK_FORMATS[-1][1]
