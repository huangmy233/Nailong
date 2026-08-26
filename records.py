"""Best-record persistence in records.json.

Comparison rule:
  1. a faster completion time is always better
  2. on an equal time, fewer flips is better

A missing, empty, or damaged file is treated as "no record yet".  Reading or
writing the file never raises out of this module, so the game cannot crash
because of a bad record file.
"""

import json
import os

import paths

BASE_DIR = paths.user_dir()
RECORD_PATH = os.path.join(BASE_DIR, "records.json")

# times within this many seconds count as equal, so the flip count decides
TIME_EPSILON = 0.05


def candidates():
    """Where records.json may live, best place first.

    Normally that is right next to the game.  Only if that folder cannot be
    written to (the exe was put in Program Files, on a read-only share, ...)
    do we fall back to the user's own AppData folder.
    """
    return [RECORD_PATH, os.path.join(paths.fallback_dir(), "records.json")]


def _read(path):
    """Parse one file.  Returns (found, record)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return False, None
    except (OSError, ValueError):
        return True, None            # found but damaged -> no record

    if not isinstance(data, dict):
        return True, None
    try:
        best_time = float(data["best_time"])
        best_flips = int(data["best_flips"])
    except (KeyError, TypeError, ValueError):
        return True, None
    if best_time <= 0 or best_flips <= 0:
        return True, None
    return True, {"best_time": best_time, "best_flips": best_flips}


def load(path=None):
    """Return {'best_time': float, 'best_flips': int} or None.

    A missing, empty or damaged file simply means "no record yet".
    """
    for candidate in ([path] if path else candidates()):
        found, record = _read(candidate)
        if found:
            return record
    return None


def save(record, path=None):
    """Write the record.  Returns True on success, False if it could not."""
    try:
        blob = json.dumps({"best_time": round(float(record["best_time"]), 2),
                           "best_flips": int(record["best_flips"])}, indent=2)
    except (TypeError, ValueError) as exc:
        print("[records] refusing to save a broken record: %s" % exc)
        return False

    last = None
    for candidate in ([path] if path else candidates()):
        try:
            folder = os.path.dirname(candidate)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(candidate, "w", encoding="utf-8") as handle:
                handle.write(blob)
            return True
        except OSError as exc:
            last = exc
    print("[records] could not save records.json: %s" % last)
    return False


def is_better(new_time, new_flips, old):
    """True if (new_time, new_flips) beats the stored record `old`."""
    if old is None:
        return True
    if new_time < old["best_time"] - TIME_EPSILON:
        return True
    if abs(new_time - old["best_time"]) <= TIME_EPSILON:
        return new_flips < old["best_flips"]
    return False


def submit(new_time, new_flips, old, path=None):
    """Store the run if it is an improvement.

    Returns (record_now, improved).
    """
    if is_better(new_time, new_flips, old):
        record = {"best_time": float(new_time), "best_flips": int(new_flips)}
        save(record, path)
        return record, True
    return old, False
