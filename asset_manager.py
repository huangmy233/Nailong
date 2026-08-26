"""Loading, automatic preparation and caching of images and sounds.

Everything is addressed through paths relative to this file, so the project
folder can be copied to another computer and still run.

Image preparation rules (done once, at load time, then cached):
  * normal pair images  -> centre-cropped to a square, then smoothscaled
  * nailong trap images -> scaled proportionally to fit inside the card
Nothing is ever stretched, and the source files on disk are never modified.
"""

import os
import pygame

import paths
import theme as T

# inside a packaged build this points at the unpacked bundle, not the source
BASE_DIR = paths.data_dir()
ASSET_DIR = os.path.join(BASE_DIR, "assets")
CARD_DIR = os.path.join(ASSET_DIR, "cards")
SOUND_DIR = os.path.join(ASSET_DIR, "sounds")
PREPARED = os.path.join(CARD_DIR, "prepared")   # optional, made by prepare_assets.py

PAIR_KEYS = ["pair_%d" % i for i in range(1, 8)]
ANGRY_KEY = "angry_nailong"
LAUGH_KEY = "laughing_nailong"
BACK_KEY = "card_back"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG")

SOUND_NAMES = ("angry", "laugh", "flip", "match", "victory")
BASE_VOLUME = {"angry": 0.75, "laugh": 0.45, "flip": 0.35,
               "match": 0.55, "victory": 0.65}
LAUGH_CHANNEL = 0


# --------------------------------------------------------------- helpers ----
def _centre_crop_square(surface):
    """Return the largest centred square of surface (never distorted)."""
    w, h = surface.get_size()
    side = min(w, h)
    rect = pygame.Rect((w - side) // 2, (h - side) // 2, side, side)
    return surface.subsurface(rect).copy()


def _fit(surface, box_w, box_h):
    """Proportionally scale surface so the whole image fits in the box."""
    w, h = surface.get_size()
    if w <= 0 or h <= 0:
        return surface
    scale = min(box_w / w, box_h / h)
    size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    return pygame.transform.smoothscale(surface, size)


def _placeholder(w, h, label):
    """A clearly labelled stand-in used when an image will not load."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    T.rounded(surf, pygame.Rect(0, 0, w, h), (236, 224, 214), radius=12)
    T.rounded(surf, pygame.Rect(0, 0, w, h), T.RED, radius=12, width=3)
    T.text(surf, "?", int(h * 0.45), T.RED, center=(w // 2, int(h * 0.42)))
    T.text(surf, label[:12], max(11, int(h * 0.11)), T.INK_SOFT,
           center=(w // 2, int(h * 0.78)))
    return surf


# ---------------------------------------------------------------- manager ----
class AssetManager:
    def __init__(self, audio_ok=True):
        self.audio_ok = audio_ok
        self.muted = False
        self._raw = {}        # key -> Surface or None
        self._cache = {}      # (kind, key, w, h) -> Surface
        self.sounds = {}
        self._laugh_channel = None
        self.warnings = []
        self._load_sounds()

    # ------------------------------------------------------------ images ---
    def _find_image(self, key):
        """Prefer a file produced by prepare_assets.py, else the original."""
        for folder in (PREPARED, CARD_DIR):
            for ext in IMAGE_EXTS:
                path = os.path.join(folder, key + ext)
                if os.path.isfile(path):
                    return path
        return None

    def _warn(self, message):
        if message not in self.warnings:
            self.warnings.append(message)
            print("[assets] " + message)

    def raw(self, key):
        """Load (once) the untouched source image.  None if unavailable."""
        if key in self._raw:
            return self._raw[key]
        path = self._find_image(key)
        surface = None
        if path is None:
            self._warn("missing image for '%s' - expected %s.png or .jpg in %s"
                       % (key, key, CARD_DIR))
        else:
            try:
                surface = pygame.image.load(path).convert_alpha()
            except pygame.error as exc:
                self._warn("could not load %s: %s" % (path, exc))
                surface = None
        self._raw[key] = surface
        return surface

    def square(self, key, side):
        """Centre-cropped square version of an image, scaled to side x side."""
        cache_key = ("sq", key, side, side)
        if cache_key not in self._cache:
            src = self.raw(key)
            if src is None:
                out = _placeholder(side, side, key)
            else:
                out = pygame.transform.smoothscale(
                    _centre_crop_square(src), (side, side))
            self._cache[cache_key] = out
        return self._cache[cache_key]

    def contained(self, key, box_w, box_h):
        """Whole image, proportionally fitted inside the box."""
        cache_key = ("fit", key, box_w, box_h)
        if cache_key not in self._cache:
            src = self.raw(key)
            if src is None:
                out = _placeholder(box_w, box_h, key)
            else:
                out = _fit(src, box_w, box_h)
            self._cache[cache_key] = out
        return self._cache[cache_key]

    # ------------------------------------------------ whole card surfaces ---
    def card_back(self, w, h):
        """The one shared face-down design, pre-rendered and cached."""
        cache_key = ("back", BACK_KEY, w, h)
        if cache_key in self._cache:
            return self._cache[cache_key]

        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        body = pygame.Rect(0, 0, w, h)
        T.rounded(surf, body, T.PINK, radius=18)
        inner = body.inflate(-int(w * 0.10), -int(h * 0.085))
        T.rounded(surf, inner, T.BLUE, radius=14)

        art_side = min(inner.w, inner.h) - 6
        if art_side > 8:
            art = self.square(BACK_KEY, art_side).copy()
            mask = pygame.Surface((art_side, art_side), pygame.SRCALPHA)
            T.rounded(mask, pygame.Rect(0, 0, art_side, art_side),
                      (255, 255, 255, 255), radius=12)
            art.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            surf.blit(art, art.get_rect(center=inner.center))

        T.rounded(surf, body, T.WHITE, radius=18, width=4)
        T.rounded(surf, body, T.PINK_DARK, radius=18, width=2)
        self._cache[cache_key] = surf
        return surf

    def card_face(self, kind, key, w, h):
        """Face-up card art (shell + prepared image), pre-rendered + cached."""
        cache_key = ("face", key, w, h)
        if cache_key in self._cache:
            return self._cache[cache_key]

        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        body = pygame.Rect(0, 0, w, h)
        if kind == "angry":
            fill, edge = (255, 232, 232), T.RED
        elif kind == "laugh":
            fill, edge = (255, 246, 214), T.PURPLE
        else:
            fill, edge = T.CARD_FACE, T.PINK
        T.rounded(surf, body, fill, radius=18)

        margin = max(7, int(w * 0.085))
        inner = body.inflate(-2 * margin, -2 * margin)
        if kind == "normal":
            side = min(inner.w, inner.h)
            art = self.square(key, side)
        else:
            # keep the whole character; the card fill provides the extra space
            art = self.contained(key, inner.w, inner.h)
        surf.blit(art, art.get_rect(center=inner.center))

        T.rounded(surf, body, T.WHITE, radius=18, width=4)
        T.rounded(surf, body, edge, radius=18, width=2)
        self._cache[cache_key] = surf
        return surf

    def shadow(self, w, h):
        cache_key = ("shadow", "-", w, h)
        if cache_key not in self._cache:
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            inset = max(3, int(w * 0.05))
            T.rounded(surf, pygame.Rect(inset, inset,
                                        w - 2 * inset, h - 2 * inset),
                      (T.SHADOW[0], T.SHADOW[1], T.SHADOW[2], 46), radius=16)
            self._cache[cache_key] = surf
        return self._cache[cache_key]

    def drop_size_cache(self):
        """Called when the window resizes: scaled surfaces are rebuilt once."""
        self._cache.clear()

    # ------------------------------------------------------------ sounds ---
    def _load_sounds(self):
        for name in SOUND_NAMES:
            self.sounds[name] = None
            if not self.audio_ok:
                continue
            path = os.path.join(SOUND_DIR, name + ".wav")
            if not os.path.isfile(path):
                self._warn("missing sound %s.wav - continuing without it"
                           % name)
                continue
            try:
                snd = pygame.mixer.Sound(path)
                snd.set_volume(BASE_VOLUME[name])
                self.sounds[name] = snd
            except pygame.error as exc:
                self._warn("could not load sound %s: %s" % (path, exc))

    def play(self, name):
        snd = self.sounds.get(name)
        if not self.audio_ok or snd is None:
            return
        snd.set_volume(0.0 if self.muted else BASE_VOLUME[name])
        try:
            snd.play()
        except pygame.error:
            pass

    def start_laugh(self):
        """Loop the laughter until stop_laugh() is called."""
        snd = self.sounds.get("laugh")
        if not self.audio_ok or snd is None:
            return
        try:
            channel = pygame.mixer.Channel(LAUGH_CHANNEL)
            channel.play(snd, loops=-1)
            channel.set_volume(0.0 if self.muted else BASE_VOLUME["laugh"])
            self._laugh_channel = channel
        except pygame.error:
            self._laugh_channel = None

    def stop_laugh(self):
        if self._laugh_channel is not None:
            try:
                self._laugh_channel.stop()
            except pygame.error:
                pass
            self._laugh_channel = None

    def laughing(self):
        try:
            return (self._laugh_channel is not None
                    and self._laugh_channel.get_busy())
        except pygame.error:
            return False

    def set_muted(self, muted):
        """Mute/unmute without touching game state or restarting a sound."""
        self.muted = bool(muted)
        for name, snd in self.sounds.items():
            if snd is not None:
                snd.set_volume(0.0 if self.muted else BASE_VOLUME[name])
        if self._laugh_channel is not None:
            try:
                self._laugh_channel.set_volume(
                    0.0 if self.muted else BASE_VOLUME["laugh"])
            except pygame.error:
                pass

    def toggle_mute(self):
        self.set_muted(not self.muted)
        return self.muted

    def shutdown(self):
        self.stop_laugh()
        if self.audio_ok:
            try:
                pygame.mixer.stop()
            except pygame.error:
                pass
