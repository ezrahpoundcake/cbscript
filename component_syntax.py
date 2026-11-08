"""On 1.21.5+ three item-component spellings changed, and the old ones are what a model writes.

A give line in a datapack function is parsed when the pack LOADS, and one refused line makes Minecraft
drop the whole function — the pack still reports as enabled (attribute_ids.py's lesson). 1.21.5 changed:

  dyed_color={rgb:N}                          -> dyed_color=N
      the old form: "Malformed 'minecraft:dyed_color' component" (measured, a 1.21.8 server).
  custom_name='{"text":"X"}' / item_name / lore=['…']
      -> custom_name={"text":"X"}               text in a component is SNBT now, and a QUOTED value is
      plain text: the old form is ACCEPTED and names the item, literally, {"text":"X"}. A JSON object
      or string is valid SNBT, so the same text goes in unquoted.
  enchantments={levels:{…}} / stored_enchantments  -> the bare map (refused: "Failed to get element minecraft:levels")
  attribute_modifiers={modifiers:[…],show_in_tooltip:false}
      -> attribute_modifiers=[…] (+ tooltip_display={hidden_components:["attribute_modifiers"]})

CORRECTED, NOT REFUSED, as nbt_case.py and attribute_ids.py are: each old spelling is never right on the
new version and the fix is mechanical. Active only when CBSCRIPT_MC is 1.21.5 or newer; on an older target
the command is returned unchanged. A warning is printed so the author learns the new form.
"""
import re

import mc_target

_warned = set()


def _new_syntax():
	return mc_target.version() >= (1, 21, 5)


def _warn(was, now):
	key = (was[:40], now[:40])
	if key not in _warned:
		_warned.add(key)
		print(f'component syntax: "{was}" is the pre-1.21.5 spelling; wrote "{now}"')


def reset_warnings():
	_warned.clear()


_DYED = re.compile(r'((?:minecraft:)?dyed_color)=\{\s*rgb\s*:\s*(-?\d+)\s*(?:,\s*show_in_tooltip\s*:\s*\w+\s*)?\}')
_TEXT_ONE = re.compile(r"((?:minecraft:)?(?:custom_name|item_name))='((?:[^'\\]|\\.)*)'")


def _unquote(body):
	"""The text inside a single-quoted SNBT string."""
	return body.replace("\\'", "'").replace('\\\\', '\\')


def _is_json_text(s):
	s = s.strip()
	return s.startswith('{') or s.startswith('"') or s.startswith('[')


def _match_bracket(s, i, open_ch, close_ch):
	"""Index just past the bracket matching s[i] (which is open_ch), respecting quoted strings."""
	depth, quote = 0, None
	while i < len(s):
		c = s[i]
		if quote:
			if c == '\\':
				i += 2
				continue
			if c == quote:
				quote = None
		elif c in '"\'':
			quote = c
		elif c == open_ch:
			depth += 1
		elif c == close_ch:
			depth -= 1
			if depth == 0:
				return i + 1
		i += 1
	return -1


def _fix_lore(command):
	out, i = [], 0
	pat = re.compile(r'(?:minecraft:)?lore=\[')
	while True:
		m = pat.search(command, i)
		if not m:
			out.append(command[i:])
			return ''.join(out)
		start = m.end() - 1
		end = _match_bracket(command, start, '[', ']')
		if end < 0:
			out.append(command[i:])
			return ''.join(out)
		body = command[start + 1:end - 1]
		items = re.findall(r"'((?:[^'\\]|\\.)*)'", body)
		rest = re.sub(r"'((?:[^'\\]|\\.)*)'", '', body).replace(',', '').strip()
		if items and not rest and all(_is_json_text(_unquote(x)) for x in items):
			new = '[' + ','.join(_unquote(x) for x in items) + ']'
			_warn(command[m.start():end], command[m.start():start] + new)
			out.append(command[i:start] + new)
		else:
			out.append(command[i:end])
		i = end


# A component that lost its wrapper in 1.21.5: attribute_modifiers={modifiers:[…]} is the bare list, and
# enchantments / stored_enchantments={levels:{…}} the bare map ("Failed to get element minecraft:levels",
# measured on a 1.21.8 server, 2026-11-08 — this file corrected only the first, the mod's ComponentSpelling
# both). A show_in_tooltip:false inside becomes tooltip_display on the item.
_WRAPPED = {'attribute_modifiers': ('modifiers', '[', ']'),
	'enchantments': ('levels', '{', '}'),
	'stored_enchantments': ('levels', '{', '}')}


def _fix_modifiers(command):
	out, i = [], 0
	pat = re.compile(r'((?:minecraft:)?(attribute_modifiers|stored_enchantments|enchantments))=\{')
	while True:
		m = pat.search(command, i)
		if not m:
			out.append(command[i:])
			return ''.join(out)
		key, lopen, lclose = _WRAPPED[m.group(2)]
		start = m.end() - 1
		end = _match_bracket(command, start, '{', '}')
		inner = command[start + 1:end - 1] if end > 0 else ''
		lm = re.match(r'\s*' + key + r'\s*:\s*' + re.escape(lopen), inner)
		if end < 0 or not lm:
			out.append(command[i:m.end()])
			i = m.end()
			continue
		lstart = lm.end() - 1
		lend = _match_bracket(inner, lstart, lopen, lclose)
		tail = inner[lend:].strip()
		hide = re.fullmatch(r',?\s*show_in_tooltip\s*:\s*(false|0b|0)\s*', tail) is not None
		if lend < 0 or not (tail == '' or hide or re.fullmatch(r',?\s*show_in_tooltip\s*:\s*\w+\s*', tail)):
			out.append(command[i:end])
			i = end
			continue
		new = m.group(1) + '=' + inner[lstart:lend]
		if hide:
			new += ',minecraft:tooltip_display={hidden_components:["minecraft:' + m.group(2) + '"]}'
		_warn(command[m.start():end], new)
		out.append(command[i:m.start()] + new)
		i = end


def fix_component_syntax(command):
	if not _new_syntax() or ('[' not in command and '{' not in command):
		return command

	def dyed(m):
		now = f'{m.group(1)}={m.group(2)}'
		_warn(m.group(0), now)
		return now

	def text(m):
		body = _unquote(m.group(2))
		if not _is_json_text(body):
			return m.group(0)
		now = f'{m.group(1)}={body}'
		_warn(m.group(0), now)
		return now

	command = _DYED.sub(dyed, command)
	command = _TEXT_ONE.sub(text, command)
	command = _fix_lore(command)
	command = _fix_modifiers(command)
	return command
