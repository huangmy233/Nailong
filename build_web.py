"""Build the browser version: one self-contained HTML file.

    python build_web.py

Writes two files:

    index.html          a complete page - double-click it, or upload it
                        anywhere.  Every picture and sound is embedded, so it
                        needs no server and no internet connection.  It sits at
                        the project root so GitHub Pages serves it as the site.
    web/artifact.html   the same page without the <html>/<head>/<body>
                        skeleton, for hosts that supply their own.

To keep the download small the assets are optimised on the way in (the
originals in assets/ are never touched):

    pictures  centre-cropped / proportionally fitted, then scaled to 512 px
    sounds    downmixed to mono 22050 Hz, which browsers play just as happily

Change a file in assets/ and re-run this script to update the web build.
"""

import argparse
import base64
import io
import json
import os
import sys
import wave

import pygame

import asset_manager as AM

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(HERE, "web")
TEMPLATE = os.path.join(WEB_DIR, "index.template.html")
GAME_JS = os.path.join(WEB_DIR, "game.js")
# the page lives at the project root so GitHub Pages serves it as the site
OUT_PAGE = os.path.join(HERE, "index.html")
OUT_FRAGMENT = os.path.join(WEB_DIR, "artifact.html")

IMAGE_SIZE = 512          # plenty: a card is at most ~220 px on screen
SOUND_RATE = 22050
SQUARE_KEYS = AM.PAIR_KEYS + [AM.BACK_KEY]      # centre-cropped by the game
KEEP_WHOLE = [AM.ANGRY_KEY, AM.LAUGH_KEY]       # whole character must stay


def _png_bytes(surface):
    buffer = io.BytesIO()
    pygame.image.save(surface, buffer, "png")
    return buffer.getvalue()


def build_images(report):
    pygame.display.set_mode((1, 1))
    out = {}
    for key in SQUARE_KEYS + KEEP_WHOLE:
        path = None
        for ext in AM.IMAGE_EXTS:
            candidate = os.path.join(AM.CARD_DIR, key + ext)
            if os.path.isfile(candidate):
                path = candidate
                break
        if path is None:
            print("  skip  %-18s no source image" % key)
            continue
        try:
            image = pygame.image.load(path).convert_alpha()
        except pygame.error as exc:
            print("  skip  %-18s %s" % (key, exc))
            continue

        with open(path, "rb") as handle:
            original = handle.read()

        if key in SQUARE_KEYS:
            side = min(image.get_size())
            square = image.subsurface(((image.get_width() - side) // 2,
                                       (image.get_height() - side) // 2,
                                       side, side)).copy()
            target = min(IMAGE_SIZE, side)
            prepared = pygame.transform.smoothscale(square, (target, target))
        else:
            prepared = AM._fit(image, IMAGE_SIZE, IMAGE_SIZE)
        shrunk = _png_bytes(prepared)

        # Several of the source PNGs are already better compressed than
        # anything we can re-encode, and the game crops/fits at draw time
        # anyway - so simply embed whichever copy is smaller.
        if len(shrunk) < len(original):
            blob, mime, note = shrunk, "image/png", "%s" % (prepared.get_size(),)
        else:
            ext = os.path.splitext(path)[1].lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
            blob, note = original, "original"

        out[key] = "data:" + mime + ";base64," + base64.b64encode(blob).decode()
        report.append((key, len(original), len(blob)))
        print("  image %-18s %6.0f kB -> %6.0f kB  (%s)"
              % (key, len(original) / 1024.0, len(blob) / 1024.0, note))
    return out


def _shrink_wav(raw):
    """Mono, 22050 Hz, 16-bit.  Returns the original bytes if we cannot."""
    try:
        import audioop
    except ImportError:
        return raw                       # Python 3.13+: ship it unchanged
    try:
        with wave.open(io.BytesIO(raw), "rb") as src:
            channels = src.getnchannels()
            width = src.getsampwidth()
            rate = src.getframerate()
            frames = src.readframes(src.getnframes())
        if width != 2:
            frames = audioop.lin2lin(frames, width, 2)
            width = 2
        if channels > 1:
            frames = audioop.tomono(frames, width, 0.5, 0.5)
        if rate != SOUND_RATE:
            frames, _ = audioop.ratecv(frames, width, 1, rate, SOUND_RATE, None)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as dst:
            dst.setnchannels(1)
            dst.setsampwidth(width)
            dst.setframerate(SOUND_RATE)
            dst.writeframes(frames)
        return buffer.getvalue()
    except Exception as exc:                                  # noqa: BLE001
        print("     (could not shrink: %s - embedding the original)" % exc)
        return raw


def build_sounds(report):
    out = {}
    for name in AM.SOUND_NAMES:
        path = os.path.join(AM.SOUND_DIR, name + ".wav")
        if not os.path.isfile(path):
            print("  skip  %-18s no sound file" % name)
            continue
        with open(path, "rb") as handle:
            raw = handle.read()
        small = _shrink_wav(raw)
        out[name] = base64.b64encode(small).decode()
        report.append((name + ".wav", len(raw), len(small)))
        print("  sound %-18s %6.0f kB -> %6.0f kB"
              % (name, len(raw) / 1024.0, len(small) / 1024.0))
    return out


def main():
    global IMAGE_SIZE
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image-size", type=int, default=512,
                        help="max picture size in pixels (default 512)")
    args = parser.parse_args()
    IMAGE_SIZE = max(128, args.image_size)

    for path in (TEMPLATE, GAME_JS):
        if not os.path.isfile(path):
            sys.exit("missing %s" % path)

    pygame.init()
    print("preparing assets for the web build")
    report = []
    assets = {"images": build_images(report), "sounds": build_sounds(report)}
    pygame.quit()

    with open(TEMPLATE, "r", encoding="utf-8") as handle:
        template = handle.read()
    with open(GAME_JS, "r", encoding="utf-8") as handle:
        script = handle.read()

    if "__ASSETS_JSON__" not in template or "__GAME_JS__" not in template:
        sys.exit("index.template.html lost its placeholders")

    body = template.replace("__ASSETS_JSON__",
                            json.dumps(assets, separators=(",", ":")))
    body = body.replace("__GAME_JS__", script)

    # index.html is a full document: the <title>/<meta> block marked in the
    # template belongs in <head>, the rest goes in <body>.  artifact.html keeps
    # everything together, because its host supplies the skeleton.
    head = ""
    if "<!--HEAD-->" in body and "<!--/HEAD-->" in body:
        start = body.index("<!--HEAD-->") + len("<!--HEAD-->")
        end = body.index("<!--/HEAD-->")
        head = body[start:end].strip()
        page_body = (body[:body.index("<!--HEAD-->")]
                     + body[end + len("<!--/HEAD-->"):]).strip()
    else:
        page_body = body
    page = ("<!doctype html>\n<html lang=\"en\">\n<head>\n"
            "<meta charset=\"utf-8\">\n" + head + "\n</head>\n<body>\n"
            + page_body + "\n</body>\n</html>\n")

    with open(OUT_PAGE, "w", encoding="utf-8") as handle:
        handle.write(page)
    with open(OUT_FRAGMENT, "w", encoding="utf-8") as handle:
        handle.write(body)

    before = sum(r[1] for r in report)
    after = sum(r[2] for r in report)
    print("\nassets %.1f MB -> %.1f MB embedded"
          % (before / 1048576.0, after / 1048576.0))
    print("wrote %s  (%.1f MB)"
          % (OUT_PAGE, os.path.getsize(OUT_PAGE) / 1048576.0))
    print("wrote %s  (%.1f MB)"
          % (OUT_FRAGMENT, os.path.getsize(OUT_FRAGMENT) / 1048576.0))
    print("\nOpen index.html in any browser - Mac, Windows, phone, tablet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
