"""Vanilla entity NBT field names are CamelCase, and `nbt={...}` matching is CASE-SENSITIVE.

`@e[nbt={onground:1b}]` is valid syntax that matches NOTHING, for ever, and says so nowhere:
CBScript compiles it, Minecraft accepts the command, the datapack loads, and the rule silently never
fires. There is no error to see and no output to miss — the only symptom is that the thing the
author asked for does not happen.

MEASURED, 2026-08-19, across 15 generated datapacks: `OnGround` was wrong-cased 33 times in 10 of
them, and `FallDistance` 12 times in one more. Every one of those packs compiled, loaded and
reported success.

And the guidance already existed. CBSCRIPT_LESSONS.md has said, in as many words and correctly
capitalised, `/execute if entity @s[nbt={OnGround:1b}] run damage @s 6 minecraft:falling_block`
since the Grumbnar work. It was written down, it was read, and the lowercase form was emitted
anyway — which is why this is a transform in the compiler rather than another line in the lessons.

CORRECTED, NOT REFUSED. The lowercase spelling is never right, the fix is mechanical, and only exact
known field names are touched, so correcting cannot change what a working script does. A warning is
printed in the same style as the rest of the compiler so the author still learns.
"""
import re

# Vanilla entity NBT fields whose capitalisation is load-bearing.
#
# Deliberately short: every entry can only be one thing, so rewriting it is safe. A field a custom
# entity might legitimately spell in lower case does not belong here.
FIELDS = [
	'OnGround', 'FallDistance', 'Motion', 'Rotation', 'Invulnerable', 'NoGravity',
	'Silent', 'CustomName', 'CustomNameVisible', 'Health', 'Fire', 'Air', 'Glowing',
	'PortalCooldown', 'Passengers', 'Tags',
]

# Only inside a selector's nbt={...} argument.
#
# Scope matters more than the list does. The same words appear legitimately elsewhere and rewriting
# them would BREAK working scripts: `minecraft:air` is a block, `tag=` in a selector really is lower
# case, and a scoreboard the author named `health` is theirs to name. A first pass over whole files
# flagged 299 "errors", essentially all of them this.
NBT_BLOCK = re.compile(r'nbt=\{[^}]*\}')

_warned = set()


def fix_nbt_case(command):
	"""Return the command with known vanilla NBT fields correctly capitalised.

	Warns once per distinct misspelling per run, so a script with the same mistake in four places
	produces one line of output rather than four.
	"""
	if not command or 'nbt=' not in command:
		return command

	def fix_block(match):
		block = match.group(0)
		for field in FIELDS:
			# A field name sits after `{` or `,` and before `:`. Anchoring on that is what stops a
			# VALUE that happens to read like a field name from being rewritten inside the data.
			pattern = re.compile(r'([{,]\s*)(' + field + r')(\s*:)', re.IGNORECASE)

			def repl(m):
				if m.group(2) != field:
					key = (m.group(2), field)
					if key not in _warned:
						_warned.add(key)
						print(f'Warning: "{m.group(2)}" should be "{field}" — vanilla NBT field '
							f'names are CamelCase and nbt={{...}} matching is case-sensitive, so '
							f'the lower-case form matches nothing and the rule never fires. '
							f'Corrected.')
				return m.group(1) + field + m.group(3)

			block = pattern.sub(repl, block)
		return block

	return NBT_BLOCK.sub(fix_block, command)


def reset_warnings():
	"""Between compiles, so a long-running process reports each script's own mistakes."""
	_warned.clear()
