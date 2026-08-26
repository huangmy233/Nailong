"""Nailong Memory Mayhem - entry point.

Run the game with:

    python main.py

The packaged build (see build_exe.py) starts here too.
"""

import os
import sys

# make sure the game's own folder is importable no matter where it is started
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths

try:
    import pygame  # noqa: F401
except ImportError:
    sys.exit("Pygame is not installed.  Run:  pip install -r requirements.txt")

from game import main


def _report_crash(exc):
    """A packaged build has no console, so leave a note next to the exe."""
    import traceback
    text = "".join(traceback.format_exception(type(exc), exc,
                                              exc.__traceback__))
    print(text)
    if not paths.frozen():
        return
    for folder in (paths.user_dir(), paths.fallback_dir()):
        try:
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "nailong_error.log"), "w",
                      encoding="utf-8") as handle:
                handle.write(text)
            return
        except OSError:
            continue


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:          # never die without saying why
        _report_crash(exc)
        raise
