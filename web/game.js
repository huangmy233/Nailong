/* Nailong Memory Mayhem - browser port of the Pygame original.
 *
 * Same rules, same numbers, same look: every constant below is the value used
 * by game.py / card.py / theme.py, so the web build behaves like the desktop
 * one.  Differences are only where the platform forces them:
 *   - the best record lives in localStorage instead of records.json
 *   - audio goes through WebAudio (so muting is a gain change, and the
 *     laughter can loop seamlessly)
 *   - the layout also scales down with the window width, which a resizable
 *     browser window needs and a fixed desktop window did not.
 */
(function () {
  "use strict";

  var ASSETS = window.NAILONG_ASSETS || { images: {}, sounds: {} };

  // ------------------------------------------------------------- theme ------
  var C = {
    BG_TOP: "#fffae4", BG_BOTTOM: "#ffe9d2",
    INK: "#4a3b34", INK_SOFT: "#8b786e",
    PANEL: "#ffffff", PANEL_EDGE: "#eedccd",
    PINK: "#ffa0be", PINK_DARK: "#e66894",
    BLUE: "#98cef6", BLUE_DARK: "#569cda",
    GREEN: "#84d89c", GREEN_DARK: "#42a866",
    RED: "#f05454", RED_DARK: "#c42e2e",
    YELLOW: "#ffd458", YELLOW_DARK: "#e2a81e",
    PURPLE: "#b284e2",
    CARD_FACE: "#fffdf6", WHITE: "#ffffff"
  };
  var FONT = '"Comic Sans MS","Chalkboard SE","Comic Neue","Trebuchet MS",Verdana,Arial,sans-serif';

  function rgb(hex) {
    return [parseInt(hex.substr(1, 2), 16), parseInt(hex.substr(3, 2), 16),
            parseInt(hex.substr(5, 2), 16)];
  }
  function shade(hex, amount) {
    var p = rgb(hex);
    return "rgb(" + Math.max(0, p[0] - amount) + "," + Math.max(0, p[1] - amount)
           + "," + Math.max(0, p[2] - amount) + ")";
  }
  function rgba(hex, alpha) {
    var p = rgb(hex);
    return "rgba(" + p[0] + "," + p[1] + "," + p[2] + "," + alpha + ")";
  }

  // ------------------------------------------------------------- tuning -----
  var GRID = 4, PAIR_COUNT = 7, CARD_ASPECT = 0.92, GAP_RATIO = 0.10;
  var COMPARE_TIME = 0.80;
  var SHUFFLE_LEAD = 0.35, TRAVEL_TIME = 0.95, TRAVEL_STAGGER = 0.28;
  var TRAVEL_PULL = 0.28, TRAVEL_SPIN = 0.55;
  var SHUFFLE_TOTAL = SHUFFLE_LEAD + TRAVEL_TIME + 0.30;
  var SHAKE_TIME = 0.75, FLASH_TIME = 0.50, TOAST_TIME = 2.60;
  var FLIP_SPEED = 5.0, MATCH_PULSE = 0.55;

  var TITLE = "title", PLAYING = "playing", COMPARE = "compare",
      SHUFFLE = "shuffle", VICTORY = "victory";

  var MSG_ANGRY = "ANGRY NAILONG SHUFFLED THE BOARD!";
  var MSG_LAUGH = "LAUGHING NAILONG WILL LAUGH FOR THE REST OF THE GAME!";
  var MSG_HIDING = "All pairs matched—but a Nailong is still hiding!";
  var CREDIT = "Produced by Mingyi";

  var PAIR_KEYS = ["pair_1", "pair_2", "pair_3", "pair_4", "pair_5", "pair_6",
                   "pair_7"];
  var ANGRY_KEY = "angry_nailong", LAUGH_KEY = "laughing_nailong",
      BACK_KEY = "card_back";
  var NORMAL = "normal", ANGRY = "angry", LAUGH = "laugh";

  var VOLUME = { angry: 0.75, laugh: 0.45, flip: 0.35, match: 0.55,
                 victory: 0.65 };
  var RECORD_KEY = "nailong_memory_mayhem_record";

  var reduceMotion = false;
  try {
    reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch (e) { /* older browser: keep the animations */ }

  // ------------------------------------------------------------ canvas ------
  var canvas = document.getElementById("game");
  var ctx = canvas.getContext("2d");
  var W = 0, H = 0, dpr = 1;

  function formatTime(seconds) {
    var m = Math.floor(seconds / 60);
    var s = seconds - 60 * m;
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s.toFixed(1);
  }

  function setFont(px, bold) {
    ctx.font = (bold ? "bold " : "") + Math.max(6, Math.round(px)) + "px " + FONT;
  }

  /* Draw one line of text.  `at` mirrors the keyword used in theme.py:
     center / midleft / midright / midtop. */
  function text(str, px, colour, at, x, y, bold, shadowed) {
    setFont(px, bold);
    ctx.textAlign = at === "midleft" ? "left" : at === "midright" ? "right"
                                                                 : "center";
    ctx.textBaseline = at === "midtop" ? "top" : "middle";
    if (shadowed) {
      ctx.fillStyle = "rgba(0,0,0,0.18)";
      ctx.fillText(str, x + 2, y + 2);
    }
    ctx.fillStyle = colour;
    ctx.fillText(str, x, y);
  }

  /* Shrink the type until the line fits the box, then centre it. */
  function textFitted(str, maxPx, colour, box, bold, dy, padding) {
    var px = Math.round(maxPx);
    padding = padding === undefined ? 24 : padding;
    while (px > 11) {
      setFont(px, bold);
      if (ctx.measureText(str).width <= box.w - padding) { break; }
      px -= 1;
    }
    text(str, px, colour, "center", box.x + box.w / 2,
         box.y + box.h / 2 + (dy || 0), bold);
  }

  function rrPath(c, x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    c.beginPath();
    c.moveTo(x + r, y);
    c.arcTo(x + w, y, x + w, y + h, r);
    c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r);
    c.arcTo(x, y, x + w, y, r);
    c.closePath();
  }
  function fillRR(c, x, y, w, h, r, colour) {
    rrPath(c, x, y, w, h, r);
    c.fillStyle = colour;
    c.fill();
  }
  /* pygame draws a rect border *inside* the rect, so inset by half the width. */
  function strokeRR(c, x, y, w, h, r, colour, width) {
    var i = width / 2;
    rrPath(c, x + i, y + i, w - width, h - width, Math.max(0, r - i));
    c.strokeStyle = colour;
    c.lineWidth = width;
    c.stroke();
  }

  // ------------------------------------------------------------ assets ------
  var images = {};        // key -> HTMLImageElement (or undefined if broken)
  var surfaces = {};      // cache of pre-rendered card canvases

  function offscreen(w, h) {
    var c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(w));
    c.height = Math.max(1, Math.round(h));
    return c;
  }

  function placeholder(w, h, label) {
    var c = offscreen(w, h), g = c.getContext("2d");
    fillRR(g, 0, 0, w, h, 12, "#ece0d6");
    strokeRR(g, 0, 0, w, h, 12, C.RED, 3);
    var save = ctx;
    ctx = g;
    text("?", h * 0.45, C.RED, "center", w / 2, h * 0.42, false);
    text(label.substr(0, 12), Math.max(11, h * 0.11), C.INK_SOFT, "center",
         w / 2, h * 0.78, false);
    ctx = save;
    return c;
  }

  /* Centre-crop to a square and scale - never stretched. */
  function drawSquare(g, key, x, y, side) {
    var img = images[key];
    if (!img) { g.drawImage(placeholder(side, side, key), x, y); return; }
    var s = Math.min(img.width, img.height);
    g.drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s,
                x, y, side, side);
  }

  /* Scale proportionally so the whole picture fits, then centre it. */
  function drawContained(g, key, cx, cy, boxW, boxH) {
    var img = images[key];
    if (!img) {
      g.drawImage(placeholder(boxW, boxH, key), cx - boxW / 2, cy - boxH / 2);
      return;
    }
    var k = Math.min(boxW / img.width, boxH / img.height);
    var w = img.width * k, h = img.height * k;
    g.drawImage(img, cx - w / 2, cy - h / 2, w, h);
  }

  function cardBack(w, h) {
    var key = "back|" + w + "x" + h;
    if (surfaces[key]) { return surfaces[key]; }
    var c = offscreen(w, h), g = c.getContext("2d");
    fillRR(g, 0, 0, w, h, 18, C.PINK);
    var ix = w * 0.05, iy = h * 0.0425;                 // inflate(-w*.10,-h*.085)
    var iw = w - 2 * ix, ih = h - 2 * iy;
    fillRR(g, ix, iy, iw, ih, 14, C.BLUE);
    var side = Math.min(iw, ih) - 6;
    if (side > 8) {
      g.save();
      rrPath(g, ix + (iw - side) / 2, iy + (ih - side) / 2, side, side, 12);
      g.clip();
      drawSquare(g, BACK_KEY, ix + (iw - side) / 2, iy + (ih - side) / 2, side);
      g.restore();
    }
    strokeRR(g, 0, 0, w, h, 18, C.WHITE, 4);
    strokeRR(g, 0, 0, w, h, 18, C.PINK_DARK, 2);
    surfaces[key] = c;
    return c;
  }

  function cardFace(kind, artKey, w, h) {
    var key = "face|" + artKey + "|" + w + "x" + h;
    if (surfaces[key]) { return surfaces[key]; }
    var c = offscreen(w, h), g = c.getContext("2d");
    var fill = C.CARD_FACE, edge = C.PINK;
    if (kind === ANGRY) { fill = "#ffe8e8"; edge = C.RED; }
    else if (kind === LAUGH) { fill = "#fff6d6"; edge = C.PURPLE; }
    fillRR(g, 0, 0, w, h, 18, fill);

    var margin = Math.max(7, w * 0.085);
    var iw = w - 2 * margin, ih = h - 2 * margin;
    if (kind === NORMAL) {
      var side = Math.min(iw, ih);
      drawSquare(g, artKey, (w - side) / 2, (h - side) / 2, side);
    } else {
      drawContained(g, artKey, w / 2, h / 2, iw, ih);
    }
    strokeRR(g, 0, 0, w, h, 18, C.WHITE, 4);
    strokeRR(g, 0, 0, w, h, 18, edge, 2);
    surfaces[key] = c;
    return c;
  }

  function shadowSurface(w, h) {
    var key = "shadow|" + w + "x" + h;
    if (surfaces[key]) { return surfaces[key]; }
    var c = offscreen(w, h), g = c.getContext("2d");
    var inset = Math.max(3, w * 0.05);
    fillRR(g, inset, inset, w - 2 * inset, h - 2 * inset, 16,
           "rgba(120,96,84,0.18)");
    surfaces[key] = c;
    return c;
  }

  // -------------------------------------------------------------- audio -----
  var audio = {
    ctx: null, master: null, buffers: {}, laughSource: null,
    ok: false, muted: false, pending: []
  };

  function audioInit() {
    if (audio.ctx) { return; }
    var Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) { return; }
    try {
      audio.ctx = new Ctor();
      audio.master = audio.ctx.createGain();
      audio.master.gain.value = 1;
      audio.master.connect(audio.ctx.destination);
      audio.ok = true;
    } catch (e) { audio.ok = false; }
  }

  function b64ToBytes(b64) {
    var raw = atob(b64), out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) { out[i] = raw.charCodeAt(i); }
    return out;
  }

  function audioDecodeAll() {
    if (!audio.ok) { return Promise.resolve(); }
    var jobs = Object.keys(ASSETS.sounds).map(function (name) {
      return new Promise(function (done) {
        var bytes;
        try { bytes = b64ToBytes(ASSETS.sounds[name]); }
        catch (e) { done(); return; }
        var finish = function (buffer) {
          if (buffer) { audio.buffers[name] = buffer; }
          done();
        };
        try {
          var p = audio.ctx.decodeAudioData(bytes.buffer, finish,
                                            function () { done(); });
          if (p && p.then) { p.then(finish, function () { done(); }); }
        } catch (e) { done(); }
      });
    });
    return Promise.all(jobs);
  }

  function audioResume() {
    if (audio.ctx && audio.ctx.state === "suspended") {
      audio.ctx.resume().catch(function () {});
    }
  }

  function playSound(name) {
    if (!audio.ok || audio.muted || !audio.buffers[name]) { return; }
    audioResume();
    try {
      var src = audio.ctx.createBufferSource();
      var gain = audio.ctx.createGain();
      gain.gain.value = VOLUME[name] || 0.5;
      src.buffer = audio.buffers[name];
      src.connect(gain);
      gain.connect(audio.master);
      src.start(0);
    } catch (e) { /* a dropped sound must never break the game */ }
  }

  function startLaugh() {
    if (!audio.ok || !audio.buffers.laugh) { return; }
    stopLaugh();
    audioResume();
    try {
      var src = audio.ctx.createBufferSource();
      var gain = audio.ctx.createGain();
      gain.gain.value = VOLUME.laugh;
      src.buffer = audio.buffers.laugh;
      src.loop = true;
      src.connect(gain);
      gain.connect(audio.master);
      src.start(0);
      audio.laughSource = src;
    } catch (e) { audio.laughSource = null; }
  }

  function stopLaugh() {
    if (audio.laughSource) {
      try { audio.laughSource.stop(0); } catch (e) { /* already ended */ }
      audio.laughSource = null;
    }
  }

  function setMuted(muted) {
    audio.muted = !!muted;
    if (audio.master) {
      audio.master.gain.value = audio.muted ? 0 : 1;   // the loop keeps running
    }
  }

  // ------------------------------------------------------------ records -----
  function loadRecord() {
    var raw;
    try { raw = window.localStorage.getItem(RECORD_KEY); }
    catch (e) { return null; }
    if (!raw) { return null; }
    var data;
    try { data = JSON.parse(raw); } catch (e) { return null; }
    if (!data || typeof data !== "object") { return null; }
    var t = Number(data.best_time), f = Math.round(Number(data.best_flips));
    if (!isFinite(t) || !isFinite(f) || t <= 0 || f <= 0) { return null; }
    return { best_time: t, best_flips: f };
  }

  function saveRecord(record) {
    try {
      window.localStorage.setItem(RECORD_KEY, JSON.stringify({
        best_time: Math.round(record.best_time * 100) / 100,
        best_flips: record.best_flips
      }));
    } catch (e) { /* private mode: play on without saving */ }
  }

  function isBetter(t, flips, old) {
    if (!old) { return true; }
    if (t < old.best_time - 0.05) { return true; }
    if (Math.abs(t - old.best_time) <= 0.05) { return flips < old.best_flips; }
    return false;
  }

  // --------------------------------------------------------------- card -----
  function Card(index) {
    this.index = index;
    this.kind = NORMAL;
    this.key = "pair_1";
    this.rect = { x: 0, y: 0, w: 10, h: 10 };
    this.turn = 0;
    this.target = 0;
    this.matched = false;
    this.locked = false;
    this.matchPulse = 0;
    this.hover = false;
  }
  Card.prototype.centre = function () {
    return { x: this.rect.x + this.rect.w / 2, y: this.rect.y + this.rect.h / 2 };
  };
  Card.prototype.isFaceUp = function () { return this.target >= 1; };
  Card.prototype.isAnimating = function () {
    return Math.abs(this.turn - this.target) > 1e-6;
  };
  Card.prototype.clickable = function () {
    return !(this.matched || this.locked || this.isFaceUp() || this.isAnimating());
  };
  Card.prototype.flipUp = function () { this.target = 1; };
  Card.prototype.flipDown = function () { this.target = 0; };
  Card.prototype.snapDown = function () { this.turn = 0; this.target = 0; };
  Card.prototype.setMatched = function () {
    this.matched = true;
    this.turn = 1;
    this.target = 1;
    this.matchPulse = MATCH_PULSE;
  };
  Card.prototype.update = function (dt) {
    if (this.turn < this.target) {
      this.turn = Math.min(this.target, this.turn + FLIP_SPEED * dt);
    } else if (this.turn > this.target) {
      this.turn = Math.max(this.target, this.turn - FLIP_SPEED * dt);
    }
    if (this.matchPulse > 0) { this.matchPulse = Math.max(0, this.matchPulse - dt); }
  };

  Card.prototype.draw = function (offset, now, scale, air) {
    scale = scale || 1;
    air = air || 0;
    var r = { x: this.rect.x + offset.x, y: this.rect.y + offset.y,
              w: this.rect.w, h: this.rect.h };
    var showingFace = this.turn >= 0.5;
    var squash = this.isAnimating()
      ? Math.max(0.06, Math.abs(Math.cos(this.turn * Math.PI))) : 1;

    var art = showingFace ? cardFace(this.kind, this.key, r.w, r.h)
                          : cardBack(r.w, r.h);
    var lift = 0;
    if (this.matchPulse > 0) {
      lift = 6 * Math.sin(Math.PI * (1 - this.matchPulse / MATCH_PULSE));
    } else if (this.hover && this.clickable()) {
      lift = 3;
    }

    var dw = Math.max(2, r.w * squash * scale);
    var dh = Math.max(2, r.h * scale);
    var dx = r.x + r.w / 2 - dw / 2;
    var dy = r.y + r.h / 2 - lift - dh / 2;

    ctx.drawImage(shadowSurface(r.w, r.h), r.x, r.y + 8 + lift + 14 * air);
    ctx.drawImage(art, dx, dy, dw, dh);

    if (this.matched) {
      strokeRR(ctx, dx, dy, dw, dh, 18, C.GREEN_DARK, 5);
      if (this.matchPulse > 0) {
        fillRR(ctx, dx, dy, dw, dh, 18,
               rgba(C.GREEN, 0.59 * (this.matchPulse / MATCH_PULSE)));
      }
      if (dw > 46) {
        var rad = Math.max(10, r.w * 0.11);
        checkMark(dx + dw - rad - 3, dy + rad + 3, rad);
      }
    } else if (this.locked && this.kind === ANGRY) {
      strokeRR(ctx, dx, dy, dw, dh, 18, C.RED, 3 + 2 * Math.sin(now * 6));
    } else if (this.locked && this.kind === LAUGH) {
      strokeRR(ctx, dx, dy, dw, dh, 18,
               Math.floor(now * 6) % 2 === 0 ? C.YELLOW : C.PURPLE, 5);
    }
    return { x: dx, y: dy, w: dw, h: dh };
  };

  function checkMark(cx, cy, radius) {
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fillStyle = C.GREEN_DARK;
    ctx.fill();
    ctx.strokeStyle = C.WHITE;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx - radius * 0.45, cy);
    ctx.lineTo(cx - radius * 0.10, cy + radius * 0.38);
    ctx.lineTo(cx + radius * 0.50, cy - radius * 0.40);
    ctx.lineWidth = Math.max(2, radius * 0.28);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.stroke();
    ctx.lineCap = "butt";
  }

  // ------------------------------------------------------------- button -----
  function Button(label, colour, small) {
    this.label = label;
    this.colour = colour;
    this.small = !!small;
    this.rect = { x: 0, y: 0, w: 0, h: 0 };
  }
  Button.prototype.draw = function (mouse, scale) {
    var r = this.rect;
    var hot = hit(r, mouse);
    var b = hot ? { x: r.x - 2, y: r.y - 2, w: r.w + 4, h: r.h + 4 } : r;
    fillRR(ctx, b.x, b.y + 4, b.w, b.h, 16, shade(this.colour, 40));
    fillRR(ctx, b.x, b.y, b.w, b.h, 16, this.colour);
    strokeRR(ctx, b.x, b.y, b.w, b.h, 16, C.WHITE, 3);
    text(this.label, (this.small ? 20 : 27) * scale, C.WHITE, "center",
         b.x + b.w / 2, b.y + b.h / 2, true);
  };

  function hit(r, p) {
    return p && p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h;
  }

  // --------------------------------------------------------------- game -----
  var G = {
    state: TITLE, now: 0, scale: 1, mouse: null,
    cards: [], buttons: {}, tl: {},
    first: null, second: null,
    compareTimer: 0, shuffleTimer: 0, shuffledYet: false,
    travel: {}, travelT: 1,
    shakeTimer: 0, flashTimer: 0,
    elapsed: 0, flips: 0, pairsFound: 0, timerRunning: false,
    angryDone: false, laughDone: false,
    toasts: [], confirmRestart: false, newRecord: false,
    record: null, running: true
  };

  function buildButtons() {
    G.buttons = {
      start: new Button("Start Game", C.GREEN_DARK),
      quit_title: new Button("Quit", C.PINK_DARK),
      sound_title: new Button("Sound: ON", C.BLUE_DARK),
      mute: new Button("Sound: ON", C.BLUE_DARK, true),
      restart: new Button("Restart", C.YELLOW_DARK, true),
      title: new Button("Title", C.PINK_DARK, true),
      again: new Button("Play Again", C.GREEN_DARK),
      to_title: new Button("Title Screen", C.BLUE_DARK),
      quit_win: new Button("Quit", C.PINK_DARK),
      yes: new Button("Yes, restart", C.GREEN_DARK),
      no: new Button("Keep playing", C.BLUE_DARK)
    };
    for (var i = 0; i < GRID * GRID; i++) { G.cards.push(new Card(i)); }
  }

  function syncSoundLabels() {
    var label = audio.muted ? "Sound: OFF" : "Sound: ON";
    G.buttons.mute.label = label;
    G.buttons.sound_title.label = label;
  }

  function layout() {
    var w = W, h = H;
    // the desktop build only scaled with height; a browser window can also be
    // narrow, so the width gets a say too
    var s = Math.max(0.62, Math.min(1.15, Math.min(h / 900, w / 1020)));
    G.scale = s;

    G.hud = { x: 22 * s, y: 14 * s, w: w - 44 * s, h: 60 * s };
    G.stats = { x: G.hud.x, y: G.hud.y + G.hud.h + 10 * s, w: G.hud.w, h: 46 * s };
    var footerTop = h - 96 * s;
    var boardTop = G.stats.y + G.stats.h + 14 * s;

    var availH = footerTop - boardTop - 8 * s;
    var availW = w - 64 * s;
    var gap = Math.max(8, Math.floor(Math.min(availW, availH) * GAP_RATIO / GRID));
    var cellH = (availH - (GRID - 1) * gap) / GRID;
    var cellW = Math.min(cellH * CARD_ASPECT, (availW - (GRID - 1) * gap) / GRID);
    cellH = Math.min(cellH, cellW / CARD_ASPECT);
    cellW = Math.floor(cellW);
    cellH = Math.floor(cellH);

    var boardW = GRID * cellW + (GRID - 1) * gap;
    var boardH = GRID * cellH + (GRID - 1) * gap;
    var boardX = Math.floor((w - boardW) / 2);
    var boardY = Math.floor(boardTop + Math.max(0, (availH - boardH) / 2));
    G.board = { x: boardX, y: boardY, w: boardW, h: boardH };

    G.cards.forEach(function (card, index) {
      var row = Math.floor(index / GRID), col = index % GRID;
      card.rect = { x: boardX + col * (cellW + gap),
                    y: boardY + row * (cellH + gap), w: cellW, h: cellH };
    });

    var toastW = Math.min(w - 40, 760 * s), toastH = 46 * s;
    G.toastRect = { x: (w - toastW) / 2, y: footerTop + 26 * s - toastH / 2,
                    w: toastW, h: toastH };
    G.footerY = h - 24 * s;

    // HUD buttons, right aligned
    var bw = 132 * s, bh = 36 * s;
    var x = G.hud.x + G.hud.w - 12 * s;
    ["title", "restart", "mute"].forEach(function (name) {
      G.buttons[name].rect = { x: x - bw, y: G.hud.y + G.hud.h / 2 - bh / 2,
                               w: bw, h: bh };
      x -= bw + 10 * s;
    });
    G.hudTitleRoom = x - G.hud.x - 24 * s;

    // ---- title screen: one measured vertical stack
    var cx = w / 2, y = 62 * s;
    G.tl = {};
    G.tl.title1 = y;
    y += 96 * s;                          // room for descenders + the bob
    G.tl.title2 = y;
    var art = Math.min(h * 0.185, w * 0.22);
    G.tl.art = art;
    y += 66 * s + art / 2;
    G.tl.artY = y;
    y += art / 2 + 64 * s;                // room for the ANGRY / LAUGHING labels
    G.tl.lineH = 28 * s;
    G.tl.textTop = y;
    y += 4 * G.tl.lineH + 34 * s;

    var sbw = 300 * s, sbh = 58 * s;
    G.buttons.start.rect = { x: cx - sbw / 2, y: y, w: sbw, h: sbh };
    y += sbh + 14 * s;
    var mw = 230 * s, mh = 46 * s;
    G.buttons.sound_title.rect = { x: cx - mw / 2, y: y, w: mw, h: mh };
    y += mh + 12 * s;
    G.buttons.quit_title.rect = { x: cx - mw / 2, y: y, w: mw, h: mh };
    G.tl.bottomY = Math.max(y + mh + 26 * s, h - 50 * s);

    // ---- victory panel
    var vh = 52 * s;
    var vw2 = Math.min(w - 50, 700 * s);
    G.victory = { x: cx - vw2 / 2, y: h / 2 - 165 * s, w: vw2, h: 330 * s };
    var vw = Math.min(200 * s, (G.victory.w - 4 * 14 * s) / 3);
    var gapx = 14 * s;
    var left = cx - (3 * vw + 2 * gapx) / 2;
    var rowY = G.victory.y + G.victory.h - 28 * s - vh;
    ["again", "to_title", "quit_win"].forEach(function (name, i) {
      G.buttons[name].rect = { x: left + i * (vw + gapx), y: rowY, w: vw, h: vh };
    });

    // ---- confirm dialog
    var cw2 = Math.min(w - 60, 540 * s), chh = 216 * s;
    G.confirm = { x: cx - cw2 / 2, y: h / 2 - chh / 2, w: cw2, h: chh };
    var cw = 200 * s, ch = 48 * s;
    var cRow = G.confirm.y + G.confirm.h - 26 * s - ch;
    G.buttons.yes.rect = { x: cx - cw - 9 * s, y: cRow, w: cw, h: ch };
    G.buttons.no.rect = { x: cx + 9 * s, y: cRow, w: cw, h: ch };

    surfaces = {};        // card art is rebuilt once, not every frame
    G.background = null;
  }

  // ------------------------------------------------------------ new deal ----
  function shuffled(list) {
    for (var i = list.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = list[i]; list[i] = list[j]; list[j] = tmp;
    }
    return list;
  }

  function resetGame() {
    stopLaugh();
    var deck = [];
    PAIR_KEYS.forEach(function (key) {
      deck.push({ kind: NORMAL, key: key });
      deck.push({ kind: NORMAL, key: key });
    });
    deck.push({ kind: ANGRY, key: ANGRY_KEY });
    deck.push({ kind: LAUGH, key: LAUGH_KEY });
    shuffled(deck);

    G.cards.forEach(function (card, i) {
      card.matched = false;
      card.locked = false;
      card.turn = 0;
      card.target = 0;
      card.matchPulse = 0;
      card.kind = deck[i].kind;
      card.key = deck[i].key;
    });

    G.first = null;
    G.second = null;
    G.compareTimer = 0;
    G.shuffleTimer = 0;
    G.shuffledYet = false;
    G.travel = {};
    G.travelT = 1;
    G.shakeTimer = 0;
    G.flashTimer = 0;
    G.elapsed = 0;
    G.flips = 0;
    G.pairsFound = 0;
    G.timerRunning = false;
    G.angryDone = false;
    G.laughDone = false;
    G.confirmRestart = false;
    G.newRecord = false;
    G.toasts = [];
    G.state = PLAYING;
  }

  function goToTitle() {
    stopLaugh();
    G.confirmRestart = false;
    G.state = TITLE;
  }

  function toast(str, colour) {
    for (var i = 0; i < G.toasts.length; i++) {
      if (G.toasts[i].text === str) { return; }
    }
    if (G.toasts.length) {
      G.toasts[0].left = Math.min(G.toasts[0].left, 0.5);
    }
    G.toasts.push({ text: str, colour: colour, left: TOAST_TIME });
  }

  // --------------------------------------------------------- card clicks ----
  function clickCard(card) {
    if (!card.clickable()) { return; }
    if (G.first !== null && card === G.cards[G.first]) { return; }

    G.timerRunning = true;
    G.flips += 1;
    card.flipUp();
    playSound("flip");

    if (card.kind === ANGRY) {
      triggerAngry(card);
    } else if (card.kind === LAUGH) {
      triggerLaugh(card);
    } else if (G.first === null) {
      G.first = card.index;
    } else {
      G.second = card.index;
      G.compareTimer = COMPARE_TIME;
      G.state = COMPARE;
    }
  }

  function clearAttempt() {
    if (G.first !== null) { G.cards[G.first].flipDown(); }
    G.first = null;
    G.second = null;
  }

  function triggerAngry(card) {
    playSound("angry");
    card.locked = true;
    G.angryDone = true;
    clearAttempt();
    G.state = SHUFFLE;
    G.shuffleTimer = 0;
    G.shuffledYet = false;
    G.flashTimer = FLASH_TIME;
    G.shakeTimer = SHAKE_TIME;
    toast(MSG_ANGRY, C.RED_DARK);
  }

  function triggerLaugh(card) {
    card.locked = true;
    G.laughDone = true;
    clearAttempt();
    startLaugh();
    toast(MSG_LAUGH, C.PURPLE);
    checkProgress();
  }

  /* Permute the identities of every face-down card and hand the permutation to
     the flying animation, so what the player sees is what happened. */
  function shuffleFaceDown() {
    var movable = G.cards.filter(function (c) { return !c.matched && !c.locked; });
    if (movable.length < 2) { return; }

    var order = movable.map(function (_, i) { return i; });
    shuffled(order);
    for (var i = 0; i < order.length; i++) {          // nothing stays put
      if (order[i] === i) {
        var j = i;
        while (j === i) { j = Math.floor(Math.random() * order.length); }
        var tmp = order[i]; order[i] = order[j]; order[j] = tmp;
      }
    }

    var identities = movable.map(function (c) {
      return { kind: c.kind, key: c.key };
    });
    G.travel = {};
    G.travelT = 0;
    order.forEach(function (source, slot) {
      var card = movable[slot];
      card.snapDown();
      card.kind = identities[source].kind;
      card.key = identities[source].key;
      G.travel[card.index] = { from: movable[source].centre(),
                               delay: Math.random() * TRAVEL_STAGGER };
    });
  }

  function travelState(card) {
    var entry = G.travel[card.index];
    if (!entry || G.travelT >= 1) { return null; }
    var span = Math.max(0.05, 1 - TRAVEL_STAGGER);
    var t = Math.min(1, Math.max(0, (G.travelT - entry.delay) / span));
    if (t >= 1) { return null; }

    var home = card.centre();
    var ease = t * t * (3 - 2 * t);
    var x = entry.from.x + (home.x - entry.from.x) * ease;
    var y = entry.from.y + (home.y - entry.from.y) * ease;

    var arc = Math.sin(Math.PI * t);
    var cx = G.board.x + G.board.w / 2, cy = G.board.y + G.board.h / 2;
    x += (cx - x) * TRAVEL_PULL * arc;
    y += (cy - y) * TRAVEL_PULL * arc;
    var angle = TRAVEL_SPIN * arc;
    var dx = x - cx, dy = y - cy;
    x = cx + dx * Math.cos(angle) - dy * Math.sin(angle);
    y = cy + dx * Math.sin(angle) + dy * Math.cos(angle);

    return { dx: x - home.x, dy: y - home.y, scale: 1 + 0.13 * arc, air: arc };
  }

  // ------------------------------------------------------------- updates ----
  function update(dt) {
    G.now += dt;
    G.cards.forEach(function (card) {
      card.hover = hit(card.rect, G.mouse);
      card.update(dt);
    });

    if (G.toasts.length) {
      G.toasts[0].left -= dt;
      if (G.toasts[0].left <= 0) { G.toasts.shift(); }
    }
    G.flashTimer = Math.max(0, G.flashTimer - dt);
    G.shakeTimer = Math.max(0, G.shakeTimer - dt);
    if (G.travelT < 1) {
      G.travelT = Math.min(1, G.travelT + dt / TRAVEL_TIME);
      if (G.travelT >= 1) { G.travel = {}; }
    }

    if (G.confirmRestart) { return; }

    if (G.state === COMPARE) {
      G.elapsed += dt;
      G.compareTimer -= dt;
      if (G.compareTimer <= 0) { resolveCompare(); }
    } else if (G.state === PLAYING) {
      if (G.timerRunning) { G.elapsed += dt; }
    } else if (G.state === SHUFFLE) {
      G.shuffleTimer += dt;                    // the clock is frozen here
      if (!G.shuffledYet && G.shuffleTimer >= SHUFFLE_LEAD) {
        shuffleFaceDown();
        G.shuffledYet = true;
      }
      if (G.shuffleTimer >= SHUFFLE_TOTAL) {
        G.state = PLAYING;
        checkProgress();       // angry may have been the last thing to find
      }
    }
  }

  function resolveCompare() {
    var a = G.cards[G.first], b = G.cards[G.second];
    if (a.key === b.key) {
      a.setMatched();
      b.setMatched();
      G.pairsFound += 1;
      playSound("match");
    } else {
      a.flipDown();
      b.flipDown();
    }
    G.first = null;
    G.second = null;
    G.state = PLAYING;
    checkProgress();
  }

  function checkProgress() {
    if (G.pairsFound < PAIR_COUNT) { return; }
    if (G.angryDone && G.laughDone) { win(); }
    else { toast(MSG_HIDING, C.YELLOW_DARK); }
  }

  function win() {
    G.state = VICTORY;
    G.timerRunning = false;
    stopLaugh();
    playSound("victory");
    if (isBetter(G.elapsed, G.flips, G.record)) {
      G.record = { best_time: G.elapsed, best_flips: G.flips };
      saveRecord(G.record);
      G.newRecord = true;
    } else {
      G.newRecord = false;
    }
  }

  // ---------------------------------------------------------------- draw ----
  function background() {
    if (!G.background || G.background.width !== Math.round(W) ||
        G.background.height !== Math.round(H)) {
      G.background = offscreen(W, H);
      var g = G.background.getContext("2d");
      var grad = g.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, C.BG_TOP);
      grad.addColorStop(1, C.BG_BOTTOM);
      g.fillStyle = grad;
      g.fillRect(0, 0, W, H);
    }
    return G.background;
  }

  function draw() {
    ctx.drawImage(background(), 0, 0);

    if (G.state === TITLE) {
      drawTitle();
    } else {
      drawHud();
      drawBoard();
      drawFooter();
      if (G.state === VICTORY) { drawVictory(); }
    }

    if (G.flashTimer > 0) {
      ctx.fillStyle = rgba(C.RED, 0.59 * (G.flashTimer / FLASH_TIME));
      ctx.fillRect(0, 0, W, H);
    }
    if (G.confirmRestart) { drawConfirm(); }
  }

  function drawTitle() {
    var s = G.scale, cx = W / 2, tl = G.tl;
    var bob = reduceMotion ? 0 : 4 * Math.sin(G.now * 2.2);
    text("Nailong Memory", 66 * s, C.PINK_DARK, "center", cx, tl.title1, true,
         true);
    text("MAYHEM", 76 * s, C.BLUE_DARK, "center", cx, tl.title2 + bob, true,
         true);

    var art = tl.art, gap = 46 * s;
    [[-art / 2 - gap / 2, ANGRY_KEY, "ANGRY", C.RED],
     [art / 2 + gap / 2, LAUGH_KEY, "LAUGHING", C.PURPLE]].forEach(function (it) {
      var bx = cx + it[0] - art / 2, by = tl.artY - art / 2;
      fillRR(ctx, bx - 5, by - 5, art + 10, art + 10, 14, it[3]);
      strokeRR(ctx, bx - 5, by - 5, art + 10, art + 10, 14, C.WHITE, 3);
      ctx.save();
      rrPath(ctx, bx, by, art, art, 10);
      ctx.clip();
      drawContained(ctx, it[1], bx + art / 2, by + art / 2, art, art);
      ctx.restore();
      text(it[2], 20 * s, it[3], "midtop", bx + art / 2, by + art + 5 + 4 * s,
           true);
    });

    var lines = [
      "Find all 7 matching pairs on the 4x4 board.",
      "Two Nailongs hide in there and they have no partner.",
      "Angry Nailong reshuffles every card still face down.",
      "Laughing Nailong cackles for the rest of the game.",
      "Match all 7 pairs AND find both Nailongs to win!"
    ];
    lines.forEach(function (line, i) {
      text(line, 23 * s, i % 2 === 0 ? C.INK : C.INK_SOFT, "center", cx,
           tl.textTop + i * tl.lineH, false);
    });

    ["start", "sound_title", "quit_title"].forEach(function (name) {
      G.buttons[name].draw(G.mouse, s);
    });

    if (G.record) {
      text("Best: " + formatTime(G.record.best_time) + " with "
           + G.record.best_flips + " flips", 22 * s, C.GREEN_DARK, "midleft",
           26 * s, tl.bottomY, true);
    }
    text(CREDIT, 19 * s, C.PINK_DARK, "midright", W - 26 * s, tl.bottomY, true);
    text("Click a card   -   M mute   -   R restart   -   ESC back", 18 * s,
         C.INK_SOFT, "center", cx, H - 22 * s, false);
  }

  function drawHud() {
    var s = G.scale;
    fillRR(ctx, G.hud.x, G.hud.y, G.hud.w, G.hud.h, 18, C.PANEL);
    strokeRR(ctx, G.hud.x, G.hud.y, G.hud.w, G.hud.h, 18, C.PANEL_EDGE, 2);
    setFont(30 * s, true);
    if (ctx.measureText("Nailong Memory Mayhem").width < G.hudTitleRoom) {
      text("Nailong Memory Mayhem", 30 * s, C.PINK_DARK, "midleft",
           G.hud.x + 18 * s, G.hud.y + G.hud.h / 2, true);
    }
    ["mute", "restart", "title"].forEach(function (name) {
      G.buttons[name].draw(G.mouse, s);
    });

    fillRR(ctx, G.stats.x, G.stats.y, G.stats.w, G.stats.h, 16, C.PANEL);
    strokeRR(ctx, G.stats.x, G.stats.y, G.stats.w, G.stats.h, 16, C.PANEL_EDGE, 2);
    var best = G.record ? formatTime(G.record.best_time) : "--:--.-";
    var bestFlips = G.record ? String(G.record.best_flips) : "--";
    var stats = [
      ["TIME", formatTime(G.elapsed), C.BLUE_DARK],
      ["FLIPS", String(G.flips), C.PINK_DARK],
      ["PAIRS", G.pairsFound + " / " + PAIR_COUNT, C.GREEN_DARK],
      ["BEST TIME", best, C.YELLOW_DARK],
      ["BEST FLIPS", bestFlips, C.YELLOW_DARK],
      ["SOUND", audio.muted ? "OFF" : "ON",
       audio.muted ? C.INK_SOFT : C.BLUE_DARK]
    ];
    var cw = G.stats.w / stats.length;
    stats.forEach(function (item, i) {
      var x = G.stats.x + cw * (i + 0.5);
      text(item[0], 15 * s, C.INK_SOFT, "center", x, G.stats.y + 14 * s, false);
      text(item[1], 24 * s, item[2], "center", x, G.stats.y + 32 * s, true);
      if (i) {
        var lx = Math.round(G.stats.x + cw * i);
        ctx.strokeStyle = C.PANEL_EDGE;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(lx, G.stats.y + 8);
        ctx.lineTo(lx, G.stats.y + G.stats.h - 8);
        ctx.stroke();
      }
    });
  }

  function drawBoard() {
    var s = G.scale, offset = { x: 0, y: 0 };
    if (G.shakeTimer > 0) {
      var power = 14 * (G.shakeTimer / SHAKE_TIME);
      offset.x = Math.sin(G.now * 47) * power;
      offset.y = Math.cos(G.now * 39) * power * 0.6;
    }
    var p = { x: G.board.x - 13 * s + offset.x, y: G.board.y - 13 * s + offset.y,
              w: G.board.w + 26 * s, h: G.board.h + 26 * s };
    fillRR(ctx, p.x, p.y, p.w, p.h, 24, "rgba(255,255,255,0.47)");
    strokeRR(ctx, p.x, p.y, p.w, p.h, 24, C.PANEL_EDGE, 3);

    var flying = [], revealed = [];
    G.cards.forEach(function (card) {
      var flight = travelState(card);
      if (flight) { flying.push({ card: card, f: flight }); }
      else if (card.locked) { revealed.push(card); }
      else { card.draw(offset, G.now); }
    });
    flying.sort(function (a, b) {
      return (a.card.centre().y + a.f.dy) - (b.card.centre().y + b.f.dy);
    });
    flying.forEach(function (it) {
      it.card.draw({ x: offset.x + it.f.dx, y: offset.y + it.f.dy }, G.now,
                   it.f.scale, it.f.air);
    });

    var laughRect = null;
    revealed.forEach(function (card) {
      var drawn = card.draw(offset, G.now);
      if (card.kind === LAUGH) { laughRect = drawn; }
    });
    if (laughRect && G.state !== VICTORY) { drawHaHa(laughRect); }
  }

  function drawHaHa(r) {
    var s = G.scale;
    var bx = G.board.x - 36 * s, bx2 = G.board.x + G.board.w + 36 * s;
    var cx = r.x + r.w / 2, cy = r.y + r.h / 2;
    for (var i = 0; i < 7; i++) {
      var angle = G.now * 1.5 + i * (Math.PI * 2 / 7);
      var x = cx + Math.cos(angle) * r.w * 0.88;
      var y = cy + Math.sin(angle * 1.3) * r.h * 0.72;
      x = Math.min(Math.max(x, bx), bx2);
      y = Math.min(Math.max(y, G.board.y), G.board.y + G.board.h);
      var size = (26 + 8 * Math.sin(G.now * 5 + i)) * s;
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(-Math.sin(angle) * 28 * Math.PI / 180);
      setFont(size, true);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.strokeStyle = C.WHITE;
      ctx.lineWidth = 3;
      ctx.lineJoin = "round";
      ctx.miterLimit = 2;
      ctx.strokeText("HA", 0, 0);
      ctx.fillStyle = i % 2 ? C.PURPLE : C.YELLOW_DARK;
      ctx.fillText("HA", 0, 0);
      ctx.restore();
    }
  }

  function drawFooter() {
    var s = G.scale;
    if (G.toasts.length) {
      var t = G.toasts[0], r = G.toastRect;
      fillRR(ctx, r.x, r.y + 4, r.w, r.h, 18, shade(t.colour, 45));
      fillRR(ctx, r.x, r.y, r.w, r.h, 18, t.colour);
      strokeRR(ctx, r.x, r.y, r.w, r.h, 18, C.WHITE, 3);
      var wobble = reduceMotion ? 0 : 2 * Math.sin(G.now * 9);
      textFitted(t.text, 25 * s, C.WHITE, r, true, wobble);
    }
    text("Click: flip   -   M: mute   -   R: restart   -   ESC: title screen",
         18 * s, C.INK_SOFT, "center", W / 2, G.footerY, false);
  }

  function dim(alpha) {
    ctx.fillStyle = "rgba(40,30,25," + alpha + ")";
    ctx.fillRect(0, 0, W, H);
  }

  function drawVictory() {
    var s = G.scale, p = G.victory, cx = p.x + p.w / 2;
    dim(0.65);
    fillRR(ctx, p.x, p.y, p.w, p.h, 28, C.PANEL);
    strokeRR(ctx, p.x, p.y, p.w, p.h, 28, C.GREEN_DARK, 5);
    var bounce = reduceMotion ? 0 : 6 * Math.sin(G.now * 4);
    textFitted("YOU BEAT THE MAYHEM!", 44 * s, C.GREEN_DARK,
               { x: p.x, y: p.y + 56 * s + bounce - 5, w: p.w, h: 10 }, true);
    text("Time " + formatTime(G.elapsed) + "   -   " + G.flips + " flips",
         30 * s, C.INK, "center", cx, p.y + 112 * s, true);
    if (G.newRecord) {
      text("NEW BEST RECORD!", 30 * s, C.PINK_DARK, "center", cx,
           p.y + 154 * s, true);
    } else if (G.record) {
      text("Best: " + formatTime(G.record.best_time) + " with "
           + G.record.best_flips + " flips", 23 * s, C.INK_SOFT, "center", cx,
           p.y + 154 * s, false);
    }
    text("7 / 7 pairs  +  both Nailongs found", 22 * s, C.BLUE_DARK, "center",
         cx, p.y + 192 * s, false);
    ["again", "to_title", "quit_win"].forEach(function (name) {
      G.buttons[name].draw(G.mouse, s);
    });
  }

  function drawConfirm() {
    var s = G.scale, r = G.confirm;
    dim(0.59);
    fillRR(ctx, r.x, r.y, r.w, r.h, 26, C.PANEL);
    strokeRR(ctx, r.x, r.y, r.w, r.h, 26, C.YELLOW_DARK, 5);
    text("Restart this game?", 34 * s, C.INK, "center", r.x + r.w / 2,
         r.y + 52 * s, true);
    text("Your time and flips will be reset.", 21 * s, C.INK_SOFT, "center",
         r.x + r.w / 2, r.y + 88 * s, false);
    ["yes", "no"].forEach(function (name) {
      G.buttons[name].draw(G.mouse, s);
    });
  }

  // --------------------------------------------------------------- input ----
  function requestRestart() {
    var inProgress = (G.state === PLAYING || G.state === COMPARE
                      || G.state === SHUFFLE) && (G.flips > 0 || G.pairsFound > 0);
    if (inProgress) { G.confirmRestart = true; } else { resetGame(); }
  }

  function toggleMute() {
    setMuted(!audio.muted);
    syncSoundLabels();
    return audio.muted;
  }

  function onKey(key) {
    audioInit();
    audioResume();
    if (key === "m") {
      toast(toggleMute() ? "SOUND MUTED" : "SOUND ON", C.BLUE_DARK);
      return;
    }
    if (G.confirmRestart) {
      if (key === "y" || key === "enter" || key === "r") { resetGame(); }
      else if (key === "n" || key === "escape") { G.confirmRestart = false; }
      return;
    }
    if (key === "escape") {
      if (G.state !== TITLE) { goToTitle(); }
      return;
    }
    if (key === "r") {
      if (G.state !== TITLE) { requestRestart(); }
      return;
    }
    if ((key === "enter" || key === " ") && G.state === TITLE) { resetGame(); }
  }

  function onClick(pos) {
    audioInit();
    audioResume();
    G.mouse = pos;
    var B = G.buttons;

    if (G.confirmRestart) {
      if (hit(B.yes.rect, pos)) { resetGame(); }
      else if (hit(B.no.rect, pos)) { G.confirmRestart = false; }
      return;
    }
    if (G.state === TITLE) {
      if (hit(B.start.rect, pos)) { resetGame(); }
      else if (hit(B.quit_title.rect, pos)) { showQuit(); }
      else if (hit(B.sound_title.rect, pos)) { toggleMute(); }
      return;
    }
    if (G.state === VICTORY) {
      if (hit(B.again.rect, pos)) { resetGame(); }
      else if (hit(B.to_title.rect, pos)) { goToTitle(); }
      else if (hit(B.quit_win.rect, pos)) { showQuit(); }
      return;
    }
    if (hit(B.mute.rect, pos)) {
      toast(toggleMute() ? "SOUND MUTED" : "SOUND ON", C.BLUE_DARK);
      return;
    }
    if (hit(B.restart.rect, pos)) { requestRestart(); return; }
    if (hit(B.title.rect, pos)) { goToTitle(); return; }

    if (G.state !== PLAYING) { return; }
    for (var i = 0; i < G.cards.length; i++) {
      if (hit(G.cards[i].rect, pos)) { clickCard(G.cards[i]); break; }
    }
  }

  /* A browser tab cannot close itself, so "Quit" goes back to the title and
     says so rather than pretending to exit. */
  function showQuit() {
    goToTitle();
    stopLaugh();
    var note = document.getElementById("quitnote");
    if (note) {
      note.classList.add("show");
      window.setTimeout(function () { note.classList.remove("show"); }, 3200);
    }
  }

  function pointerPos(evt) {
    var r = canvas.getBoundingClientRect();
    return { x: evt.clientX - r.left, y: evt.clientY - r.top };
  }

  function bindInput() {
    canvas.addEventListener("mousemove", function (e) {
      G.mouse = pointerPos(e);
    });
    canvas.addEventListener("mouseleave", function () { G.mouse = null; });
    canvas.addEventListener("mousedown", function (e) {
      if (e.button === 0) { onClick(pointerPos(e)); }
    });
    canvas.addEventListener("touchstart", function (e) {
      if (e.touches.length) {
        var r = canvas.getBoundingClientRect();
        onClick({ x: e.touches[0].clientX - r.left,
                  y: e.touches[0].clientY - r.top });
        G.mouse = null;
      }
      e.preventDefault();
    }, { passive: false });
    window.addEventListener("keydown", function (e) {
      var key = e.key.length === 1 ? e.key.toLowerCase() : e.key.toLowerCase();
      if (["arrowup", "arrowdown", "arrowleft", "arrowright", " "].indexOf(key)
          >= 0) { e.preventDefault(); }
      onKey(key);
    });
    window.addEventListener("resize", resize);
    window.addEventListener("orientationchange", resize);
  }

  function resize() {
    var vw = window.innerWidth, vh = window.innerHeight;
    // keep roughly the shape of the desktop window, and never overflow
    var h = Math.min(vh - 8, 980);
    var w = Math.min(vw - 8, Math.max(560, Math.round(h * 1.15)));
    h = Math.max(420, h);
    w = Math.max(360, w);
    dpr = Math.min(2, window.devicePixelRatio || 1);
    W = w;
    H = h;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    layout();
  }

  // ---------------------------------------------------------------- boot ----
  function loadImages() {
    var keys = Object.keys(ASSETS.images);
    return Promise.all(keys.map(function (key) {
      return new Promise(function (done) {
        var img = new Image();
        img.onload = function () { images[key] = img; done(); };
        img.onerror = function () {
          window.console && console.warn("[assets] could not decode " + key);
          done();
        };
        img.src = ASSETS.images[key];
      });
    }));
  }

  var last = 0;
  function frame(stamp) {
    if (!last) { last = stamp; }
    var dt = Math.min(0.05, (stamp - last) / 1000);
    last = stamp;
    update(dt);
    draw();
    window.requestAnimationFrame(frame);
  }

  function boot() {
    buildButtons();
    G.record = loadRecord();
    resize();
    bindInput();
    audioInit();

    loadImages().then(function () {
      surfaces = {};
      var boot = document.getElementById("boot");
      if (boot) { boot.classList.add("gone"); }
      syncSoundLabels();
      window.requestAnimationFrame(frame);
      return audioDecodeAll();      // finishes in the background
    }).catch(function (err) {
      var boot = document.getElementById("boot");
      if (boot) {
        boot.textContent = "Something went wrong while loading: " + err;
      }
    });
  }

  /* Read-only snapshot of the game, for debugging from the browser console -
     a canvas has no DOM to inspect.  Nothing here can change the game. */
  window.NAILONG_STATE = function () {
    var buttons = {};
    Object.keys(G.buttons).forEach(function (name) {
      var r = G.buttons[name].rect;
      buttons[name] = { x: Math.round(r.x + r.w / 2),
                        y: Math.round(r.y + r.h / 2) };
    });
    return {
      state: G.state, flips: G.flips, pairs: G.pairsFound,
      elapsed: Math.round(G.elapsed * 100) / 100,
      timerRunning: G.timerRunning,
      angryFound: G.angryDone, laughFound: G.laughDone,
      travelT: Math.round(G.travelT * 100) / 100,
      shake: Math.round(G.shakeTimer * 100) / 100,
      confirm: G.confirmRestart, newRecord: G.newRecord, record: G.record,
      muted: audio.muted, audioOk: audio.ok,
      soundsDecoded: Object.keys(audio.buffers).sort(),
      laughing: !!audio.laughSource,
      toasts: G.toasts.map(function (t) { return t.text; }),
      size: [Math.round(W), Math.round(H)],
      scale: Math.round(G.scale * 100) / 100,
      buttons: buttons,
      cards: G.cards.map(function (c) {
        return { i: c.index, kind: c.kind, key: c.key, matched: c.matched,
                 locked: c.locked, turn: Math.round(c.turn * 100) / 100,
                 x: Math.round(c.rect.x + c.rect.w / 2),
                 y: Math.round(c.rect.y + c.rect.h / 2) };
      })
    };
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
