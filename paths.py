"""Where the game reads its assets from and where it may write its record.

Running from source these are the same folder.  Inside a PyInstaller build
they are not: the assets live in a temporary folder that is unpacked next to
nothing and wiped on exit, so anything we want to keep has to go beside the
executable instead.
"""

import os
import sys


def frozen():
    """True when running from a PyInstaller build instead of source."""
    return bool(getattr(sys, "frozen", False))


def data_dir():
    """Folder holding the read-only files that ship with the game (assets)."""
    if frozen():
        # PyInstaller onefile unpacks the bundle here; onedir has no _MEIPASS
        return getattr(sys, "_MEIPASS", None) or os.path.dirname(
            os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def user_dir():
    """Folder for files the game writes, i.e. next to the exe or the sources."""
    if frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def fallback_dir():
    """Used only when user_dir() turns out to be read-only."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "NailongMemoryMayhem")
