#!/usr/bin/env python3
"""The OUTER LOOP: mine real CBScript compile failures and turn them into better context.

Every author_datapack attempt the wish agent makes is logged (source + error + outcome) to
~/.moddingfromamod/cbscript-compiles.jsonl. Each failed attempt is a compile loop the agent
had to spend — pure time-to-goal cost. This script surfaces where that time goes so we can
kill it at the source, by either:

  1. adding a rule to CBSCRIPT_LESSONS.md (auto-loaded into the agent's context), or
  2. fixing a real robustness bug in the compiler here in the fork.

Usage:
    python3 cbscript_outer_loop.py            # summarize the default log
    python3 cbscript_outer_loop.py <file>     # a specific log
    python3 cbscript_outer_loop.py --show-fails   # also print the failed drafts

Run it after a hill-climb session (or on a schedule). It never modifies anything — it reports;
you distill the recurring failures into CBSCRIPT_LESSONS.md and commit.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

DEFAULT_LOG = os.path.expanduser("~/.moddingfromamod/cbscript-compiles.jsonl")


def normalize(err):
    """Collapse an error to a pattern so near-identical failures group together."""
    if not err:
        return "(no error text)"
    e = err.strip().split("\n")[0]
    e = re.sub(r"line \d+", "line N", e)
    e = re.sub(r"column \d+", "column C", e)
    e = re.sub(r"state \d+", "state S", e)
    e = re.sub(r"\(here: .*?\)", "(here: ...)", e)
    e = re.sub(r"'[^']*'", "'X'", e)
    e = re.sub(r"\"[^\"]*\"", '"X"', e)
    return e[:160]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_fails = "--show-fails" in sys.argv
    path = args[0] if args else DEFAULT_LOG
    if not os.path.isfile(path):
        print(f"No compile log at {path} yet — nothing to analyze.")
        return

    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue

    total = len(records)
    ok = sum(1 for r in records if r.get("ok"))
    fails = total - ok
    print(f"=== CBScript compile log: {path} ===")
    print(f"attempts={total}  successes={ok}  failures={fails}"
          + (f"  (failure rate {fails*100//total}%)" if total else ""))

    # Loops-to-success per feature = the time-to-goal metric. Consecutive attempts on the same
    # feature_id ending in a success is one "hill climb"; count attempts in it.
    by_feature = defaultdict(list)
    for r in records:
        by_feature[r.get("feature_id", "?")].append(r)
    print("\n--- loops per feature (attempts before it compiled) ---")
    for fid, recs in sorted(by_feature.items()):
        attempts = len(recs)
        got = any(r.get("ok") for r in recs)
        flag = "" if attempts <= 1 else ("  <-- worth a lesson" if attempts >= 3 else "")
        print(f"  {fid:24} attempts={attempts} compiled={'yes' if got else 'NO'}{flag}")

    # The payoff: which error patterns recur. Each is a candidate lesson.
    patterns = Counter(normalize(r.get("error")) for r in records if not r.get("ok"))
    if patterns:
        print("\n--- recurring failure patterns (most costly first) ---")
        for patt, n in patterns.most_common(15):
            print(f"  x{n:<3} {patt}")

    if show_fails:
        print("\n--- failed drafts ---")
        for r in records:
            if not r.get("ok"):
                print("-" * 60)
                print("feature:", r.get("feature_id"), "| error:", (r.get("error") or "")[:200])
                print(r.get("source", ""))

    print("\nNext: turn the top recurring patterns into rules in CBSCRIPT_LESSONS.md")
    print("(or fix the compiler if it's a crash/bad message), then commit.")


if __name__ == "__main__":
    main()
