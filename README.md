# Nailong Memory Mayhem

A cute-but-cruel desktop memory game in Python + Pygame.

A 4x4 board holds **seven matching pairs** and **two lone Nailongs** that have
no partner:

- **Angry Nailong** screams, flashes the screen red and shakes the board, then
  **every card that is still face down lifts off, swirls around the middle of
  the board and lands in a new slot**. The animation shows the real
  permutation: the card you see flying from slot A to slot B is exactly the
  card whose picture moved from A to B. Already matched pairs - and any Nailong
  already revealed - do not move at all.
- **Laughing Nailong** starts cackling and **keeps laughing for the rest of the
  game**, with little "HA" letters bouncing around it.

You win when all seven pairs are matched **and** both Nailongs have been found.

---

## Four ways to play

| | What to open | Works on |
|---|---|---|
| **Online** | **https://huangmy233.github.io/Nailong/** | anything with a browser |
| **Browser, offline** | `index.html` (double-click, or upload it anywhere) | Mac, Windows, Linux, iPad, phone |
| **Windows app** | `dist/Nailong.exe` (double-click) | Windows, nothing installed |
| **From source** | `python main.py` | anywhere Python + Pygame run |

All four are the same game with the same rules and the same look.

### Browser version

`index.html` is one self-contained 2.9 MB page: every picture and sound is
embedded in the file, so it needs no server, no install and no internet
connection. Double-click it, drop it on any static host, or e-mail it. Your
best records are kept in that browser's local storage.

This is the version to use on a Mac - no Python, no build step, nothing to
approve. Chrome, Safari, Firefox and Edge all work; the first click also
switches the sound on, because browsers only allow audio after a real
interaction.

The only thing the browser cannot do is close its own tab, so **Quit** returns
to the title screen and explains that.

### Windows app

Double-click **`dist/Nailong.exe`**. It is one self-contained 19 MB file with
Python, Pygame and every asset inside it, so it also runs on a Windows machine
that has no Python at all - copy it to a USB stick and it works. The first
launch takes a second or two while it unpacks itself; later launches are
quicker. `records.json` is written next to the .exe.

## Run from source

You need **Python 3.8 or newer**.

```bash
pip install -r requirements.txt
```

```bash
python main.py
```

On Windows, if `python` is not on your PATH, use the launcher instead:

```bash
py -m pip install -r requirements.txt
```

```bash
py main.py
```

That is all. No internet connection, no server, no database - just Pygame.

---

## Controls

| Input | Action |
|---|---|
| Left mouse button | Flip a card / press a button |
| `M` | Mute or unmute all sound |
| `R` | Restart (asks first if a game is in progress) |
| `ESC` | Back to the title screen (quits from the title screen) |
| Window close button | Exit cleanly |

The **Sound / Restart / Title** buttons in the top bar do the same things with
the mouse, so a demo can be run without touching the keyboard.

## Rules in detail

- All 16 cards start face down and are reshuffled at the start of every game.
- Two flipped cards that match stay face up and turn green.
- Two cards that do not match are shown briefly, then turn back over. Clicks
  are ignored while that is happening.
- Every valid flip adds 1 to the flip counter.
- The clock starts on your first click and **pauses during the Angry Nailong
  shuffle**, so the animation never costs you time.
- Both Nailong cards trigger their effect once, then stay face up forever.
- If you match all seven pairs while a Nailong is still hidden, the game keeps
  going and tells you: *All pairs matched—but a Nailong is still hiding!*

## Two leaderboards

A sprint and a flawless memory are different achievements, so the game keeps
**two separate records**:

| Board | Won by | Tie broken by |
|---|---|---|
| **Best time** | the faster completion | fewer flips |
| **Fewest flips** | the smaller flip count | the faster time |

One run can take one board, both, or neither - and the victory screen says
which. Each board also stores the other statistic of its own run, so a record
always describes a real game ("Fewest flips 18 flips in 01:12.55").

The timer runs to a **hundredth of a second** (`mm:ss.cc`), so ties are rare
and a 0.01 s margin actually counts.

Records are stored next to the game (next to the .exe for the packaged build)
in **`records.json`**; the browser version keeps them in that browser's local
storage instead.

```json
{
  "best_time":  { "time": 24.31, "flips": 22 },
  "best_flips": { "time": 31.20, "flips": 18 }
}
```

If the file is missing, empty or damaged, the game simply starts with no
records - it never crashes because of it. A file written by an older version
(one flat `best_time` number) is migrated automatically. Delete the file to
reset your records.

## Project layout

```text
nailong_memory/
    main.py             entry point - "python main.py", and the exe starts here
    game.py             game states, board logic, drawing
    card.py             one card: identity, flip and match animation
    asset_manager.py    image preparation/caching + all audio control
    records.py          records.json load / save / comparison
    paths.py            where to read assets / write records (source vs. exe)
    theme.py            colours, fonts and small drawing helpers
    index.html          BUILT: the whole browser game in one file, and the
                        page GitHub Pages serves
    prepare_assets.py   optional image-resizing utility (not required)
    build_exe.py        builds dist/Nailong.exe
    build_web.py        builds index.html (the browser build)
    nailong.ico         app icon, generated by build_exe.py
    requirements.txt        pygame - to play
    requirements-build.txt  pyinstaller - only to build the exe
    README.md
    assets/
        cards/          pair_1..pair_7, angry_nailong, laughing_nailong, card_back
        sounds/         angry, laugh, flip, match, victory (.wav)
    dist/               the built .exe
    web/
        game.js             the browser version of the game
        index.template.html the page around it
        artifact.html       BUILT: the same page without the html/head/body
                            skeleton, for hosts that supply their own
```

## Publishing it (GitHub Pages)

The repository already contains the built `index.html` at its root, so the
whole site is just that one file. To turn it into a public link:

1. **Settings** -> **Pages**
2. **Source: Deploy from a branch**, **Branch: `main`**, folder **`/ (root)`**
3. Save, wait a minute, and the game is live at
   **https://huangmy233.github.io/Nailong/**

After changing the game, re-run `py build_web.py` and commit `index.html` -
Pages redeploys by itself.

The browser version is a port, not a wrapper: `web/game.js` draws the same game
on an HTML canvas. Every rule and every timing constant is copied from the
Python source, so both versions behave identically. Three things differ because
the platform forces them: the best records live in the browser's local storage
instead of `records.json`, sound goes through WebAudio, and the layout also
scales with the window width (a browser window can be any shape).

**Changing the game means changing both** - `game.py`/`card.py` for the desktop
version and `web/game.js` for the browser one. That is the price of a web build
that needs no Python at runtime.

## Rebuilding the browser version

```bash
py build_web.py
```

Reads `assets/`, `web/game.js` and `web/index.template.html`, and writes
`index.html` (and `web/artifact.html`). Pictures are cropped/fitted and
scaled to 512 px, sounds are downmixed to mono 22050 Hz, and each file is
embedded only if that copy is actually smaller than the original - which takes
the 5.6 MB of assets down to 2.2 MB. The originals in `assets/` are untouched.
`py build_web.py --image-size 768` if you want sharper pictures and a bigger
file.

## Rebuilding the .exe

Only needed if you changed the code or the pictures.

```bash
py -m pip install -r requirements-build.txt
```

```bash
py build_exe.py
```

That regenerates the icon from `assets/cards/angry_nailong.png`, bundles the
whole `assets/` folder and writes `dist/Nailong.exe`. Options:

- `py build_exe.py --folder` - a folder instead of one file; starts instantly
- `py build_exe.py --console` - keeps a console window, so asset warnings and
  errors are visible while debugging
- `py build_exe.py --icon-only` - just regenerate `nailong.ico`

Because a windowed build has no console, an unexpected crash writes
`nailong_error.log` next to the .exe instead of vanishing silently. If the
folder holding the .exe is read-only (e.g. Program Files), `records.json` and
that log go to `%LOCALAPPDATA%\NailongMemoryMayhem\` instead.

Note that the .exe is a Windows build. To get a Mac or Linux binary, run
`python build_exe.py` on that machine - PyInstaller only builds for the system
it runs on.

## Replacing the pictures and sounds

Just drop new files into `assets/` using the same names. **No code changes are
needed.** The .exe and the web page each carry their own copy of `assets/`, so
re-run `py build_exe.py` and `py build_web.py` afterwards to put the new
pictures into them.

- Any size and aspect ratio works, `.png` or `.jpg`.
- Nothing is ever stretched: the seven pair pictures are centre-cropped to a
  square and smooth-scaled to the card; the two Nailong pictures are scaled
  proportionally so the whole character stays visible.
- Scaling happens once when the images load, and the results are cached - the
  animation never rescales an image.
- A missing or unreadable image becomes a clearly labelled placeholder card and
  prints a warning naming the file; the game keeps running.
- A missing sound file is simply disabled. Sounds must be `.wav`.
- Your original files are never modified.

Optional: `python prepare_assets.py` writes uniformly sized copies into
`assets/cards/prepared/`, which the game prefers if that folder exists. This is
only a convenience for checking crops - the game does not need it.
`python prepare_assets.py --clean` removes the folder again.

## 60-second demo script

1. Open the game (browser page or .exe) and click **Start Game**.
2. Flip two cards, find one pair (green flash, matched sound).
3. Keep flipping until **Angry Nailong** appears: red flash, board shake, and
   the whole face-down half of the board takes off, swirls and re-lands in new
   places - while the matched pair sits there untouched.
4. Find **Laughing Nailong**: the laughter starts and does not stop. Press `M`
   to prove you can mute it, `M` again to bring it back.
5. Finish the pairs and show the victory screen: the time to a hundredth of a
   second, the flip count, and which of the two leaderboards you just took.
