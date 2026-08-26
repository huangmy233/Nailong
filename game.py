"""Nailong Memory Mayhem - game states, board logic and drawing."""

import math
import random
import sys

import pygame

import records
import theme as T
from asset_manager import (AssetManager, ANGRY_KEY, LAUGH_KEY, PAIR_KEYS)
from card import Card, ANGRY, LAUGH, NORMAL

# ------------------------------------------------------------------ tuning ---
DEFAULT_SIZE = (1020, 900)      # shrunk to fit smaller screens automatically
MIN_SIZE = (760, 640)
FPS = 60

GRID = 4
PAIR_COUNT = 7
CARD_ASPECT = 0.92              # card width / card height
GAP_RATIO = 0.10

COMPARE_TIME = 0.80             # how long a mismatch stays visible
SHUFFLE_LEAD = 0.35             # card flip is seen before the board shakes
TRAVEL_TIME = 0.95              # cards flying to their new slots
TRAVEL_STAGGER = 0.28           # cards do not all take off at once
TRAVEL_PULL = 0.28              # how far the paths bend towards the centre
TRAVEL_SPIN = 0.55              # radians the whole board appears to swirl
SHUFFLE_TOTAL = SHUFFLE_LEAD + TRAVEL_TIME + 0.30   # timer paused throughout
SHAKE_TIME = 0.75
FLASH_TIME = 0.50
TOAST_TIME = 2.60

# game states
TITLE = "title"
PLAYING = "playing"
COMPARE = "compare"
SHUFFLE = "shuffle"
VICTORY = "victory"

MSG_ANGRY = "ANGRY NAILONG SHUFFLED THE BOARD!"
MSG_LAUGH = "LAUGHING NAILONG WILL LAUGH FOR THE REST OF THE GAME!"
MSG_HIDING = "All pairs matched—but a Nailong is still hiding!"
CREDIT = "Produced by Mingyi"


NO_TIME = "--:--.--"


def format_time(seconds):
    """mm:ss.cc - the timer is accurate to a hundredth of a second."""
    minutes = int(seconds) // 60
    return "%02d:%05.2f" % (minutes, seconds - 60 * minutes)


class Button:
    def __init__(self, name, label, colour, text_colour=None, small=False):
        self.name = name
        self.label = label
        self.colour = colour
        self.text_colour = text_colour or T.WHITE
        self.small = small
        self.rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, surface, mouse, scale=1.0):
        hot = self.rect.collidepoint(mouse)
        rect = self.rect.inflate(4, 4) if hot else self.rect
        shade = tuple(max(0, c - 40) for c in self.colour)
        T.rounded(surface, rect.move(0, 4), shade, radius=16)
        T.rounded(surface, rect, self.colour, radius=16)
        T.rounded(surface, rect, T.WHITE, radius=16, width=3)
        size = (20 if self.small else 27) * scale
        T.text(surface, self.label, size, self.text_colour, center=rect.center,
               bold=True)

    def hit(self, pos):
        return self.rect.collidepoint(pos)


class Game:
    def __init__(self):
        pygame.init()
        self.audio_ok = self._init_audio()

        info = pygame.display.Info()
        width = max(MIN_SIZE[0], min(DEFAULT_SIZE[0], info.current_w - 60))
        height = max(MIN_SIZE[1], min(DEFAULT_SIZE[1], info.current_h - 110))
        self.screen = pygame.display.set_mode((width, height),
                                              pygame.RESIZABLE)
        pygame.display.set_caption("Nailong Memory Mayhem")

        self.clock = pygame.time.Clock()
        self.assets = AssetManager(audio_ok=self.audio_ok)
        self._set_icon()

        self.state = TITLE
        self.running = True
        self.now = 0.0                # animation clock, always advancing
        self.background = None
        self.scale = 1.0

        self.cards = [Card(i) for i in range(GRID * GRID)]
        self.buttons = {}
        self._build_buttons()
        self._layout()

        self.record = records.load()
        self.toasts = []
        self.confirm_restart = False
        self.improved = []
        self.mouse = (0, 0)

        self.reset_game()       # deal a board so nothing is ever undefined
        self.state = TITLE      # ...but the player starts on the title screen

    # ------------------------------------------------------------- set-up ---
    def _init_audio(self):
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            return True
        except pygame.error as exc:
            print("[audio] no audio device (%s) - running silently" % exc)
            return False

    def _set_icon(self):
        art = self.assets.raw(ANGRY_KEY)
        if art is not None:
            try:
                pygame.display.set_icon(
                    pygame.transform.smoothscale(art, (32, 32)))
            except pygame.error:
                pass

    def _build_buttons(self):
        self.buttons = {
            "start": Button("start", "Start Game", T.GREEN_DARK),
            "quit_title": Button("quit_title", "Quit", T.PINK_DARK),
            "sound_title": Button("sound_title", "Sound: ON", T.BLUE_DARK),
            "mute": Button("mute", "Sound: ON", T.BLUE_DARK, small=True),
            "restart": Button("restart", "Restart", T.YELLOW_DARK, small=True),
            "title": Button("title", "Title", T.PINK_DARK, small=True),
            "again": Button("again", "Play Again", T.GREEN_DARK),
            "to_title": Button("to_title", "Title Screen", T.BLUE_DARK),
            "quit_win": Button("quit_win", "Quit", T.PINK_DARK),
            "yes": Button("yes", "Yes, restart", T.GREEN_DARK),
            "no": Button("no", "Keep playing", T.BLUE_DARK),
        }

    def _layout(self):
        """Recompute every rectangle from the current window size."""
        w, h = self.screen.get_size()
        self.w, self.h = w, h
        self.scale = max(0.75, min(1.15, h / 900.0))
        s = self.scale

        self.hud_rect = pygame.Rect(int(22 * s), int(14 * s),
                                    w - int(44 * s), int(60 * s))
        self.stats_rect = pygame.Rect(self.hud_rect.left,
                                      self.hud_rect.bottom + int(10 * s),
                                      self.hud_rect.width, int(46 * s))
        footer_top = h - int(96 * s)
        board_top = self.stats_rect.bottom + int(14 * s)

        avail_h = footer_top - board_top - int(8 * s)
        avail_w = w - int(64 * s)
        gap = max(8, int(min(avail_w, avail_h) * GAP_RATIO / GRID))
        cell_h = (avail_h - (GRID - 1) * gap) / GRID
        cell_w = min(cell_h * CARD_ASPECT, (avail_w - (GRID - 1) * gap) / GRID)
        cell_h = min(cell_h, cell_w / CARD_ASPECT)
        cell_w, cell_h = int(cell_w), int(cell_h)

        board_w = GRID * cell_w + (GRID - 1) * gap
        board_h = GRID * cell_h + (GRID - 1) * gap
        board_x = (w - board_w) // 2
        board_y = board_top + max(0, (avail_h - board_h) // 2)
        self.board_rect = pygame.Rect(board_x, board_y, board_w, board_h)
        self.cell = (cell_w, cell_h)

        for index, card in enumerate(self.cards):
            row, col = divmod(index, GRID)
            card.rect = pygame.Rect(board_x + col * (cell_w + gap),
                                    board_y + row * (cell_h + gap),
                                    cell_w, cell_h)

        self.toast_rect = pygame.Rect(0, 0, min(w - 40, int(760 * s)),
                                      int(46 * s))
        self.toast_rect.center = (w // 2, footer_top + int(26 * s))
        self.footer_y = h - int(24 * s)

        # HUD buttons, right aligned
        bw, bh = int(132 * s), int(36 * s)
        x = self.hud_rect.right - int(12 * s)
        for name in ("title", "restart", "mute"):
            self.buttons[name].rect = pygame.Rect(x - bw,
                                                  self.hud_rect.centery - bh // 2,
                                                  bw, bh)
            x -= bw + int(10 * s)

        # ---- title screen: one vertical stack, measured so nothing overlaps
        cx = w // 2
        self.tl = {}
        y = int(62 * s)
        self.tl["title1"] = y
        # room for the descenders of "Nailong Memory" plus the MAYHEM bob
        y += int(96 * s)
        self.tl["title2"] = y
        art = int(min(h * 0.185, w * 0.22))
        self.tl["art_h"] = art
        y += int(66 * s) + art // 2
        self.tl["art_y"] = y
        y += art // 2 + int(64 * s)      # leaves room for the ANGRY / LAUGHING labels
        line_h = int(28 * s)
        self.tl["line_h"] = line_h
        self.tl["text_top"] = y
        y += 4 * line_h + int(34 * s)

        bw, bh = int(300 * s), int(58 * s)
        self.buttons["start"].rect = pygame.Rect(0, 0, bw, bh)
        self.buttons["start"].rect.center = (cx, y + bh // 2)
        y += bh + int(14 * s)
        sw, sh = int(230 * s), int(46 * s)
        self.buttons["sound_title"].rect = pygame.Rect(0, 0, sw, sh)
        self.buttons["sound_title"].rect.center = (cx, y + sh // 2)
        y += sh + int(12 * s)
        self.buttons["quit_title"].rect = pygame.Rect(0, 0, sw, sh)
        self.buttons["quit_title"].rect.center = (cx, y + sh // 2)
        # best record on the left, the credit on the right, one shared row
        self.tl["bottom_y"] = max(y + sh + int(26 * s), h - int(50 * s))

        # ---- victory panel and its buttons
        vh = int(52 * s)
        self.victory_rect = pygame.Rect(0, 0, min(w - 50, int(700 * s)),
                                        int(344 * s))
        self.victory_rect.center = (cx, h // 2)
        vw = int(min(200 * s, (self.victory_rect.width - 4 * 14 * s) / 3))
        gapx = int(14 * s)
        left = cx - (3 * vw + 2 * gapx) // 2
        row_y = self.victory_rect.bottom - int(28 * s) - vh
        for i, name in enumerate(("again", "to_title", "quit_win")):
            self.buttons[name].rect = pygame.Rect(
                left + i * (vw + gapx), row_y, vw, vh)

        # ---- confirm dialog
        self.confirm_rect = pygame.Rect(0, 0, min(w - 60, int(540 * s)),
                                        int(216 * s))
        self.confirm_rect.center = (cx, h // 2)
        cw, ch = int(200 * s), int(48 * s)
        row_y = self.confirm_rect.bottom - int(26 * s) - ch
        self.buttons["yes"].rect = pygame.Rect(
            self.confirm_rect.centerx - cw - int(9 * s), row_y, cw, ch)
        self.buttons["no"].rect = pygame.Rect(
            self.confirm_rect.centerx + int(9 * s), row_y, cw, ch)

        self.background = self._make_background(w, h)

    def _make_background(self, w, h):
        surf = pygame.Surface((w, h))
        for y in range(h):
            t = y / max(1, h - 1)
            colour = tuple(int(T.BG_TOP[i] + (T.BG_BOTTOM[i] - T.BG_TOP[i]) * t)
                           for i in range(3))
            pygame.draw.line(surf, colour, (0, y), (w, y))
        return surf

    # --------------------------------------------------------- new deal ---
    def reset_game(self):
        """Deal a fresh board.  Safe to call at any moment."""
        self.assets.stop_laugh()
        deck = [(NORMAL, key) for key in PAIR_KEYS for _ in (0, 1)]
        deck.append((ANGRY, ANGRY_KEY))
        deck.append((LAUGH, LAUGH_KEY))
        assert len(deck) == GRID * GRID
        random.shuffle(deck)

        for card, identity in zip(self.cards, deck):
            card.matched = False
            card.locked = False
            card.turn = 0.0
            card.target = 0.0
            card.match_pulse = 0.0
            card.set_identity(*identity)

        self.first = None
        self.second = None
        self.compare_timer = 0.0
        self.shuffle_timer = 0.0
        self.shuffled_yet = False
        self.travel = {}
        self.travel_t = 1.0
        self.shake_timer = 0.0
        self.flash_timer = 0.0
        self.elapsed = 0.0
        self.flips = 0
        self.pairs_found = 0
        self.timer_running = False
        self.angry_done = False
        self.laugh_done = False
        self.confirm_restart = False
        self.improved = []
        self.toasts = []
        self.state = PLAYING

    def go_to_title(self):
        self.assets.stop_laugh()
        self.confirm_restart = False
        self.state = TITLE

    # ------------------------------------------------------------- toasts ---
    def toast(self, text, colour):
        if self.toasts and self.toasts[0][0] == text:
            return
        for queued in self.toasts:
            if queued[0] == text:
                return
        if self.toasts:
            # let the banner already on screen bow out quickly
            self.toasts[0][2] = min(self.toasts[0][2], 0.5)
        self.toasts.append([text, colour, TOAST_TIME])

    # -------------------------------------------------------------- input ---
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEORESIZE:
            size = (max(MIN_SIZE[0], event.w), max(MIN_SIZE[1], event.h))
            self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
            self.assets.drop_size_cache()
            self._layout()
            return
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
            return
        if event.type == pygame.KEYDOWN:
            self._on_key(event.key)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.mouse = event.pos
            self._on_click(event.pos)

    def _on_key(self, key):
        if key == pygame.K_m:
            muted = self.assets.toggle_mute()
            self._sync_sound_labels()
            self.toast("SOUND MUTED" if muted else "SOUND ON", T.BLUE_DARK)
            return

        if self.confirm_restart:
            if key in (pygame.K_y, pygame.K_RETURN, pygame.K_r):
                self.reset_game()
            elif key in (pygame.K_n, pygame.K_ESCAPE):
                self.confirm_restart = False
            return

        if key == pygame.K_ESCAPE:
            if self.state == TITLE:
                self.running = False
            else:
                self.go_to_title()
            return

        if key == pygame.K_r:
            if self.state == TITLE:
                return
            self._request_restart()
            return

        if key in (pygame.K_RETURN, pygame.K_SPACE) and self.state == TITLE:
            self.reset_game()

    def _request_restart(self):
        """Ask first if a game is actually in progress."""
        in_progress = (self.state in (PLAYING, COMPARE, SHUFFLE)
                       and (self.flips > 0 or self.pairs_found > 0))
        if in_progress:
            self.confirm_restart = True
        else:
            self.reset_game()

    def _on_click(self, pos):
        buttons = self.buttons
        if self.confirm_restart:
            if buttons["yes"].hit(pos):
                self.reset_game()
            elif buttons["no"].hit(pos):
                self.confirm_restart = False
            return

        if self.state == TITLE:
            if buttons["start"].hit(pos):
                self.reset_game()
            elif buttons["quit_title"].hit(pos):
                self.running = False
            elif buttons["sound_title"].hit(pos):
                self.assets.toggle_mute()
                self._sync_sound_labels()
            return

        if self.state == VICTORY:
            if buttons["again"].hit(pos):
                self.reset_game()
            elif buttons["to_title"].hit(pos):
                self.go_to_title()
            elif buttons["quit_win"].hit(pos):
                self.running = False
            return

        # in-game HUD buttons work in every play state
        if buttons["mute"].hit(pos):
            muted = self.assets.toggle_mute()
            self._sync_sound_labels()
            self.toast("SOUND MUTED" if muted else "SOUND ON", T.BLUE_DARK)
            return
        if buttons["restart"].hit(pos):
            self._request_restart()
            return
        if buttons["title"].hit(pos):
            self.go_to_title()
            return

        # cards only respond while the board is idle
        if self.state != PLAYING:
            return
        for card in self.cards:
            if card.rect.collidepoint(pos):
                self._click_card(card)
                break

    def _sync_sound_labels(self):
        label = "Sound: OFF" if self.assets.muted else "Sound: ON"
        self.buttons["mute"].label = label
        self.buttons["sound_title"].label = label

    # ---------------------------------------------------------- card logic ---
    def _click_card(self, card):
        if not card.clickable():
            return                       # matched, already up, or animating
        if self.first is not None and card is self.cards[self.first]:
            return

        self.timer_running = True
        self.flips += 1
        card.flip_up()
        self.assets.play("flip")

        if card.kind == ANGRY:
            self._trigger_angry(card)
        elif card.kind == LAUGH:
            self._trigger_laugh(card)
        elif self.first is None:
            self.first = card.index
        else:
            self.second = card.index
            self.compare_timer = COMPARE_TIME
            self.state = COMPARE

    def _clear_attempt(self):
        """Turn a lone face-up normal card back down."""
        if self.first is not None:
            self.cards[self.first].flip_down()
        self.first = None
        self.second = None

    def _trigger_angry(self, card):
        self.assets.play("angry")
        card.locked = True
        self.angry_done = True
        self._clear_attempt()
        self.state = SHUFFLE
        self.shuffle_timer = 0.0
        self.shuffled_yet = False
        self.flash_timer = FLASH_TIME
        self.shake_timer = SHAKE_TIME
        self.toast(MSG_ANGRY, T.RED_DARK)

    def _trigger_laugh(self, card):
        card.locked = True
        self.laugh_done = True
        self._clear_attempt()
        self.assets.start_laugh()
        self.toast(MSG_LAUGH, T.PURPLE)
        self._check_progress()

    def _shuffle_face_down(self):
        """Permute the identities of every eligible face-down card.

        Matched cards and revealed nailongs keep their place, so the board
        always still holds exactly the same 16 cards and every remaining
        picture keeps exactly one partner.

        The permutation is also handed to the travel animation: the card that
        used to sit in slot A is drawn flying from A to its new slot, so what
        the player sees is exactly what happened to the deck.
        """
        movable = [c for c in self.cards if not c.matched and not c.locked]
        if len(movable) < 2:
            return

        # order[slot] = which movable card's identity lands in that slot
        order = list(range(len(movable)))
        random.shuffle(order)
        for i in range(len(order)):        # make sure nothing stays put
            if order[i] == i:
                choices = [k for k in range(len(order)) if k != i]
                j = random.choice(choices)
                order[i], order[j] = order[j], order[i]

        identities = [card.identity for card in movable]
        self.travel = {}
        self.travel_t = 0.0
        for slot, source in enumerate(order):
            card = movable[slot]
            card.snap_down()
            card.set_identity(*identities[source])
            self.travel[card.index] = (movable[source].rect.center,
                                       random.uniform(0.0, TRAVEL_STAGGER))

    def _travel_state(self, card):
        """Where a card is along its flight, or None if it is home.

        Returns (dx, dy, scale, air) as an offset from the card's own slot.
        """
        entry = self.travel.get(card.index)
        if entry is None or self.travel_t >= 1.0:
            return None
        origin, delay = entry
        span = max(0.05, 1.0 - TRAVEL_STAGGER)
        t = min(1.0, max(0.0, (self.travel_t - delay) / span))
        if t >= 1.0:
            return None

        home = card.rect.center
        ease = t * t * (3.0 - 2.0 * t)                   # smooth start and stop
        x = origin[0] + (home[0] - origin[0]) * ease
        y = origin[1] + (home[1] - origin[1]) * ease

        arc = math.sin(math.pi * t)                      # 0 -> 1 -> 0
        cx, cy = self.board_rect.center
        x += (cx - x) * TRAVEL_PULL * arc                # gather inwards...
        y += (cy - y) * TRAVEL_PULL * arc
        angle = TRAVEL_SPIN * arc                        # ...and swirl around
        dx, dy = x - cx, y - cy
        x = cx + dx * math.cos(angle) - dy * math.sin(angle)
        y = cy + dx * math.sin(angle) + dy * math.cos(angle)

        return (int(round(x - home[0])), int(round(y - home[1])),
                1.0 + 0.13 * arc, arc)

    # ------------------------------------------------------------- updates --
    def update(self, dt):
        self.now += dt
        for card in self.cards:
            card.hover = card.rect.collidepoint(self.mouse)
            card.update(dt)

        if self.toasts:
            self.toasts[0][2] -= dt
            if self.toasts[0][2] <= 0:
                self.toasts.pop(0)

        self.flash_timer = max(0.0, self.flash_timer - dt)
        self.shake_timer = max(0.0, self.shake_timer - dt)
        if self.travel_t < 1.0:
            self.travel_t = min(1.0, self.travel_t + dt / TRAVEL_TIME)
            if self.travel_t >= 1.0:
                self.travel = {}

        if self.confirm_restart:
            return                      # everything pauses behind the dialog

        if self.state == COMPARE:
            self.elapsed += dt
            self.compare_timer -= dt
            if self.compare_timer <= 0:
                self._resolve_compare()
        elif self.state == PLAYING:
            if self.timer_running:
                self.elapsed += dt
        elif self.state == SHUFFLE:
            # the timer is deliberately frozen here
            self.shuffle_timer += dt
            if not self.shuffled_yet and self.shuffle_timer >= SHUFFLE_LEAD:
                self._shuffle_face_down()
                self.shuffled_yet = True
            if self.shuffle_timer >= SHUFFLE_TOTAL:
                self.state = PLAYING
                # the angry card may have been the last thing left to find
                self._check_progress()

    def _resolve_compare(self):
        first = self.cards[self.first]
        second = self.cards[self.second]
        if first.key == second.key:
            first.set_matched()
            second.set_matched()
            self.pairs_found += 1
            self.assets.play("match")
        else:
            first.flip_down()
            second.flip_down()
        self.first = None
        self.second = None
        self.state = PLAYING
        self._check_progress()

    def _check_progress(self):
        if self.pairs_found < PAIR_COUNT:
            return
        if self.angry_done and self.laugh_done:
            self._win()
        else:
            self.toast(MSG_HIDING, T.YELLOW_DARK)

    def _win(self):
        self.state = VICTORY
        self.timer_running = False
        self.assets.stop_laugh()
        self.assets.play("victory")
        self.record, self.improved = records.submit(
            self.elapsed, self.flips, self.record)

    # --------------------------------------------------------------- draw ---
    def draw(self):
        screen = self.screen
        screen.blit(self.background, (0, 0))

        if self.state == TITLE:
            self._draw_title()
        else:
            self._draw_hud()
            self._draw_board()
            self._draw_footer()
            if self.state == VICTORY:
                self._draw_victory()

        if self.flash_timer > 0:
            flash = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            alpha = int(150 * (self.flash_timer / FLASH_TIME))
            flash.fill((T.RED[0], T.RED[1], T.RED[2], alpha))
            screen.blit(flash, (0, 0))

        if self.confirm_restart:
            self._draw_confirm()

        pygame.display.flip()

    # ---- title -------------------------------------------------------------
    def _draw_title(self):
        s = self.scale
        cx = self.w // 2
        tl = self.tl
        bob = int(4 * math.sin(self.now * 2.2))
        T.text(self.screen, "Nailong Memory", int(66 * s), T.PINK_DARK,
               center=(cx, tl["title1"]), bold=True, shadow=True)
        T.text(self.screen, "MAYHEM", int(76 * s), T.BLUE_DARK,
               center=(cx, tl["title2"] + bob), bold=True, shadow=True)

        art_h = tl["art_h"]
        angry = self.assets.contained(ANGRY_KEY, art_h, art_h)
        laugh = self.assets.contained(LAUGH_KEY, art_h, art_h)
        gap = int(46 * s)
        for art, dx, label, colour in (
                (angry, -art_h // 2 - gap // 2, "ANGRY", T.RED),
                (laugh, art_h // 2 + gap // 2, "LAUGHING", T.PURPLE)):
            rect = art.get_rect(center=(cx + dx, tl["art_y"]))
            frame = rect.inflate(10, 10)
            T.rounded(self.screen, frame, colour, radius=14)
            T.rounded(self.screen, frame, T.WHITE, radius=14, width=3)
            self.screen.blit(art, rect)
            T.text(self.screen, label, int(20 * s), colour,
                   midtop=(rect.centerx, frame.bottom + int(4 * s)), bold=True)

        lines = [
            "Find all 7 matching pairs on the 4x4 board.",
            "Two Nailongs hide in there and they have no partner.",
            "Angry Nailong reshuffles every card still face down.",
            "Laughing Nailong cackles for the rest of the game.",
            "Match all 7 pairs AND find both Nailongs to win!",
        ]
        for i, line in enumerate(lines):
            colour = T.INK if i % 2 == 0 else T.INK_SOFT
            T.text(self.screen, line, int(23 * s), colour,
                   center=(cx, tl["text_top"] + i * tl["line_h"]))

        for name in ("start", "sound_title", "quit_title"):
            self.buttons[name].draw(self.screen, self.mouse, self.scale)

        if records.has_any(self.record):
            T.text(self.screen, self.record_line(), int(20 * s), T.GREEN_DARK,
                   midleft=(int(26 * s), tl["bottom_y"]), bold=True)
        T.text(self.screen, CREDIT, int(19 * s), T.PINK_DARK,
               midright=(self.w - int(26 * s), tl["bottom_y"]), bold=True)
        T.text(self.screen, "Left click a card   -   M mute   -   R restart"
                            "   -   ESC quit", int(18 * s), T.INK_SOFT,
               center=(cx, self.h - int(22 * s)))

    def record_line(self):
        """One compact line naming both leaderboards."""
        time_board = self.record.get("time")
        flip_board = self.record.get("flips")
        parts = []
        if time_board:
            parts.append("Best time %s" % format_time(time_board["time"]))
        if flip_board:
            parts.append("Fewest flips %d" % flip_board["flips"])
        return "   |   ".join(parts)

    # ---- hud ---------------------------------------------------------------
    def _draw_hud(self):
        s = self.scale
        T.rounded(self.screen, self.hud_rect, T.PANEL, radius=18)
        T.rounded(self.screen, self.hud_rect, T.PANEL_EDGE, radius=18, width=2)
        T.text(self.screen, "Nailong Memory Mayhem", int(30 * s), T.PINK_DARK,
               midleft=(self.hud_rect.left + int(18 * s),
                        self.hud_rect.centery), bold=True)
        for name in ("mute", "restart", "title"):
            self.buttons[name].draw(self.screen, self.mouse, self.scale)

        # --- stats strip
        T.rounded(self.screen, self.stats_rect, T.PANEL, radius=16)
        T.rounded(self.screen, self.stats_rect, T.PANEL_EDGE, radius=16, width=2)
        time_board = self.record.get("time")
        flip_board = self.record.get("flips")
        best = format_time(time_board["time"]) if time_board else NO_TIME
        best_flips = str(flip_board["flips"]) if flip_board else "--"
        stats = [
            ("TIME", format_time(self.elapsed), T.BLUE_DARK),
            ("FLIPS", str(self.flips), T.PINK_DARK),
            ("PAIRS", "%d / %d" % (self.pairs_found, PAIR_COUNT), T.GREEN_DARK),
            ("BEST TIME", best, T.YELLOW_DARK),
            ("BEST FLIPS", best_flips, T.YELLOW_DARK),
            ("SOUND", "OFF" if self.assets.muted else "ON",
             T.INK_SOFT if self.assets.muted else T.BLUE_DARK),
        ]
        cell_w = self.stats_rect.width / len(stats)
        for i, (label, value, colour) in enumerate(stats):
            cx = int(self.stats_rect.left + cell_w * (i + 0.5))
            T.text(self.screen, label, int(15 * s), T.INK_SOFT,
                   center=(cx, self.stats_rect.top + int(14 * s)))
            T.text(self.screen, value, int(24 * s), colour,
                   center=(cx, self.stats_rect.top + int(32 * s)), bold=True)
            if i:
                x = int(self.stats_rect.left + cell_w * i)
                pygame.draw.line(self.screen, T.PANEL_EDGE,
                                 (x, self.stats_rect.top + 8),
                                 (x, self.stats_rect.bottom - 8), 2)

    # ---- board -------------------------------------------------------------
    def _draw_board(self):
        offset = (0, 0)
        if self.shake_timer > 0:
            power = 14 * (self.shake_timer / SHAKE_TIME)
            offset = (int(math.sin(self.now * 47) * power),
                      int(math.cos(self.now * 39) * power * 0.6))

        panel = self.board_rect.inflate(int(26 * self.scale),
                                        int(26 * self.scale)).move(offset)
        T.rounded(self.screen, panel, (255, 255, 255, 120), radius=24)
        T.rounded(self.screen, panel, T.PANEL_EDGE, radius=24, width=3)

        laugh_rect = None
        in_flight = []
        revealed = []
        for card in self.cards:
            flight = self._travel_state(card)
            if flight is not None:
                in_flight.append((card, flight))
            elif card.locked:
                revealed.append(card)       # drawn last: never buried
            else:
                card.draw(self.screen, self.assets, offset, self.now)

        # flying cards go above the table, lower ones last so they overlap
        in_flight.sort(key=lambda item: item[0].rect.centery + item[1][1])
        for card, (dx, dy, bump, air) in in_flight:
            card.draw(self.screen, self.assets,
                      (offset[0] + dx, offset[1] + dy), self.now, bump, air)

        for card in revealed:
            drawn = card.draw(self.screen, self.assets, offset, self.now)
            if card.kind == LAUGH:
                laugh_rect = drawn
        if laugh_rect is not None and self.state != VICTORY:
            self._draw_ha_ha(laugh_rect)

    def _draw_ha_ha(self, rect):
        """Animated HA HA text bouncing around Laughing Nailong."""
        bounds = self.board_rect.inflate(int(36 * self.scale), 0)
        for i in range(7):
            angle = self.now * 1.5 + i * (math.tau / 7)
            x = rect.centerx + math.cos(angle) * rect.w * 0.88
            y = rect.centery + math.sin(angle * 1.3) * rect.h * 0.72
            x = min(max(x, bounds.left), bounds.right)
            y = min(max(y, bounds.top), bounds.bottom)
            size = int((26 + 8 * math.sin(self.now * 5 + i)) * self.scale)
            colour = T.PURPLE if i % 2 else T.YELLOW_DARK
            img = T.font(size, bold=True).render("HA", True, colour)
            halo = T.font(size, bold=True).render("HA", True, T.WHITE)
            img = pygame.transform.rotate(img, math.sin(angle) * 28)
            halo = pygame.transform.rotate(halo, math.sin(angle) * 28)
            centre = (int(x), int(y))
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                self.screen.blit(halo, halo.get_rect(
                    center=(centre[0] + dx, centre[1] + dy)))
            self.screen.blit(img, img.get_rect(center=centre))

    # ---- footer ------------------------------------------------------------
    def _draw_footer(self):
        s = self.scale
        if self.toasts:
            text, colour, remaining = self.toasts[0]
            rect = self.toast_rect
            T.rounded(self.screen, rect.move(0, 4),
                      tuple(max(0, c - 45) for c in colour), radius=18)
            T.rounded(self.screen, rect, colour, radius=18)
            T.rounded(self.screen, rect, T.WHITE, radius=18, width=3)
            wobble = int(2 * math.sin(self.now * 9))
            T.text_fitted(self.screen, text, int(25 * s), T.WHITE, rect,
                          bold=True, dy=wobble)
        T.text(self.screen,
               "Left click: flip   -   M: mute   -   R: restart   -   "
               "ESC: title screen", int(18 * s), T.INK_SOFT,
               center=(self.w // 2, self.footer_y))

    # ---- overlays ----------------------------------------------------------
    def _dim(self, alpha=170):
        veil = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        veil.fill((40, 30, 25, alpha))
        self.screen.blit(veil, (0, 0))

    def _draw_victory(self):
        s = self.scale
        self._dim(165)
        panel = self.victory_rect
        T.rounded(self.screen, panel, T.PANEL, radius=28)
        T.rounded(self.screen, panel, T.GREEN_DARK, radius=28, width=5)

        cx = panel.centerx
        bounce = int(6 * math.sin(self.now * 4))
        line = pygame.Rect(panel.left, 0, panel.width, 10)
        line.centery = panel.top + int(52 * s) + bounce
        T.text_fitted(self.screen, "YOU BEAT THE MAYHEM!", int(44 * s),
                      T.GREEN_DARK, line, bold=True)
        T.text(self.screen, "Time %s   -   %d flips"
               % (format_time(self.elapsed), self.flips), int(30 * s), T.INK,
               center=(cx, panel.top + int(100 * s)), bold=True)

        y = panel.top + int(134 * s)
        if self.improved:
            if len(self.improved) == 2:
                banner = "NEW BEST TIME  +  NEW FEWEST FLIPS!"
            elif self.improved[0] == "time":
                banner = "NEW BEST TIME!"
            else:
                banner = "NEW FEWEST FLIPS!"
            T.text_fitted(self.screen, banner, int(28 * s), T.PINK_DARK,
                          pygame.Rect(panel.left, y - 5, panel.width, 10),
                          bold=True)
            y += int(34 * s)

        # the two leaderboards, each with the run that set it
        for label, board, colour in (("Best time", "time", T.BLUE_DARK),
                                     ("Fewest flips", "flips", T.PINK_DARK)):
            entry = self.record.get(board)
            if entry:
                line = "%s  %s  in %s" % (
                    label,
                    format_time(entry["time"]) if board == "time"
                    else "%d flips" % entry["flips"],
                    "%d flips" % entry["flips"] if board == "time"
                    else format_time(entry["time"]))
            else:
                line = "%s  -" % label
            T.text(self.screen, line, int(21 * s), colour,
                   center=(cx, y), bold=False)
            y += int(26 * s)

        T.text(self.screen, "7 / 7 pairs  +  both Nailongs found",
               int(20 * s), T.INK_SOFT, center=(cx, y + int(2 * s)))

        for name in ("again", "to_title", "quit_win"):
            self.buttons[name].draw(self.screen, self.mouse, self.scale)

    def _draw_confirm(self):
        s = self.scale
        self._dim(150)
        rect = self.confirm_rect
        T.rounded(self.screen, rect, T.PANEL, radius=26)
        T.rounded(self.screen, rect, T.YELLOW_DARK, radius=26, width=5)
        T.text(self.screen, "Restart this game?", int(34 * s), T.INK,
               center=(rect.centerx, rect.top + int(52 * s)), bold=True)
        T.text(self.screen, "Your time and flips will be reset.", int(21 * s),
               T.INK_SOFT, center=(rect.centerx, rect.top + int(88 * s)))
        for name in ("yes", "no"):
            self.buttons[name].draw(self.screen, self.mouse, self.scale)

    # ---------------------------------------------------------------- loop ---
    def run(self):
        self._sync_sound_labels()
        while self.running:
            dt = min(0.05, self.clock.tick(FPS) / 1000.0)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
        self.shutdown()

    def shutdown(self):
        self.assets.shutdown()
        pygame.quit()


def main():
    try:
        Game().run()
    except KeyboardInterrupt:
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
