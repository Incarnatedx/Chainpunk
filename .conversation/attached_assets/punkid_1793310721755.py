"""Draws a Punk ID card from a punk's on-chain data. Pillow only for the card itself."""
import base64
import io
import json
import os
import textwrap
import time
import urllib.parse

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 675
BG = (10, 10, 10)
FG = (232, 230, 224)
DIM = (130, 132, 140)
LINE = (48, 48, 52)
ACCENT = (110, 231, 183)

FONT_CANDIDATES = [
    os.environ.get("FONT_PATH", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "/System/Library/Fonts/Menlo.ttc",
]


def _font(size):
    for path in FONT_CANDIDATES:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _decode_data_uri(uri):
    head, _, body = uri.partition(",")
    if ";base64" in head:
        return base64.b64decode(body)
    return urllib.parse.unquote_to_bytes(body)


def parse_token_uri(uri):
    """tokenURI -> (metadata dict, svg bytes). Both are data URIs on this contract."""
    meta = json.loads(_decode_data_uri(uri))
    svg = _decode_data_uri(meta.get("image", ""))
    return meta, svg


def parse_soul(text, limit=3):
    """Pull the 'HOW I ACT' bullets out of the punk's soul page."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().lstrip("#").strip().lower() == "how i act":
            start = i + 1
            break
    if start is None:
        return []
    bullets = []
    for line in lines[start:]:
        s = line.strip()
        if s.startswith("```") or (s.startswith("#") and bullets):
            break
        if s.startswith(("-", "*")):
            bullets.append(s.lstrip("-* ").strip())
        elif s and bullets:  # wrapped continuation of the previous bullet
            bullets[-1] += " " + s
    return bullets[:limit]


def svg_to_png(svg_bytes, size=1000):
    """SVG -> PNG. Default is cairosvg; set RENDERER=browser to use Playwright instead
    (use it if the glyphs look wrong, since it honours fonts embedded in the SVG)."""
    if os.environ.get("RENDERER", "cairosvg") == "browser":
        from playwright.sync_api import sync_playwright

        b64 = base64.b64encode(svg_bytes).decode()
        html = (
            f"<body style='margin:0;background:#0a0a0a'>"
            f"<img src='data:image/svg+xml;base64,{b64}' style='width:{size}px;height:{size}px;object-fit:contain'>"
        )
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": size, "height": size})
            page.set_content(html)
            png = page.screenshot()
            browser.close()
        return png
    import cairosvg

    return cairosvg.svg2png(bytestring=svg_bytes, output_width=size, background_color="#0a0a0a")


def _short(addr):
    return f"{addr[:6]}…{addr[-4:]}" if addr and len(addr) > 12 else (addr or "-")


def make_card(art, d, show_holder=True):
    """art: PIL image of the punk. d: dict with token_id, traits [(k, v)], genome, holder,
    held_since (unix seconds or None), soul [str]."""
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle((16, 16, W - 16, H - 16), radius=22, outline=LINE, width=2)

    dr.text((48, 38), "PUNK ID", font=_font(30), fill=FG)
    dr.text((W - 48, 38), f"#{d['token_id']}", font=_font(30), fill=ACCENT, anchor="ra")
    dr.line((48, 90, W - 48, 90), fill=LINE, width=2)

    # art panel
    px, py, ps = 48, 110, 500
    dr.rounded_rectangle((px, py, px + ps, py + ps), radius=14, fill=(12, 12, 12), outline=LINE, width=2)
    a = art.convert("RGBA")
    bg = Image.new("RGBA", a.size, BG + (255,))
    a = Image.alpha_composite(bg, a).convert("RGB")
    a.thumbnail((ps - 24, ps - 24), Image.LANCZOS)
    img.paste(a, (px + (ps - a.width) // 2, py + (ps - a.height) // 2))

    # traits grid
    x0, y0 = 608, 110
    lab, val = _font(15), _font(21)
    shown = [(k, v) for k, v in d["traits"] if str(v).strip().lower() != "none"]
    for i, (k, v) in enumerate(shown[:12]):
        cx = x0 + (i % 2) * 280
        cy = y0 + (i // 2) * 46
        dr.text((cx, cy), str(k).upper(), font=lab, fill=DIM)
        dr.text((cx, cy + 18), str(v), font=val, fill=FG)

    # meta row
    my = y0 + 6 * 46 + 12
    dr.line((x0, my - 8, W - 48, my - 8), fill=LINE, width=1)
    held = time.strftime("%d %b %Y", time.gmtime(d["held_since"])) if d.get("held_since") else "-"
    meta = [("GENOME", _short(d.get("genome", ""))), ("HOLDER", _short(d.get("holder", "")) if show_holder else "hidden"), ("HELD SINCE", held)]
    for i, (k, v) in enumerate(meta):
        cx = x0 + i * 185
        dr.text((cx, my), k, font=lab, fill=DIM)
        dr.text((cx, my + 18), v, font=_font(19), fill=FG)

    # soul
    sy = my + 66
    dr.line((x0, sy - 8, W - 48, sy - 8), fill=LINE, width=1)
    dr.text((x0, sy), "SOUL · HOW I ACT", font=lab, fill=ACCENT)
    lines = []
    for b in d.get("soul", []):
        lines += textwrap.wrap("• " + b, width=52, subsequent_indent="  ") or []
    lines = lines[:4]
    if len(lines) == 4 and sum(len(textwrap.wrap("• " + b, width=52)) for b in d["soul"]) > 4:
        lines[-1] = lines[-1][:49] + "…"
    for j, line in enumerate(lines):
        dr.text((x0, sy + 24 + j * 24), line, font=_font(17), fill=FG)

    dr.text((48, H - 46), "fan-made  ·  art is CC0  ·  not an official Chain Punks product", font=_font(14), fill=DIM)
    return img
