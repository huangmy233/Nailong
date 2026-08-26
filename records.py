"""Best-record persistence in records.json.

Two independent leaderboards are kept:

    "time"    the fastest completion.  A faster time wins; on an equal time
              the run with fewer flips wins.
    "flips"   the fewest flips.  Fewer flips wins; on an equal flip count the
              faster run wins.

A single run can beat one board, both, or neither - a lucky sprint and a
patient no-mistakes game are different achievements.  Each board also
remembers the other statistic of its own run, so a record always describes a
real game.

In memory a record is:

    {"time":  {"time": 24.31, "flips": 22} or None,
     "flips": {"time": 31.20, "flips": 18} or None}

A missing, empty or damaged file simply means "no records yet", and reading or
writing never raises out of this module, so the game cannot crash because of a
bad record file.  Files written by the older single-board version are read and
migrated automatically.
"""

import json
import os

import paths

BASE_DIR = paths.user_dir()
RECORD_PATH = os.path.join(BASE_DIR, "records.json")

# the timer is shown to 0.01 s, so times inside this are a tie
TIME_EPSILON = 0.005

BOARDS = ("time", "flips")


def empty():
    return {"time": None, "flips": None}


def has_any(record):
    return bool(record) and any(record.get(b) for b in BOARDS)


def candidates():
    """Where records.json may live, best place first.

    Normally that is right next to the game.  Only if that folder cannot be
    written to (the exe was put in Program Files, on a read-only share, ...)
    do we fall back to the user's own AppData folder.
    """
    return [RECORD_PATH, os.path.join(paths.fallback_dir(), "records.json")]


def _entry(data):
    """Validate one {"time": float, "flips": int} run.  None if unusable."""
    if not isinstance(data, dict):
        return None
    try:
        seconds = float(data["time"])
        flips = int(data["flips"])
    except (KeyError, TypeError, ValueError):
        return None
    if seconds <= 0 or flips <= 0:
        return None
    return {"time": seconds, "flips": flips}


def _parse(data):
    """Turn whatever was in the file into a record."""
    if not isinstance(data, dict):
        return empty()
    # the old one-board format: {"best_time": 24.31, "best_flips": 22}
    if isinstance(data.get("best_time"), (int, float)):
        old = _entry({"time": data.get("best_time"),
                      "flips": data.get("best_flips")})
        return {"time": old, "flips": dict(old) if old else None}
    return {"time": _entry(data.get("best_time")),
            "flips": _entry(data.get("best_flips"))}


def _read(path):
    """Parse one file.  Returns (found, record)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return False, empty()
    except (OSError, ValueError):
        return True, empty()             # found but damaged -> no records
    return True, _parse(data)


def load(path=None):
    """Return the record.  Boards with no valid entry are None."""
    for candidate in ([path] if path else candidates()):
        found, record = _read(candidate)
        if found:
            return record
    return empty()


def _dump(entry):
    if not entry:
        return None
    return {"time": round(float(entry["time"]), 2), "flips": int(entry["flips"])}


def save(record, path=None):
    """Write the record.  Returns True on success, False if it could not."""
    try:
        blob = json.dumps({"best_time": _dump(record.get("time")),
                           "best_flips": _dump(record.get("flips"))}, indent=2)
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


def beats_time(seconds, flips, entry):
    """Faster wins; an equal time is decided by the flip count."""
    if entry is None:
        return True
    if seconds < entry["time"] - TIME_EPSILON:
        return True
    if abs(seconds - entry["time"]) <= TIME_EPSILON:
        return flips < entry["flips"]
    return False


def beats_flips(seconds, flips, entry):
    """Fewer flips wins; an equal flip count is decided by the time."""
    if entry is None:
        return True
    if flips != entry["flips"]:
        return flips < entry["flips"]
    return seconds < entry["time"] - TIME_EPSILON


def submit(seconds, flips, record, path=None):
    """Store the run on whichever boards it beats.

    Returns (record_now, improved) where improved lists the board names the
    run took over - any of (), ("time",), ("flips",) or both.
    """
    record = dict(record) if record else empty()
    run = {"time": float(seconds), "flips": int(flips)}
    improved = []
    if beats_time(seconds, flips, record.get("time")):
        record["time"] = dict(run)
        improved.append("time")
    if beats_flips(seconds, flips, record.get("flips")):
        record["flips"] = dict(run)
        improved.append("flips")
    if improved:
        save(record, path)
    return record, improved
