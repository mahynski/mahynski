"""Neon-glass "card" generator for the profile README.

Renders content sections (currently ``tl;dr`` and ``whoami``) as matched
light/dark PNG cards that reuse the *brand frame* of the repo logo system:
a glossy dark-glass panel, a neon-green (``#86efac``) accent with soft glow,
a neon hairline border + top gloss sheen, and the Jost / Space Mono type
pairing. Run::

    uv run --with pillow python cards/make_cards.py

It writes ``img/<name>_card-light.png`` and ``img/<name>_card-dark.png`` for
each card defined in ``CARDS`` at the bottom of the file.

Design notes
------------
The glass panel is dark in *both* themes (exactly as the logo badge is), so
all text drawn *inside* the card is theme-independent. Only the surrounding
canvas and the panel's depth treatment change between variants: a dark
gradient + neon halo for ``dark``, a light gradient + soft drop shadow for
``light``. This mirrors the logo skill's light/dark rules so a README can
auto-switch the pair with a ``<picture>`` element.

Only the ``CARDS`` content table should change to add/edit cards; the
``render`` machinery is the fixed brand frame and is meant to stay put.
"""

import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ==== BRAND FRAME (keep identical to the logo system) =====================
SS = 2                                   # supersample, then downscale LANCZOS

# palette (shared with make_logo.py)
NEON = (134, 239, 172)                   # #86efac signature neon green
NEON_BRIGHT = (190, 250, 213)            # lighter glow core
GLASS_TOP, GLASS_BOT = (34, 37, 46), (9, 10, 13)         # dark-glass gradient
BG_TOP, BG_BOT = (12, 13, 16), (6, 6, 8)                 # dark canvas gradient
LIGHT_TOP, LIGHT_BOT = (251, 251, 253), (231, 232, 236)  # light canvas gradient

# card-specific text colors (drawn on the dark glass, so theme-independent)
INK = (228, 231, 238)                    # body text, off-white
MUTE = (150, 159, 175)                   # metadata / secondary text
PROMPT = (90, 120, 100)                  # dim "$" before the terminal label

# layout (logical px; multiplied by SS internally)
CARD_W = 1180                            # width of the glass panel
MARGIN = 60                              # canvas padding around the panel
RADIUS = 44                              # panel corner radius
PAD_X = 70                               # text inset from panel edge (x)
PAD_TOP = 60                             # text inset from panel top
PAD_BOT = 64                             # text inset from panel bottom

_HERE = os.path.dirname(os.path.abspath(__file__))
FONT_JOST = os.path.join(_HERE, 'fonts', 'Jost[wght].ttf')
FONT_MONO = os.path.join(_HERE, 'fonts', 'SpaceMono-Regular.ttf')


def jost(size, weight=400):
    f = ImageFont.truetype(FONT_JOST, int(size * SS))
    f.set_variation_by_axes([weight])
    return f


def mono(size):
    return ImageFont.truetype(FONT_MONO, int(size * SS))


def vgrad(top, bot, w, h):
    """Vertical gradient image of size ``(w, h)``."""
    g = Image.new('RGB', (1, h))
    for y in range(h):
        t = y / (h - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return g.resize((w, h))


def wrap(draw, text, font, maxw):
    """Greedy word-wrap ``text`` to ``maxw`` pixels for ``font``."""
    lines, cur = [], ''
    for word in text.split():
        trial = word if not cur else cur + ' ' + word
        if cur and draw.textlength(trial, font=font) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def layout(draw, content, maxw):
    """Turn a content list into flat draw ops and a total content height.

    Returns ``(ops, height)`` where each op is ``(dx, dy, text, font, fill)``
    with ``dy`` measured from the top of the content box. A measuring pass is
    enough because every element is plain wrapped text.
    """
    ops, y = [], 0

    def line(text, font, fill, dx=0, lead=1.34):
        nonlocal y
        ops.append((dx, y, text, font, fill))
        y += int(font.size * lead)

    for el in content:
        kind = el[0]
        if kind == 'label':                      # terminal prompt "$ name"
            f = mono(30)
            ops.append((0, y, '$', f, PROMPT))
            ops.append((int(draw.textlength('$  ', font=f)), y, el[1], f, NEON))
            y += int(f.size * 1.7)
        elif kind == 'entry':                    # org / meta / description
            _, org, meta, desc = el
            line(org, jost(34, weight=600), NEON, lead=1.18)
            line(meta, mono(20), MUTE, lead=1.5)
            for ln in wrap(draw, desc, jost(26), maxw):
                line(ln, jost(26), INK)
            y += int(20 * SS)
        elif kind == 'para':
            for ln in wrap(draw, el[1], jost(27), maxw):
                line(ln, jost(27), INK, lead=1.42)
            y += int(10 * SS)
        elif kind == 'spacer':
            y += int(el[1] * SS)

    return ops, y


def render(name, content):
    """Render one card to ``img/{name}_card-light.png`` and ``-dark.png``."""
    cw, margin = CARD_W * SS, MARGIN * SS
    pad_x, pad_top, pad_bot = PAD_X * SS, PAD_TOP * SS, PAD_BOT * SS
    radius = RADIUS * SS

    # --- measure content to size the panel/canvas ---
    probe = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    ops, content_h = layout(probe, content, cw - 2 * pad_x)
    panel_h = pad_top + content_h + pad_bot
    W = cw + 2 * margin
    H = panel_h + 2 * margin
    px0, py0 = margin, margin                     # panel top-left on canvas
    px1, py1 = margin + cw, margin + panel_h
    panel_box = [px0, py0, px1, py1]

    for theme in ('light', 'dark'):
        # --- canvas ---
        if theme == 'light':
            img = vgrad(LIGHT_TOP, LIGHT_BOT, W, H).convert('RGBA')
        else:
            img = vgrad(BG_TOP, BG_BOT, W, H).convert('RGBA')
            pool = Image.new('L', (W, H), 0)      # soft green pool of light
            ImageDraw.Draw(pool).ellipse(
                [W // 2 - cw // 2, py0 - 120 * SS, W // 2 + cw // 2, py1 + 120 * SS],
                fill=46)
            pool = pool.filter(ImageFilter.GaussianBlur(180 * SS))
            img.paste(Image.new('RGBA', (W, H), (26, 40, 32, 255)), (0, 0), pool)

        # --- depth behind the panel: shadow (light) or neon halo (dark) ---
        if theme == 'light':
            shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                [px0, py0 + 14 * SS, px1, py1 + 14 * SS], radius, fill=(20, 24, 30, 85))
            img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(40 * SS)))
        else:
            halo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(halo).rounded_rectangle(panel_box, radius, fill=(*NEON, 80))
            img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(48 * SS)))

        # --- glass body (dark in BOTH themes) ---
        mask = Image.new('L', (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle(panel_box, radius, fill=255)
        img.paste(vgrad(GLASS_TOP, GLASS_BOT, W, H).convert('RGBA'), (0, 0), mask)

        # --- top gloss sheen ---
        gloss = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(gloss).rounded_rectangle(
            [px0, py0, px1, py0 + int(panel_h * 0.40)], radius, fill=(255, 255, 255, 22))
        gloss = gloss.filter(ImageFilter.GaussianBlur(26 * SS))
        img.paste(gloss, (0, 0),
                  Image.composite(gloss.getchannel('A'), Image.new('L', (W, H), 0), mask))

        # --- neon hairline border ---
        ImageDraw.Draw(img).rounded_rectangle(panel_box, radius, outline=(*NEON, 70),
                                              width=2 * SS)

        # --- content text, with a soft neon glow on the neon-colored ops ---
        cx, cy = px0 + pad_x, py0 + pad_top
        glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for dx, dy, text, font, fill in ops:
            if fill == NEON:
                gd.text((cx + dx, cy + dy), text, font=font, fill=(*NEON, 180))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(7 * SS)))

        draw = ImageDraw.Draw(img)
        for dx, dy, text, font, fill in ops:
            draw.text((cx + dx, cy + dy), text, font=font, fill=fill)

        out = img.convert('RGB').resize((W // SS, H // SS), Image.LANCZOS)
        path = os.path.join(_HERE, '..', 'img', f'{name}_card-{theme}.png')
        out.save(path)
        print('saved', os.path.normpath(path))


# ==== CARD CONTENT (edit these to change the cards) =======================
TLDR = [
    ('label', 'tl;dr'),
    ('spacer', 18),
    ('entry', 'Altamira', '2025 - present   ·   Principal AI Scientist',
     'Building agentic AI, AutoML, and physics-informed solutions.'),
    ('entry', 'NIST', '2015 - 2025   ·   Group Leader, Chemical Informatics',
     '10+ years designing numerical algorithms for soft-matter physics and '
     'thermodynamics.'),
    ('entry', 'Princeton University', '2010 - 2015   ·   Ph.D. & M.A., Chemical Engineering',
     'Computational & information science; thesis on the statistical mechanics '
     'of colloidal self-assembly.'),
    ('entry', 'Purdue University', '2006 - 2010   ·   B.S., Chemical Engineering',
     'Minor in Chemistry.'),
]

WHOAMI = [
    ('label', 'whoami'),
    ('spacer', 18),
    ('para', 'I translate AI and HPC tools into solutions by working alongside '
     'subject-matter experts across many disciplines. Since 2010 I have built '
     'AI/ML and data-science products and computer simulations - agentic AI, '
     'AutoML, physics-encoded models (e.g., physics-informed neural networks), '
     'signal-based outlier detection, and generative AI for threat and fraud '
     'detection.'),
    ('spacer', 6),
    ('para', 'At Altamira I create data-accelerated analytic, operations, and '
     'engineering solutions for partners in the intelligence, space, and '
     'defense industries.'),
    ('spacer', 6),
    ('para', 'My career began at NIST, using advanced modeling to make '
     'data-driven discoveries in materials science, nuclear chemistry, '
     'food-fraud detection, and environmental monitoring.'),
]

CARDS = {'tldr': TLDR, 'whoami': WHOAMI}


if __name__ == '__main__':
    for card_name, card_content in CARDS.items():
        render(card_name, card_content)
