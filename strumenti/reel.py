#!/usr/bin/env python3
"""Generatore di Reel Ribasso Tech (1080x1920, 30 fps, MP4 H.264 + AAC) per TikTok, Facebook e Instagram.

Uso:  python3 reel.py spec.json uscita.mp4 [--muto]
Crea anche uscita_copertina.png (fotogramma del gancio, da usare come copertina).

spec.json, due tipi:

1) Offerte reali (prezzi presi da offerte.json del catalogo):
{"type": "offerte",
 "hook": ["3 OFFERTE TECH", "DI OGGI"],          # 1-3 righe, l'ultima in arancione
 "hook_sub": "prezzi controllati sullo storico", # facoltativo
 "offers": [ {"name": "...", "price": 29.99, "list_price": 89.99, "discount": 67,
              "cat_label": "🏠 Casa smart", "deal": "min|prime|tempo|err|null", "ts": "2026-10-08T09:30+02:00"} ],
 "cta": "Link nel canale Telegram"}               # facoltativo

2) Tema (video educativo / curiosita'):
{"type": "tema",
 "scenes": [
   {"title": ["QUESTO SCONTO"], "highlight": "È FALSO", "sub": "...", "tag": "-50%", "emoji": "❌"},
   {"chart": {"values": [39,39,41,40,79,79,80,39.5], "low_label": "39€", "high_label": "79€",
              "tag": "-50%", "top": "Prima alzano il prezzo…", "top2": "…poi te lo \"scontano\"",
              "bottom": "Stesso prezzo di prima."}},
   {"title": ["Noi controlliamo lo"], "highlight": "STORICO PREZZI", "sub": "...",
    "bullets": [["✅", "Minimi storici veri"], ["⚡", "Errori di prezzo"]]}
 ]}
Ogni video finisce con la scena "Segui RIBASSO TECH" (Telegram @ribasso_tech).
"""
import json, math, os, subprocess, sys, textwrap, urllib.request
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
BG = (14, 14, 17); OR = (255, 138, 0); OR2 = (255, 176, 32); RED = (255, 72, 60)
GREEN = (60, 210, 120); WHITE = (245, 245, 247); GREY = (154, 159, 171); CARD = (30, 30, 37); LINE = (52, 52, 62)
HERE = Path(__file__).resolve().parent

# ---------- font ----------
def _font_path(weight):
    for d in (HERE / "fonts", Path.home() / "offerteloraesp32" / "fonts", Path("/tmp/reel_fonts")):
        p = d / f"Poppins-{weight}.ttf"
        if p.exists():
            return p
    d = Path("/tmp/reel_fonts"); d.mkdir(exist_ok=True)
    p = d / f"Poppins-{weight}.ttf"
    try:
        urllib.request.urlretrieve(f"https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-{weight}.ttf", p)
        return p
    except Exception:
        for alt in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            if Path(alt).exists():
                return Path(alt)
    raise SystemExit("Nessun font disponibile")
_fc = {}
def F(weight, size):
    k = (weight, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(str(_font_path(weight)), size)
    return _fc[k]

EMO_PATH = next((p for p in ("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
                             "/usr/share/fonts/noto/NotoColorEmoji.ttf") if Path(p).exists()), None)
_ec = {}
def emoji(ch, size):
    """Emoji a colori come immagine RGBA (None se il font emoji non c'e')."""
    if not EMO_PATH or not ch:
        return None
    k = (ch, size)
    if k not in _ec:
        f = ImageFont.truetype(EMO_PATH, 109)
        e = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(e).text((8, 8), ch, font=f, embedded_color=True)
        bb = e.getbbox()
        _ec[k] = e.crop(bb).resize((size, size), Image.LANCZOS) if bb else None
    return _ec[k]

def split_emoji(label):
    """'🏠 Casa smart' -> ('🏠', 'Casa smart')"""
    if label and not label[0].isalnum() and " " in label:
        a, b = label.split(" ", 1)
        return a, b
    return None, label or ""

# ---------- animazione ----------
def clamp(x): return max(0.0, min(1.0, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def back(x):
    x = clamp(x); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

def make_base():
    im = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), BG); g = ImageDraw.Draw(glow)
    g.ellipse((-400, -300, 900, 800), fill=(110, 50, 0)); g.ellipse((300, 1300, 1500, 2300), fill=(90, 40, 0))
    return Image.blend(im, glow.filter(ImageFilter.GaussianBlur(220)), 0.85)
BASE = None

def header(d):
    x, y = 70, 120
    d.rounded_rectangle((x, y, x + 64, y + 64), 16, fill=OR)
    d.polygon([(x+32, y+53), (x+13, y+30), (x+24, y+30), (x+24, y+11), (x+40, y+11), (x+40, y+30), (x+51, y+30)], fill=BG)
    f = F("Bold", 46); d.text((x + 82, y + 4), "RIBASSO", font=f, fill=WHITE)
    d.text((x + 82 + d.textlength("RIBASSO ", font=f), y + 4), "TECH", font=f, fill=OR)

def fit(text, weight, size, maxw, minsize=34):
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    while size > minsize and d.textlength(text, font=F(weight, size)) > maxw:
        size -= 4
    return F(weight, size)

def ltext(im, y, txt, font, fill, a=1.0, scale=1.0, x=None):
    """Testo (centrato se x e' None) con opacita' e scala."""
    if a <= 0 or not txt:
        return
    a = clamp(a)
    td0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    w = int(td0.textlength(txt, font=font)) + 20
    h = int(font.size * 1.5)
    tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((10, font.size * 0.15), txt, font=font, fill=fill + (int(255 * a),))
    if scale != 1.0 and scale > 0.05:
        tmp = tmp.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    px = int((W - tmp.width) / 2) if x is None else int(x)
    im.paste(tmp, (px, int(y - font.size * 0.15 * scale)), tmp)

def pill(im, cx, cy, txt, color, fg=(255, 255, 255), size=120, ang=0, s=1.0, a=1.0):
    if s <= 0.02 or a <= 0:
        return
    f = F("Bold", size)
    td0 = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    tw = td0.textlength(txt, font=f)
    w, h = int(tw + size * 1.0), int(size * 1.75)
    t = Image.new("RGBA", (w, h), (0, 0, 0, 0)); td = ImageDraw.Draw(t)
    td.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=color + (int(255 * a),))
    td.text(((w - tw) / 2, h * 0.16), txt, font=f, fill=fg + (int(255 * a),))
    t = t.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    if ang:
        t = t.rotate(ang, expand=True, resample=Image.BICUBIC)
    im.paste(t, (int(cx - t.width / 2), int(cy - t.height / 2)), t)

def paste_emoji(im, ch, x, y, size, a=1.0):
    e = emoji(ch, size)
    if e is None or a <= 0:
        return
    if a < 1:
        e = e.copy(); e.putalpha(e.getchannel("A").point(lambda v: int(v * a)))
    im.paste(e, (int(x), int(y)), e)

def eur(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "€"

# ---------- scene ----------
def scene_text(sc):
    """Titolo + evidenziato + sottotitolo + eventuali etichetta/emoji/punti elenco."""
    title = sc.get("title") or []
    if isinstance(title, str):
        title = [title]
    hl, sub, bullets = sc.get("highlight"), sc.get("sub"), sc.get("bullets") or []
    has_low = bool(sc.get("tag") or bullets)
    dur = sc.get("dur") or (4.2 if bullets else 3.0)
    def draw(t):
        im = BASE.copy(); d = ImageDraw.Draw(im); header(d)
        y = 330 if has_low else 600
        for i, ln in enumerate(title):
            f = fit(ln, "Bold", 96, W - 160)
            ltext(im, y, ln, f, WHITE, ease((t - i * .12) / .3), 0.85 + 0.15 * back((t - i * .12) / .35))
            y += int(f.size * 1.12)
        if hl:
            f = fit(hl, "Bold", 150, W - 140)
            st = .15 + .12 * len(title)
            ltext(im, y, hl, f, OR if not sc.get("red") else RED, ease((t - st) / .3), 0.6 + 0.4 * back((t - st) / .4))
            y += int(f.size * 1.15)
        if sub:
            for j, ln in enumerate(textwrap.wrap(sub, 40)[:3]):
                ltext(im, y + 10, ln, F("Medium", 44), GREY, ease((t - .5) / .35))
                y += 58
        if sc.get("tag"):
            s = back((t - .6) / .35)
            shake = math.sin(t * 40) * 4 * clamp((t - .9) / .2) if t < dur - .5 else 0
            pill(im, W / 2, max(y + 260, 1000), sc["tag"], RED, size=120, ang=-8 + shake, s=s)
            if sc.get("emoji") and t > 1.0:
                paste_emoji(im, sc["emoji"], W / 2 + 190, max(y + 260, 1000) - 110, 150, ease((t - 1.0) / .3))
        elif sc.get("emoji") and not bullets:
            paste_emoji(im, sc["emoji"], W / 2 - 90, y + 80, 180, ease((t - .6) / .3))
        for i, (e, txt) in enumerate(bullets[:4]):
            st = .9 + i * .5; a = ease((t - st) / .35)
            if a <= 0:
                continue
            by = y + 90 + i * 180; dx = int((1 - a) * 120)
            card = Image.new("RGBA", (900, 150), (0, 0, 0, 0)); cd = ImageDraw.Draw(card)
            cd.rounded_rectangle((0, 0, 899, 149), 40, fill=CARD + (int(255 * a),), outline=LINE + (int(255 * a),), width=3)
            em = emoji(e, 84)
            tx = 40
            if em is not None:
                em = em.copy(); em.putalpha(em.getchannel("A").point(lambda v: int(v * a)))
                card.paste(em, (40, 33), em); tx = 150
            f = fit(txt, "Bold", 56, 900 - tx - 40)
            cd.text((tx, 75 - f.size * 0.62), txt, font=f, fill=WHITE + (int(255 * a),))
            im.paste(card, (90 + dx, by), card)
        return im
    return draw, dur

def scene_chart(c):
    vals = c["values"]; dur = c.get("dur", 4.5)
    def draw(t):
        im = BASE.copy(); d = ImageDraw.Draw(im); header(d)
        ltext(im, 300, c.get("top", ""), fit(c.get("top", ""), "Bold", 70, W - 140), WHITE, ease(t / .3))
        ltext(im, 390, c.get("top2", ""), fit(c.get("top2", ""), "Bold", 70, W - 140), OR, ease((t - 1.9) / .3))
        x0, y0, x1, y1 = 90, 560, 990, 1260
        d.rounded_rectangle((x0 - 20, y0 - 30, x1 + 20, y1 + 110), 36, fill=(26, 26, 32), outline=(46, 46, 56), width=3)
        for i in range(4):
            yy = y0 + 40 + i * (y1 - y0 - 40) / 3; d.line((x0 + 20, yy, x1 - 20, yy), fill=(46, 46, 56), width=2)
        lo, hi = min(vals) * 0.75, max(vals) * 1.12
        n = len(vals)
        xs = [x0 + 40 + i * (x1 - x0 - 80) / (n - 1) for i in range(n)]
        ys = [y1 - (v - lo) / (hi - lo) * (y1 - y0 - 60) for v in vals]
        prog = ease(t / 3.0) * (n - 1)
        pts = []
        for i in range(n):
            if i <= prog:
                pts.append((xs[i], ys[i]))
            else:
                f = prog - (i - 1); pts.append((xs[i-1] + (xs[i]-xs[i-1]) * f, ys[i-1] + (ys[i]-ys[i-1]) * f)); break
        if len(pts) > 1:
            d.line(pts, fill=OR, width=12, joint="curve")
        px, py = pts[-1]; d.ellipse((px - 18, py - 18, px + 18, py + 18), fill=WHITE)
        fl = F("Bold", 50)
        imax = vals.index(max(vals))
        if c.get("low_label"):
            d.text((xs[0] - 10, ys[0] + 30), c["low_label"], font=fl, fill=GREEN)
        if c.get("high_label") and prog >= imax:
            d.text((xs[imax] - 30, ys[imax] - 85), c["high_label"], font=fl, fill=RED)
        if c.get("tag") and prog >= n - 1.1:
            pill(im, xs[-1] - 120, ys[-1] - 150, c["tag"], RED, size=66, ang=8, s=back((t - 2.9) / .4))
        fm = F("Medium", 36)
        d.text((x0 + 10, y1 + 30), c.get("left", "settimane prima"), font=fm, fill=GREY)
        r = c.get("right", "oggi"); d.text((x1 - 10 - d.textlength(r, font=fm), y1 + 30), r, font=fm, fill=GREY)
        d.text((x0 + 10, y0 - 10), c.get("note", "ESEMPIO"), font=F("Bold", 30), fill=GREY)
        if c.get("bottom"):
            ltext(im, 1460, c["bottom"], fit(c["bottom"], "Bold", 64, W - 140), WHITE, ease((t - 3.3) / .3))
        return im
    return draw, dur

DEAL = {"min": ("MINIMO STORICO", GREEN, BG), "prime": ("FESTA PRIME", OR, BG),
        "tempo": ("OFFERTA A TEMPO", RED, WHITE), "err": ("ERRORE DI PREZZO?", RED, WHITE)}

def short_name(name, n=60):
    name = " ".join(name.replace("|", " ").split())
    for sep in (" - ", ", ", " – "):
        if sep in name[:n + 20]:
            name = name.split(sep)[0]
    return name if len(name) <= n else name[:n].rsplit(" ", 1)[0] + "…"

def scene_offer(o, idx, total):
    dur = 3.6
    price, lp = float(o["price"]), o.get("list_price")
    disc = o.get("discount")
    emo, cat = split_emoji(o.get("cat_label", ""))
    lines = textwrap.wrap(short_name(o["name"]), 22)[:3]
    when = ""
    try:
        when = "Prezzo rilevato alle " + datetime.fromisoformat(o["ts"]).strftime("%H:%M del %d/%m")
    except Exception:
        pass
    def draw(t):
        im = BASE.copy(); d = ImageDraw.Draw(im); header(d)
        # contatore 1/3
        fc = F("Bold", 40); txt = f"{idx}/{total}"
        d.text((W - 70 - d.textlength(txt, font=fc), 128), txt, font=fc, fill=GREY)
        # riquadro prodotto
        a = ease(t / .35); dy = int((1 - a) * 80)
        x0, y0, x1, y1 = 90, 300 + dy, 990, 1470 + dy
        card = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0)); cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), 48, fill=(24, 24, 30, int(255 * a)), outline=LINE + (int(255 * a),), width=3)
        im.paste(card, (x0, y0), card)
        # categoria con emoji grande
        if emo:
            paste_emoji(im, emo, W / 2 - 90, 360 + dy, 180, a)
        ltext(im, 570 + dy, cat.upper(), F("Bold", 40), GREY, a)
        y = 660 + dy
        for i, ln in enumerate(lines):
            ltext(im, y, ln, F("Bold", 70), WHITE, ease((t - .15 - i * .08) / .3))
            y += 84
        y += 30
        # prezzo vecchio barrato, poi prezzo nuovo che "scende"
        if lp and lp > price:
            f = F("Medium", 60); s = eur(lp); w = d.textlength(s, font=f)
            aa = ease((t - .4) / .3)
            ltext(im, y, s, f, GREY, aa)
            if t > .8:
                k = ease((t - .8) / .25)
                d.line(((W - w) / 2, y + 42, (W - w) / 2 + w * k, y + 42), fill=RED, width=7)
            y += 90
        pr = price if not (lp and lp > price) else lp - (lp - price) * ease((t - .9) / .7)
        ltext(im, y, eur(pr), F("Bold", 150), OR, ease((t - .85) / .25), 0.8 + 0.2 * back((t - .85) / .4))
        y += 205
        if disc:
            pill(im, W / 2, y + 40, f"-{disc}%", RED, size=64, ang=-4, s=back((t - 1.6) / .35))
            y += 120
        if o.get("deal") in DEAL and t > 1.9:
            lab, bg, fg = DEAL[o["deal"]]
            pill(im, W / 2, y + 40, lab, bg, fg=fg, size=40, s=back((t - 1.9) / .35))
        ltext(im, 1500, when, F("Medium", 34), GREY, ease((t - 1.2) / .4))
        ltext(im, 1550, "#ad · link affiliato nel canale Telegram", F("Medium", 34), GREY, ease((t - 1.2) / .4))
        return im
    return draw, dur

def scene_cta(text=None):
    dur = 3.7
    def draw(t):
        im = BASE.copy()
        s = back(t / .45); L = int(220 * s)
        if L > 4:
            lg = Image.new("RGBA", (220, 220), (0, 0, 0, 0)); ld = ImageDraw.Draw(lg)
            ld.rounded_rectangle((0, 0, 219, 219), 54, fill=OR + (255,))
            ld.polygon([(110, 182), (45, 104), (82, 104), (82, 38), (138, 38), (138, 104), (175, 104)], fill=BG + (255,))
            lg = lg.resize((L, L), Image.LANCZOS); im.paste(lg, ((W - L) // 2, 510 - L // 2), lg)
        ltext(im, 700, "Segui", F("Medium", 64), GREY, ease((t - .3) / .3))
        ltext(im, 790, "RIBASSO TECH", F("Bold", 124), WHITE, ease((t - .4) / .3), 0.8 + 0.2 * back((t - .4) / .4))
        ltext(im, 960, text or "Solo offerte vere, ogni giorno.", fit(text or "Solo offerte vere, ogni giorno.", "Bold", 58, W - 140), OR, ease((t - .8) / .3))
        if t > 1.3:
            pulse = 1 + 0.04 * math.sin((t - 1.3) * 6) if t > 1.7 else 1
            pill(im, W / 2, 1225, "Telegram: @ribasso_tech", OR, fg=BG, size=int(54 * pulse), a=ease((t - 1.3) / .35))
        ltext(im, 1340, "Anche su Facebook, Instagram e WhatsApp", F("Medium", 42), GREY, ease((t - 1.9) / .4))
        return im
    return draw, dur

# ---------- musica (base strumentale generata, nessun diritto d'autore) ----------
def make_music(path, seconds):
    try:
        import numpy as np, wave
    except ImportError:
        return False
    sr = 44100; n = int(sr * seconds); t = np.arange(n) / sr
    bpm = 112; beat = 60 / bpm
    out = np.zeros(n)
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    bar = beat * 4
    for k in range(int(seconds / bar) + 1):
        ch = chords[k % 4]; s0 = int(k * bar * sr); s1 = min(n, int((k + 1) * bar * sr))
        if s0 >= n: break
        tt = t[s0:s1] - k * bar
        env = np.minimum(1, tt * 8) * np.exp(-tt * 0.6)
        pad = sum(np.sin(2 * np.pi * hz(m) * tt) + 0.3 * np.sin(2 * np.pi * hz(m + 12) * tt) for m in ch)
        out[s0:s1] += 0.06 * pad * env
        bass = np.sign(np.sin(2 * np.pi * hz(ch[0] - 12) * tt)) * 0.5 + np.sin(2 * np.pi * hz(ch[0] - 12) * tt)
        out[s0:s1] += 0.05 * bass * np.exp(-((tt % beat)) * 5)
    for b in range(int(seconds / beat) + 1):
        s0 = int(b * beat * sr)
        if s0 >= n: break
        L = min(n - s0, int(0.25 * sr)); tt = np.arange(L) / sr
        kick = np.sin(2 * np.pi * (50 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 14)
        out[s0:s0 + L] += 0.45 * kick
        h0 = s0 + int(beat / 2 * sr)
        if h0 < n:
            L2 = min(n - h0, int(0.05 * sr))
            out[h0:h0 + L2] += 0.05 * np.random.uniform(-1, 1, L2) * np.exp(-np.arange(L2) / sr * 80)
    fade = int(sr * 1.0); out[-fade:] *= np.linspace(1, 0, fade); out[:2000] *= np.linspace(0, 1, 2000)
    out = out / max(1e-6, np.abs(out).max()) * 0.55
    data = (out * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(data.tobytes())
    return True

# ---------- main ----------
def build(spec, out, muted=False):
    global BASE
    BASE = make_base()
    scenes = []
    if spec["type"] == "offerte":
        offers = spec["offers"][:5]
        hook = spec.get("hook") or [f"{len(offers)} OFFERTE TECH", "DI OGGI"]
        scenes.append(scene_text({"title": hook[:-1], "highlight": hook[-1], "sub": spec.get("hook_sub", "prezzi controllati sullo storico"),
                                  "emoji": spec.get("hook_emoji", "🔥"), "dur": 2.6}))
        for i, o in enumerate(offers, 1):
            scenes.append(scene_offer(o, i, len(offers)))
    else:
        for sc in spec["scenes"]:
            scenes.append(scene_chart(sc["chart"]) if "chart" in sc else scene_text(sc))
    scenes.append(scene_cta(spec.get("cta")))
    total = sum(d for _, d in scenes)
    out = Path(out)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    wav = out.with_suffix(".wav")
    if not muted and make_music(wav, total):
        cmd += ["-i", str(wav)]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    prev = None; cover_done = False
    for k, (fn, dur) in enumerate(scenes):
        n = int(dur * FPS); last = None
        for i in range(n):
            fr = fn(i / FPS)
            if k == 0 and not cover_done and i == n - 5:
                fr.save(out.with_name(out.stem + "_copertina.png")); cover_done = True
            if prev is not None and i < 6:
                fr = Image.blend(prev, fr, (i + 1) / 7)
            p.stdin.write(fr.convert("RGB").tobytes()); last = fr
        prev = last
    p.stdin.close(); p.wait()
    if wav.exists():
        wav.unlink()
    if p.returncode:
        raise SystemExit("ffmpeg fallito")
    print(f"ok {out} ({total:.1f}s)")

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        raise SystemExit(__doc__)
    build(json.load(open(args[0], encoding="utf-8")), args[1], muted="--muto" in sys.argv)
