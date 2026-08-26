"""Optional helper: write uniformly sized copies of the card images.

The game does NOT need this - it prepares images automatically at load time.
This utility is here for when you want the processed files on disk, e.g. to
check how a new picture will be cropped.

    python prepare_assets.py             # build assets/cards/prepared/
    python prepare_assets.py --size 400  # different output size
    python prepare_assets.py --clean     # delete the prepared folder again

Source files in assets/cards/ are never modified.  Anything found in
assets/cards/prepared/ is preferred by the game the next time it starts.
"""

import argparse
import os
import shutil
import sys

import pygame

import asset_manager as AM

BACKDROP = (255, 250, 228)      # cream, matches the game background


def prepare(size):
    pygame.init()
    pygame.display.set_mode((1, 1))            # needed for convert_alpha()
    os.makedirs(AM.PREPARED, exist_ok=True)
    made, skipped = 0, 0

    for key in AM.PAIR_KEYS + [AM.ANGRY_KEY, AM.LAUGH_KEY, AM.BACK_KEY]:
        source = None
        for ext in AM.IMAGE_EXTS:
            candidate = os.path.join(AM.CARD_DIR, key + ext)
            if os.path.isfile(candidate):
                source = candidate
                break
        if source is None:
            print("skip   %-18s (no source image found)" % key)
            skipped += 1
            continue

        try:
            image = pygame.image.load(source).convert_alpha()
        except pygame.error as exc:
            print("skip   %-18s (%s)" % (key, exc))
            skipped += 1
            continue

        canvas = pygame.Surface((size, size), pygame.SRCALPHA)
        if key in (AM.ANGRY_KEY, AM.LAUGH_KEY):
            # keep the whole character, pad with background colour
            canvas.fill(BACKDROP)
            fitted = AM._fit(image, size, size)
        else:
            # square crop, no distortion
            fitted = pygame.transform.smoothscale(
                AM._centre_crop_square(image), (size, size))
        canvas.blit(fitted, fitted.get_rect(center=(size // 2, size // 2)))

        target = os.path.join(AM.PREPARED, key + ".png")
        pygame.image.save(canvas, target)
        print("wrote  %-18s %sx%s -> %sx%s" % (key, image.get_width(),
                                               image.get_height(), size, size))
        made += 1

    pygame.quit()
    print("\n%d prepared, %d skipped -> %s" % (made, skipped, AM.PREPARED))


def clean():
    if os.path.isdir(AM.PREPARED):
        shutil.rmtree(AM.PREPARED)
        print("removed " + AM.PREPARED)
    else:
        print("nothing to remove")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--size", type=int, default=512,
                        help="edge length of the square output (default 512)")
    parser.add_argument("--clean", action="store_true",
                        help="delete the prepared folder instead")
    args = parser.parse_args()
    if args.clean:
        clean()
    else:
        prepare(max(64, args.size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
