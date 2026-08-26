"""Shared colours and font helpers for Nailong Memory Mayhem."""

import pygame

# ---------------------------------------------------------------- colours ----
BG_TOP        = (255, 250, 228)   # cream
BG_BOTTOM     = (255, 233, 210)
INK           = (74, 59, 52)
INK_SOFT      = (139, 120, 110)
PANEL         = (255, 255, 255)
PANEL_EDGE    = (238, 220, 205)

PINK          = (255, 160, 190)
PINK_DARK     = (230, 104, 148)
BLUE          = (152, 206, 246)
BLUE_DARK     = (86, 156, 218)
GREEN         = (132, 216, 156)
GREEN_DARK    = (66, 168, 102)
RED           = (240, 84, 84)
RED_DARK      = (196, 46, 46)
YELLOW        = (255, 212, 88)
YELLOW_DARK   = (226, 168, 30)
PURPLE        = (178, 132, 226)
CARD_FACE     = (255, 253, 246)
WHITE         = (255, 255, 255)
SHADOW        = (120, 96, 84)

# Playful first, sane fallbacks after.  SysFont picks the first name it finds.
FONT_STACK = "comicsansms,chalkboardse,segoeuiblack,trebuchetms,verdana,arial"

_font_cache = {}


def font(size, bold=False):
    """Cached SysFont lookup so we never build the same font twice."""
    key = (int(size), bool(bold))
    if key not in _font_cache:
        try:
            f = pygame.font.SysFont(FONT_STACK, int(size), bold=bold)
        except Exception:                                  # pragma: no cover
            f = pygame.font.Font(None, int(size))
        _font_cache[key] = f
    return _font_cache[key]


def text(surface, string, size, colour, center=None, topleft=None,
         midleft=None, midtop=None, midright=None, bold=False, shadow=False):
    """Blit one line of text and return its rect."""
    f = font(size, bold)
    img = f.render(string, True, colour)
    rect = img.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    elif midleft:
        rect.midleft = midleft
    elif midtop:
        rect.midtop = midtop
    elif midright:
        rect.midright = midright
    if shadow:
        ghost = f.render(string, True, (0, 0, 0))
        ghost.set_alpha(45)
        surface.blit(ghost, rect.move(2, 2))
    surface.blit(img, rect)
    return rect


def text_fitted(surface, string, max_size, colour, rect, bold=False, dy=0,
                padding=24):
    """Centre text in `rect`, shrinking the font until the line fits."""
    size = int(max_size)
    while size > 11 and font(size, bold).size(string)[0] > rect.width - padding:
        size -= 1
    return text(surface, string, size, colour,
                center=(rect.centerx, rect.centery + dy), bold=bold)


def check_mark(surface, centre, radius, circle_colour, tick_colour):
    """A little round matched-badge with a hand-drawn looking tick."""
    cx, cy = centre
    pygame.draw.circle(surface, circle_colour, centre, radius)
    pygame.draw.circle(surface, tick_colour, centre, radius, 2)
    points = [(cx - radius * 0.45, cy),
              (cx - radius * 0.10, cy + radius * 0.38),
              (cx + radius * 0.50, cy - radius * 0.40)]
    pygame.draw.lines(surface, tick_colour, False,
                      [(int(x), int(y)) for x, y in points],
                      max(2, int(radius * 0.28)))


def rounded(surface, rect, colour, radius=14, width=0):
    pygame.draw.rect(surface, colour, rect, width=width, border_radius=radius)
