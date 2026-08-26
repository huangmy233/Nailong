"""Package the game into a standalone Windows .exe with PyInstaller.

    pip install pyinstaller
    python build_exe.py                # one single .exe  (dist/)
    python build_exe.py --folder       # a folder build - starts faster
    python build_exe.py --console      # keep a console window (for debugging)

The result is dist/Nailong.exe (or a folder of the same name).
It contains Python, Pygame and every asset, so it runs on a Windows machine
with nothing installed.  records.json is written next to the .exe.

Running the game from source with "python main.py" keeps working either way.
"""

import argparse
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "Nailong"            # -> dist/Nailong.exe
ICON_PATH = os.path.join(HERE, "nailong.ico")
ICON_SOURCE = os.path.join(HERE, "assets", "cards", "angry_nailong.png")
ICON_SIZES = (16, 32, 48, 64, 128, 256)


# ------------------------------------------------------------------- icon ----
def _bmp_entry(surface, size):
    """One classic (BMP/DIB) icon image: 32-bit BGRA, bottom-up, + AND mask."""
    import pygame
    scaled = pygame.transform.smoothscale(surface, (size, size))
    pixels = bytearray(pygame.image.tostring(scaled, "RGBA", True))
    pixels[0::4], pixels[2::4] = pixels[2::4], pixels[0::4]      # RGBA -> BGRA
    mask_stride = ((size + 31) // 32) * 4
    mask = b"\x00" * (mask_stride * size)
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                         len(pixels) + len(mask), 0, 0, 0, 0)
    return header + bytes(pixels) + mask


def build_icon():
    """Write nailong.ico from the angry nailong picture."""
    import pygame
    if not os.path.isfile(ICON_SOURCE):
        print("no icon source at %s - building without an icon" % ICON_SOURCE)
        return None
    pygame.init()
    pygame.display.set_mode((1, 1))
    source = pygame.image.load(ICON_SOURCE).convert_alpha()
    side = min(source.get_size())
    square = source.subsurface(((source.get_width() - side) // 2,
                                (source.get_height() - side) // 2,
                                side, side)).copy()
    images = [_bmp_entry(square, size) for size in ICON_SIZES]
    pygame.quit()

    offset = 6 + 16 * len(images)
    blob = struct.pack("<HHH", 0, 1, len(images))
    for size, image in zip(ICON_SIZES, images):
        blob += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32,
                            len(image), offset)
        offset += len(image)
    blob += b"".join(images)
    with open(ICON_PATH, "wb") as handle:
        handle.write(blob)
    print("wrote %s (%d sizes, %d bytes)" % (ICON_PATH, len(images), len(blob)))
    return ICON_PATH


# ------------------------------------------------------------------ build ----
def build(one_file=True, console=False):
    try:
        import PyInstaller                                     # noqa: F401
    except ImportError:
        sys.exit("PyInstaller is not installed.  Run:  pip install pyinstaller")

    icon = build_icon()
    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", APP_NAME,
        "--onefile" if one_file else "--onedir",
        "--console" if console else "--windowed",
        # absolute source path: relative ones are resolved against --specpath
        "--add-data", os.path.join(HERE, "assets") + os.pathsep + "assets",
        "--exclude-module", "tkinter",
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build_tmp"),
        "--specpath", os.path.join(HERE, "build_tmp"),
    ]
    if icon:
        command += ["--icon", icon]
    command.append(os.path.join(HERE, "main.py"))

    print("\n" + " ".join(command) + "\n")
    result = subprocess.run(command, cwd=HERE)
    if result.returncode != 0:
        sys.exit("PyInstaller failed with exit code %d" % result.returncode)

    target = os.path.join(HERE, "dist", APP_NAME + (".exe" if one_file else ""))
    print("\nBuilt: %s" % target)
    if os.path.isfile(target):
        print("Size : %.1f MB" % (os.path.getsize(target) / (1024 * 1024)))
    print("Double-click it, or hand the single file to anyone on Windows.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", action="store_true",
                        help="build a folder instead of one single .exe")
    parser.add_argument("--console", action="store_true",
                        help="keep the console window (shows warnings)")
    parser.add_argument("--icon-only", action="store_true",
                        help="only regenerate nailong.ico")
    args = parser.parse_args()
    if args.icon_only:
        build_icon()
        return 0
    build(one_file=not args.folder, console=args.console)
    return 0


if __name__ == "__main__":
    sys.exit(main())
