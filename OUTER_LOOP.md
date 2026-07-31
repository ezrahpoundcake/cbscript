# The outer improvement loop

The wish agent writes CBScript, and CBScript is niche — so its first draft sometimes fails to
compile and it iterates. **Every failed compile is a loop the agent had to spend: pure
time-to-goal cost.** The outer loop is the practice of continuously driving that loop count
down, so tomorrow's first draft is more often right the first time.

Two feedback lanes feed it:

```
 agent writes CBScript ─▶ author_datapack ─▶ compile
        ▲                                      │
        │  fewer loops next time               ▼
   CBSCRIPT_LESSONS.md  ◀── distill ──  cbscript-compiles.jsonl   (every attempt: source+error+ok)
        │                                      │
        └── loaded into the agent via          └── analyzed by cbscript_outer_loop.py
            cbscript_help (data, no rebuild)        (recurring errors, loops per feature)
```

## The two artifacts

- **`~/.moddingfromamod/cbscript-compiles.jsonl`** — the RAW signal. The mod appends one line per
  compile attempt: `{time_ms, feature_id, ok, error, source}`. Machine-local (it grows and holds
  generated code), not committed.
- **`CBSCRIPT_LESSONS.md`** — the DISTILLED context. Short "what fails → do this → why" rules. It is
  **data**: `cbscript_help` appends it to the static primer at runtime, so adding a rule improves the
  next draft **without rebuilding or redeploying the mod**. Committed, versioned with the compiler.

## The practice (run after a hill-climb, or on a schedule)

1. `python3 cbscript_outer_loop.py --show-fails` — see failures/attempts, **loops per feature**, and
   the **recurring error patterns** (ranked by how much time they cost).
2. For each recurring pattern, pick the cheaper fix:
   - **A rule** → add it to `CBSCRIPT_LESSONS.md` (most syntax/semantic mistakes).
   - **A compiler fix** → if the compiler crashed or gave an unactionable message, fix it in the
     fork (e.g. a bad parse-error message, a `NoneType` crash) — that helps every future author.
3. Commit the lessons / fork fix. The next agent run starts smarter.

A scheduled version (e.g. a daily cron that runs the analyzer and opens a summary) is a natural
extension — the log is already structured for it. Start manual; automate once the signal is steady.

## Why this is the biggest lever

Correctness *and* speed both come from the agent getting it right in fewer tries. Model prompting
alone plateaus; a lessons file grown from the agent's own real failures compounds — it encodes
exactly the mistakes this agent, on this compiler, actually makes.
