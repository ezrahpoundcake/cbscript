#!/usr/bin/env python3
"""Non-interactive, one-shot CBScript compile with structured JSON output.

The stock ``compile.py`` compiles once and then loops forever watching the file
for changes. That is perfect for a human editing a script, but useless for a
program (a mod, a test) that wants to compile a source and read the result. This
wrapper compiles exactly once, never watches, lets the caller choose the output
location, and prints a machine-readable JSON verdict so compile errors can be
fed straight back to whoever wrote the script.

Usage:
    compile_once.py <script.cbscript> [--dir <world_dir>] [--out <zip_path>]

- ``--dir`` overrides the mandatory ``dir "..."`` header, so agent-authored
  scripts never have to carry a machine-specific world path. The datapack is
  written to ``<dir>/datapacks/<namespace>.zip``.
- ``--out`` writes the datapack zip to an explicit path instead (its parent is
  created if needed). Takes precedence over ``--dir`` for placement.

Output: a JSON object on stdout ::

    {"ok": bool, "namespace": str, "output": str|null,
     "log": [str, ...], "error": str|null}

Exit code is 0 on success, 1 on any compile failure — so a caller can branch on
either the code or ``ok``.
"""
import argparse
import contextlib
import io
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cbscript as cbscript_mod          # noqa: E402
import mcworld                           # noqa: E402
import scriptparse                       # noqa: E402
from source_file import source_file      # noqa: E402
from CompileError import CompileError     # noqa: E402


class OneShot(cbscript_mod.cbscript):
    """A cbscript that collects log lines instead of printing, and lets the
    caller redirect where the compiled datapack lands."""

    def __init__(self, source, parse_func, out_dir=None, out_path=None):
        super().__init__(source, parse_func)
        self.out_dir = out_dir
        self.out_path = out_path
        self.logs = []

    def log(self, text):
        self.logs.append(str(text))

    def create_world(self, dir, namespace):
        target_dir = self.out_dir if self.out_dir else dir
        os.makedirs(os.path.join(target_dir, 'datapacks'), exist_ok=True)
        world = mcworld.mcworld(target_dir, namespace)
        if self.out_path:
            out_path = self.out_path

            def write_zip():
                world.zip.close()
                parent = os.path.dirname(os.path.abspath(out_path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(out_path, 'wb') as fh:
                    fh.write(world.zipbytes.getvalue())

            world.write_zip = write_zip
        return world



def _idiom_hint(script_path, error_text):
    """Explain a parse failure in terms of mcfunction-vs-CBScript idiom, if that fits.

    Best-effort and deliberately defensive: a linter that raises would turn a reported
    compile error into a crashed compiler, which is strictly worse than no hint.
    """
    try:
        import re as _re
        import mcfunction_idioms
        m = _re.search(r'line (\d+)', error_text or '')
        if not m:
            return None
        with open(script_path, 'r') as fh:
            text = fh.read()
        return mcfunction_idioms.explain(text, int(m.group(1)))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description='One-shot CBScript compile.')
    ap.add_argument('script', help='path to the .cbscript source')
    ap.add_argument('--dir', default=None,
                    help='override the world dir the datapack is written under')
    ap.add_argument('--out', default=None,
                    help='explicit output .zip path (overrides --dir placement)')
    args = ap.parse_args()

    # Resolve everything to absolute paths BEFORE the compiler chdir's into the
    # script's own directory (it does that so `import common` resolves).
    script_path = os.path.abspath(args.script)
    out_dir = os.path.abspath(args.dir) if args.dir else None
    out_path = os.path.abspath(args.out) if args.out else None

    result = {'ok': False, 'namespace': None, 'output': None, 'log': [], 'error': None}
    buf = io.StringIO()
    try:
        src = source_file(script_path)
        os.chdir(src.get_directory())
        script = OneShot(src, scriptparse.parse, out_dir, out_path)
        result['namespace'] = script.namespace
        with contextlib.redirect_stdout(buf):
            try:
                ok = script.compile_all()
            except (SyntaxError, CompileError) as e:
                ok = False
                result['error'] = str(e)
                # A parser error names the token it choked on; it does not say WHY the
                # line is wrong. When the cause is Minecraft-command syntax written in
                # a CBScript position -- the single commonest way this language is got
                # wrong -- add the sentence that actually fixes it, so a caller
                # retrying on the error message has something to act on.
                hint = _idiom_hint(script_path, result['error'])
                if hint:
                    result['hint'] = hint
                    result['error'] += '\n' + hint
            except Exception as e:  # noqa: BLE001 - report anything to the caller
                ok = False
                result['error'] = 'Unexpected compiler error: ' + repr(e) \
                    + '\n' + traceback.format_exc()
        result['ok'] = bool(ok)
        if ok:
            if out_path:
                result['output'] = out_path
            else:
                base = out_dir if out_dir else os.path.dirname(script_path)
                result['output'] = os.path.join(base, 'datapacks',
                                                script.namespace + '.zip')
        elif not result['error']:
            result['error'] = 'Compile failed — see log.'
        # Merge the compiler's own log() lines with anything it printed to stdout.
        stray = [ln for ln in buf.getvalue().split('\n') if ln.strip()]
        result['log'] = script.logs + stray
    except Exception as e:  # noqa: BLE001
        result['error'] = repr(e) + '\n' + traceback.format_exc()
        result['log'] = [ln for ln in buf.getvalue().split('\n') if ln.strip()]

    print(json.dumps(result, indent=2))
    sys.exit(0 if result['ok'] else 1)


if __name__ == '__main__':
    main()
