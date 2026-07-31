# CBScript lessons (auto-loaded into the wish agent)

Distilled rules that stop real compile / runtime failures. This file is DATA: the mod's
`cbscript_help` tool appends it to the static primer, so a rule added here improves the next
draft without rebuilding the mod. Grow it from `~/.moddingfromamod/cbscript-compiles.jsonl`
via `tools/cbscript-outer-loop.sh` (see docs/OUTER_LOOP.md). Keep each lesson short:
**what fails → do this instead → why.**

## Syntax (parse errors)

- **Every block must be closed with `end`.** `reset`, `clock tick`, `function name()`, `as ...`,
  `at ...`, `if ...`, `unless ...`, `while`, `for`, `switch` all open a block that needs a matching
  `end`. A missing `end` is the #1 parse error. (Error will say `Syntax error at line N ... (here: ...)`.)
- **Do NOT write a `dir` or `desc` header.** The mod injects it. Writing your own is a parse error
  (two `dir` lines) — start straight with `import`, `define`, `function`, `reset`, or `clock tick`.
- **Comments start with `#`,** on their own line. Not `//`, not `--`.
- **One raw command per line, starting with `/`.** A raw Minecraft command (`/give`, `/execute`,
  `/tellraw`, `/particle`, ...) must be a single physical line — never wrap JSON/NBT across lines.
- **Selector bases are single letters:** `@e @a @s @p @r`. `@Entity`, `@Player`, `@Marker`,
  `@Position` only exist if you `import common` (recommended — put it at the top).
- **`define` a selector like:** `define @Foo = @e[type=snowball, tag=mine]` then a blank line then
  `end`. Deep NBT/component matches (e.g. `nbt={Item:{components:{...}}}`) belong in a RAW `/execute`
  command, not in a `define` — the selector parser is happy with type/tag/distance but not deep NBT.

## Runtime (compiles fine, but breaks in game)

- **Never let a generated `.mcfunction` line start with `$`.** Minecraft treats a `$`-prefixed line
  as a macro and refuses to run the function plainly ("This function should not run"). In CBScript
  `$` means a compile-time variable/macro — fine in expressions, but make sure your *give/greet/…*
  functions don't emit a leading `$`. If a function must take runtime args, that's a macro by design;
  otherwise keep command lines starting with `/` or a letter.
- **`/damage` hits ONE entity.** `damage @e[...]` errors "Only one entity is allowed". Do
  `execute as @e[...] run damage @s 4 minecraft:on_fire`.
- **Greet players in the `clock tick`, not in `reset`.** A `reset`-time `tellraw @a` reaches nobody
  in singleplayer (the pack loads a beat before the player joins). Pattern:
  `as @a[tag=!x_greeted]` → `tag @s add x_greeted` → call your greet function.
- **A datapack can't change an item's inventory ICON** (needs a resource pack). You CAN rename it,
  add glint (`enchantment_glint_override=true`), or swap its model to another vanilla item with the
  `minecraft:item_model` component.
- **Status effects/NBT you set ONCE decay.** `TicksFrozen`, `Fire`, effect timers etc. tick down —
  if you want a mob kept frozen/burning, re-apply it every tick while the condition holds, or use a
  long duration.
- **Placed blocks need support.** Snow layers / carpets pop off if the block under them is air —
  place effect blocks on the ground where something lands, not floating in mid-air.

## Calling functions (macros vs plain)

- **A function that uses CBScript macros (`with $(x) = @s.foo do ... end`) compiles to a Minecraft
  MACRO function** (its `.mcfunction` has `$`-prefixed lines). You CANNOT call it with a plain
  `/function ns:name` — it throws "This function should not run". Two safe options: call it from
  CBScript with `name()` (which passes the macro args for you), or **drive that logic from the
  `clock tick`** instead of a raw `/function`.
- **For a "spawn this thing" chat link, don't click-run a macro function.** Instead summon a tagged
  marker from the link (`/summon minecraft:marker ~ ~ ~ {Tags:["spawn_x"]}`) and let the `clock tick`
  detect `@e[type=marker,tag=spawn_x]`, do the build, and `kill @s`. This sidesteps the macro issue
  entirely and is how the Mario-face head spawns.

## Moving/deforming display entities (proven on the Mario 64 head)

- Give each `block_display`/`item_display` `interpolation_duration` (e.g. 2) and `teleport_duration`
  when you summon it, or transforms will snap instead of easing.
- **Deform = edit the 4x4 `transformation` matrix, then set `start_interpolation` to 0** so it eases
  to the new shape. Stretch a piece by scaling one axis; move it by changing the translation column.
- **Spring-back:** store a per-entity timer (`@s.squish = @s.squish + 1`), and when it passes your
  threshold, write the REST transform back and re-interpolate.
- **Invisible grab/hit points = `minecraft:interaction` entities** placed on the model. Read their
  `attack`/`interaction` data component in the tick to know a player just hit/grabbed that spot.
  (Reading it back is also how you can self-test deform logic with no player.)

## Detecting a thrown custom item (the reliable recipe)

Tag the projectile by its custom_data in a raw command, then act on the tag:

```
/execute as @e[type=snowball,tag=!mine,nbt={Item:{components:{"minecraft:custom_data":{mine:1b}}}}] run tag @s add mine
as @e[type=snowball, tag=mine] at @s
    ...effects at the projectile...
end
```

To detect the LANDING/impact, spawn a marker at the projectile each tick and, when the projectile is
gone (it despawned on impact), fire the effect at the marker, then kill the marker.
