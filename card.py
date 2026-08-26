"""One card on the board, plus its flip / match animation."""

import math
import pygame

import theme as T

NORMAL = "normal"
ANGRY = "angry"
LAUGH = "laugh"

FLIP_SPEED = 5.0        # full flip takes 1 / FLIP_SPEED seconds
MATCH_PULSE = 0.55      # seconds of the green "matched!" pulse


class Card:
    """A card knows its identity, where it is drawn and how far it is flipped.

    `turn` runs from 0.0 (fully face down) to 1.0 (fully face up); anything in
    between is the flip animation, drawn by squashing the card horizontally.
    """

    def __init__(self, index):
        self.index = index
        self.kind = NORMAL
        self.key = "pair_1"
        self.rect = pygame.Rect(0, 0, 10, 10)

        self.turn = 0.0
        self.target = 0.0
        self.matched = False
        self.locked = False      # a revealed nailong: never flips again
        self.match_pulse = 0.0
        self.hover = False

    # ------------------------------------------------------------ identity --
    def set_identity(self, kind, key):
        self.kind = kind
        self.key = key

    @property
    def identity(self):
        return (self.kind, self.key)

    # -------------------------------------------------------------- state ---
    def is_face_up(self):
        return self.target >= 1.0

    def is_face_down(self):
        return self.target <= 0.0 and self.turn <= 0.0

    def is_animating(self):
        return abs(self.turn - self.target) > 1e-6

    def clickable(self):
        return not (self.matched or self.locked or self.is_face_up()
                    or self.is_animating())

    def flip_up(self):
        self.target = 1.0

    def flip_down(self):
        self.target = 0.0

    def snap_down(self):
        """Turn face down with no animation (used before a shuffle)."""
        self.turn = 0.0
        self.target = 0.0

    def set_matched(self):
        self.matched = True
        self.target = 1.0
        self.turn = 1.0
        self.match_pulse = MATCH_PULSE

    # ------------------------------------------------------------- update ---
    def update(self, dt):
        if self.turn < self.target:
            self.turn = min(self.target, self.turn + FLIP_SPEED * dt)
        elif self.turn > self.target:
            self.turn = max(self.target, self.turn - FLIP_SPEED * dt)
        if self.match_pulse > 0.0:
            self.match_pulse = max(0.0, self.match_pulse - dt)

    # --------------------------------------------------------------- draw ---
    def draw(self, surface, assets, offset=(0, 0), time=0.0, scale=1.0,
             air=0.0):
        rect = self.rect.move(offset)
        showing_face = self.turn >= 0.5

        # Horizontal squash gives a convincing card-flip without 3D maths.
        squash = abs(math.cos(self.turn * math.pi))
        squash = max(0.06, squash) if self.is_animating() else 1.0

        art = (assets.card_face(self.kind, self.key, rect.w, rect.h)
               if showing_face else assets.card_back(rect.w, rect.h))

        lift = 0
        if self.match_pulse > 0.0:
            lift = int(6 * math.sin(math.pi * (1 - self.match_pulse / MATCH_PULSE)))
        elif self.hover and self.clickable():
            lift = 3

        draw_w = max(2, int(rect.w * squash * scale))
        draw_h = max(2, int(rect.h * scale))
        draw_rect = pygame.Rect(0, 0, draw_w, draw_h)
        draw_rect.center = (rect.centerx, rect.centery - lift)

        # a card in the air throws its shadow further away
        shadow = assets.shadow(rect.w, rect.h)
        surface.blit(shadow, (rect.x, rect.y + 8 + lift + int(14 * air)))

        if (draw_w, draw_h) != (rect.w, rect.h):
            art = pygame.transform.scale(art, (draw_w, draw_h))
        surface.blit(art, draw_rect)

        # ---- matched highlight -------------------------------------------
        if self.matched:
            T.rounded(surface, draw_rect, T.GREEN_DARK, radius=18, width=5)
            if self.match_pulse > 0.0:
                glow = pygame.Surface(draw_rect.size, pygame.SRCALPHA)
                alpha = int(150 * (self.match_pulse / MATCH_PULSE))
                T.rounded(glow, pygame.Rect(0, 0, *draw_rect.size),
                          (T.GREEN[0], T.GREEN[1], T.GREEN[2], alpha),
                          radius=18)
                surface.blit(glow, draw_rect)
            if draw_w > 46:
                radius = max(10, int(rect.w * 0.11))
                centre = (draw_rect.right - radius - 3,
                          draw_rect.top + radius + 3)
                T.check_mark(surface, centre, radius, T.GREEN_DARK, T.WHITE)

        # ---- revealed trap cards -----------------------------------------
        elif self.locked and self.kind == ANGRY:
            pulse = 3 + int(2 * math.sin(time * 6))
            T.rounded(surface, draw_rect, T.RED, radius=18, width=pulse)
        elif self.locked and self.kind == LAUGH:
            hue = T.YELLOW if int(time * 6) % 2 == 0 else T.PURPLE
            T.rounded(surface, draw_rect, hue, radius=18, width=5)

        return draw_rect
