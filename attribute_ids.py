"""On 1.21.1 EVERY attribute id carries a prefix, and the short name a model writes is always wrong.

`attribute @s minecraft:scale base set 2` is valid CBScript and valid-looking Minecraft. It compiles,
the datapack is written, the pack loads — and Minecraft REJECTS THE WHOLE FUNCTION at load time with
"Can't find element 'minecraft:scale' of type 'minecraft:attribute'" and simply drops it. The pack
still reports as enabled. Nothing the author or the player can see says the rule is gone.

That is a strictly worse failure than the same mistake in a command typed at the console, where the
error comes straight back. Here one bad line silently removes an entire function.

MEASURED. The name is `minecraft:generic.scale` on this version and `minecraft:scale` from 1.21.2 on,
so the short form is exactly what a model trained past that point writes. Sampling the wish agent's
real output turns it up again and again across weeks — in `attribute` commands and inside
`attributes:[{id:"..."}]` on /summon — and the author had written the correct id in its own notes
before emitting the broken one again.

CORRECTED, NOT REFUSED, on the same reasoning as nbt_case.py: the short spelling is never right on
this version, the fix is mechanical, and only the 31 names this Minecraft actually has are touched —
so correcting cannot change what a working script does. A warning is printed so the author learns.

VERSION-PINNED ON PURPOSE. This branch is the 1.21.1 fork, and the table below is read from THAT
Minecraft's own Attributes.java, not from memory. On a version where the short names became real,
this file must be deleted rather than edited: rewriting `minecraft:scale` there would break a script
that was correct. `test_every_short_name_is_unambiguous` fails loudly if the table ever grows two
prefixes for one short name, which is the shape that would make a rewrite a guess.
"""
import re

# Every attribute registered by Minecraft 1.21.1, read out of net.minecraft...Attributes.java.
# All 31 are prefixed; there is no bare attribute on this version, which is what makes the
# correction unambiguous rather than a judgement call.
QUALIFIED = [
	'generic.armor', 'generic.armor_toughness', 'generic.attack_damage',
	'generic.attack_knockback', 'generic.attack_speed', 'generic.burning_time',
	'generic.explosion_knockback_resistance', 'generic.fall_damage_multiplier',
	'generic.flying_speed', 'generic.follow_range', 'generic.gravity',
	'generic.jump_strength', 'generic.knockback_resistance', 'generic.luck',
	'generic.max_absorption', 'generic.max_health', 'generic.movement_efficiency',
	'generic.movement_speed', 'generic.oxygen_bonus', 'generic.safe_fall_distance',
	'generic.scale', 'generic.step_height', 'generic.water_movement_efficiency',
	'player.block_break_speed', 'player.block_interaction_range',
	'player.entity_interaction_range', 'player.mining_efficiency', 'player.sneaking_speed',
	'player.submerged_mining_speed', 'player.sweeping_damage_ratio',
	'zombie.spawn_reinforcements',
]

# short name -> the one real id. Built rather than written out, so the two can never disagree.
BY_SHORT = {}
for _qualified in QUALIFIED:
	BY_SHORT.setdefault(_qualified.split('.', 1)[1], _qualified)

# `attribute <target> <id> ...` — the id is the token after the target, exactly as Brigadier reads it.
ATTRIBUTE_COMMAND = re.compile(r'(\battribute\s+\S+\s+)([a-z0-9_.:]+)', re.IGNORECASE)

# `attributes:[{id:"minecraft:scale",base:3.0}]` on /summon and /give.
#
# Scope matters more than the table does, which is nbt_case.py's lesson repeated. `id:` appears all
# over vanilla NBT and means something different nearly everywhere, so this only ever looks inside an
# `attributes:[...]` list — the one place the value is certainly an attribute name.
ATTRIBUTES_NBT = re.compile(r'attributes\s*:\s*\[[^\]]*\]', re.IGNORECASE)
NBT_ID = re.compile(r'(\bid\s*:\s*")([a-z0-9_.:]+)(")', re.IGNORECASE)

_warned = set()


def _corrected(raw):
	"""The real id for what the author wrote, or None if it needs no change.

	Keeps the author's own shape: a bare `scale` becomes `generic.scale`, and a namespaced
	`minecraft:scale` keeps its namespace.
	"""
	namespaced = ':' in raw
	name = raw.split(':', 1)[1] if namespaced else raw
	if name in QUALIFIED:
		return None                      # already right
	real = BY_SHORT.get(name.lower())
	if real is None:
		return None                      # not an attribute we know; leave the author's own text
	return ('minecraft:' + real) if namespaced else real


def _warn(was, now):
	if (was, now) not in _warned:
		_warned.add((was, now))
		print(f'Warning: "{was}" should be "{now}" — on this Minecraft every attribute id is '
			f'prefixed, and the short name makes the whole FUNCTION fail to load while the pack '
			f'still reports as enabled. Corrected.')


def fix_attribute_ids(command):
	"""Return the command with attribute ids this Minecraft actually has."""
	if not command:
		return command
	lowered = command.lower()
	if 'attribute' not in lowered:
		return command

	def fix_command(match):
		fixed = _corrected(match.group(2))
		if fixed is None:
			return match.group(0)
		_warn(match.group(2), fixed)
		return match.group(1) + fixed

	command = ATTRIBUTE_COMMAND.sub(fix_command, command)

	def fix_nbt_block(block_match):
		def fix_id(m):
			fixed = _corrected(m.group(2))
			if fixed is None:
				return m.group(0)
			_warn(m.group(2), fixed)
			return m.group(1) + fixed + m.group(3)
		return NBT_ID.sub(fix_id, block_match.group(0))

	return ATTRIBUTES_NBT.sub(fix_nbt_block, command)


def reset_warnings():
	"""Between compiles, so a long-running process reports each script's own mistakes."""
	_warned.clear()
