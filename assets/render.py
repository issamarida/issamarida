"""Raymarch a sitting orange-tabby SDF and plot it as rotating colour ASCII in an animated SVG.

    python3 assets/render.py > assets/cat.svg
"""
import numpy as np

COLS, ROWS, FRAMES, SECONDS = 56, 38, 48, 6.0
RAMP = " .,:;-=+*x#%@"
FONT, CW, LH = 13, 7.8, 13.0  # font size, char width, line height (px)


def sphere(p, c, r):
    return np.linalg.norm(p - c, axis=-1) - r


def ellipsoid(p, c, r):
    q = (p - c) / r
    k0 = np.linalg.norm(q, axis=-1)
    k1 = np.linalg.norm(q / r, axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def capsule(p, a, b, r):
    pa, ba = p - a, b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)[..., None]
    return np.linalg.norm(pa - ba * h, axis=-1) - r


def cone(p, a, b, r1, r2):
    # linearly tapered capsule: good enough for ears
    pa, ba = p - a, b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    return np.linalg.norm(pa - ba * h[..., None], axis=-1) - (r1 + (r2 - r1) * h)


def smin(a, b, k=0.12):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * h - k * h * (1 - h)


V = lambda *x: np.array(x, dtype=float)


def cat(p):
    d = ellipsoid(p, V(0, 0.45, -0.08), V(0.52, 0.48, 0.55))          # haunches
    d = smin(d, ellipsoid(p, V(0, 0.95, 0.08), V(0.34, 0.5, 0.32)), 0.2)  # chest
    head = ellipsoid(p, V(0, 1.55, 0.18), V(0.42, 0.36, 0.37))
    head = smin(head, sphere(p, V(0, 1.44, 0.48), 0.15), 0.08)          # muzzle
    for s in (-1, 1):
        head = smin(head, cone(p, V(0.2 * s, 1.75, 0.15), V(0.3 * s, 2.1, 0.1), 0.13, 0.015), 0.05)
        head = np.maximum(head, -sphere(p, V(0.15 * s, 1.6, 0.53), 0.06))  # eye sockets
        d = smin(d, capsule(p, V(0.15 * s, 0.9, 0.28), V(0.16 * s, 0.07, 0.38), 0.085), 0.06)  # legs
    d = smin(d, head, 0.1)
    t = np.linspace(-0.4, 1.9, 9)                                       # tail wraps the base
    pts = np.stack([0.62 * np.sin(t), 0.06 + 0.04 * t, -0.08 - 0.62 * np.cos(t)], -1)
    for a, b in zip(pts[:-1], pts[1:]):
        d = smin(d, capsule(p, a, b, 0.07 - 0.008 * np.linalg.norm(a - pts[0])), 0.04)
    return d


TAIL = np.stack([0.62 * np.sin(np.linspace(-0.4, 1.9, 9)), 0.06 + 0.04 * np.linspace(-0.4, 1.9, 9),
                 -0.08 - 0.62 * np.cos(np.linspace(-0.4, 1.9, 9))], -1)
# coat materials: orange, tabby stripe, cream, pink, eye green, pupil
ORANGE, STRIPE, CREAM, PINK, EYE, PUPIL = range(6)


def coat(p):
    """Orange-tabby markings painted onto the surface in the cat's own frame."""
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    phi = np.arctan2(x, z)
    # mackerel stripes ring the body, wobbling around it; rings march down the tail
    m = np.where(np.sin(21 * y + 2.2 * np.sin(3 * phi) + 1.5 * np.cos(phi)) > 0.25, STRIPE, ORANGE)
    head = y > 1.22
    cheek = np.sin(34 * (y - 0.45 * np.abs(x))) > 0.35
    brow = (np.sin(48 * x + np.pi / 2) > 0.3) & (y > 1.68) & (z > 0.05)
    m = np.where(head, np.where((np.abs(x) > 0.24) & cheek | brow, STRIPE, ORANGE), m)
    tr = np.hypot(x, z + 0.08)
    tail = (y < 0.32) & (np.abs(tr - 0.62) < 0.13)
    ang = np.arctan2(x, -(z + 0.08))
    m = np.where(tail, np.where(np.sin(15 * ang) > 0.2, STRIPE, ORANGE), m)
    # cream bib, paws, muzzle and tail tip
    bib = (z > 0.3) & (y > 0.5) & (y < 1.22) & (np.abs(x) < 0.1 + 0.06 * (y - 0.5))
    paws = (y < 0.16) & (z > 0.22) & (np.abs(x) < 0.3)
    muzzle = (np.linalg.norm(p - V(0, 1.41, 0.5), axis=-1) < 0.19) & (y < 1.52)
    tip = np.linalg.norm(p - TAIL[-1], axis=-1) < 0.17
    m = np.where(bib | paws | muzzle | tip, CREAM, m)
    # pink nose and inner ears
    m = np.where(np.linalg.norm(p - V(0, 1.5, 0.6), axis=-1) < 0.06, PINK, m)
    for s in (-1, 1):
        a, b = V(0.2 * s, 1.75, 0.15), V(0.3 * s, 2.1, 0.1)
        h = np.clip(((p - a) @ (b - a)) / ((b - a) @ (b - a)), 0, 1)
        ax = a + (b - a) * h[..., None]
        r = 0.13 + (0.015 - 0.13) * h
        inner = (y > 1.84) & (h > 0.12) & (h < 0.85) & (z - ax[..., 2] > 0.02) & (np.abs(x - ax[..., 0]) < 0.62 * r)
        m = np.where(inner, PINK, m)
        # green eyes with a slit pupil, inside the carved sockets
        e = V(0.15 * s, 1.6, 0.53)
        eye = sphere(p, e, 0.06) > -0.02
        eye &= np.linalg.norm(p - e, axis=-1) < 0.075
        m = np.where(eye, np.where(np.abs(x - e[0]) < 0.016, PUPIL, EYE), m)
    return m


def normal(p, e=1e-3):
    n = np.stack([cat(p + V(*o)) - cat(p - V(*o)) for o in np.eye(3) * e], -1)
    return np.nan_to_num(n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9))


def frame(theta):
    span = 2.4
    xs = (np.arange(COLS) + 0.5 - COLS / 2) / COLS * span
    ys = 1.05 - (np.arange(ROWS) + 0.5 - ROWS / 2) / ROWS * span * (ROWS * LH) / (COLS * CW)
    X, Y = np.meshgrid(xs, ys)
    c, s = np.cos(theta), np.sin(theta)
    tilt = 0.25
    # orthographic camera orbiting the cat, slightly from above
    fwd = V(-s * np.cos(tilt), -np.sin(tilt), -c * np.cos(tilt))
    right = V(c, 0, -s)
    up = np.cross(right, fwd)
    ro = X[..., None] * right + (Y[..., None] - 1.05) * up + V(0, 1.05, 0) - fwd * 4
    t = np.zeros(X.shape)
    hit = np.zeros(X.shape, bool)
    for _ in range(90):
        d = cat(ro + fwd * t[..., None])
        hit |= d < 1e-3
        t = np.where(hit, t, t + d * 0.9)
    p = ro + fwd * t[..., None]
    n = normal(p)
    light = V(-0.5, 0.8, 0.3)
    light = light / np.linalg.norm(light)
    rot_light = V(light[0] * c + light[2] * s, light[1], -light[0] * s + light[2] * c)  # light follows camera
    diff = np.clip(n @ rot_light, 0, 1)
    rim = (1 - np.abs(n @ fwd)) ** 3
    light_ = np.clip(0.15 + 0.85 * diff - 0.35 * rim, 0, 1)
    # dense glyphs where lit so the coat reads as colour; shade picks the tint
    ink = 0.3 + 0.7 * light_
    idx = np.where(hit, 1 + np.nan_to_num(ink * (len(RAMP) - 2)).round().astype(int), 0)
    mat = coat(p)
    shade = np.digitize(light_, [0.22, 0.48])  # 0 shadow, 1 mid, 2 lit
    cls = np.where(mat < PINK, mat * 3 + shade, 9 + mat - PINK)
    return [[(RAMP[i], int(k)) for i, k in zip(r, c)] for r, c in zip(idx, cls)]


# class -> (light theme, dark theme); orange/stripe/cream come shadow, mid, lit
PALETTE = [("#a8460a", "#c4580f"), ("#e06a0c", "#f07a18"), ("#ff8c1a", "#ffa040"),
           ("#4e1e05", "#86380c"), ("#6e2a06", "#a2480f"), ("#8c3a0a", "#b8561a"),
           ("#c08a52", "#c9a57a"), ("#d6a26a", "#e8cba2"), ("#e8b880", "#fbe6c4"),
           ("#e0567f", "#ff8fb4"), ("#3f9e1c", "#8ee04a"), ("#1b1b1b", "#0d0d0d")]


def svg():
    W = int(COLS * CW) + 80
    H = int(ROWS * LH) + 110
    ox, oy = 40, 40
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
           "<style>",
           ":root{--ink:#1b1b1b;--pen:#d9480f;--faint:#1b1b1b33}",
           "@media (prefers-color-scheme:dark){:root{--ink:#e8e6e1;--pen:#ff8a4c;--faint:#e8e6e133}}",
           f"text{{font:{FONT}px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:var(--ink);white-space:pre}}",
           ".m{font-size:10px;letter-spacing:.12em;fill:var(--pen)}",
           ".l{stroke:var(--pen);stroke-width:.8;fill:none}",
           ".h{stroke:var(--faint);stroke-width:.6}",
           "".join(f".c{i}{{fill:{a}}}" for i, (a, _) in enumerate(PALETTE)),
           "@media (prefers-color-scheme:dark){" + "".join(f".c{i}{{fill:{b}}}" for i, (_, b) in enumerate(PALETTE)) + "}",
           f"g.f{{visibility:hidden;animation:k {SECONDS}s step-end infinite}}",
           f"@keyframes k{{0%{{visibility:visible}}{100 / FRAMES:.4f}%,100%{{visibility:hidden}}}}",
           "</style>"]
    # plotter furniture: crop marks, frame, hatched floor shadow, caption
    out.append(f'<rect class="l" x="{ox - 16}" y="{oy - 16}" width="{W - 2 * ox + 32}" height="{H - 2 * oy + 2}" stroke-dasharray="2 4"/>')
    for x, y, dx, dy in [(ox - 24, oy - 24, 1, 1), (W - ox + 24, oy - 24, -1, 1),
                         (ox - 24, H - oy + 10, 1, -1), (W - ox + 24, H - oy + 10, -1, -1)]:
        out.append(f'<path class="l" d="M{x} {y + 14 * dy}V{y}H{x + 14 * dx}"/>')
    cx, cy, rx, ry = W / 2, oy + ROWS * LH * 0.93, COLS * CW * 0.27, 16
    out.append(f'<clipPath id="s"><ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}"/></clipPath><g clip-path="url(#s)">')
    out += [f'<line class="h" x1="{x}" y1="{cy - ry}" x2="{x + 30}" y2="{cy + ry}"/>'
            for x in np.arange(cx - rx - 30, cx + rx, 5)]
    out.append("</g>")
    out.append(f'<ellipse class="l" cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" stroke-dasharray="1 3"/>')
    out.append(f'<text class="m" x="{ox}" y="{H - oy + 4}">silly feline rotating</text>')
    for i in range(FRAMES):
        theta = 2 * np.pi * i / FRAMES
        out.append(f'<g class="f" style="animation-delay:{SECONDS * i / FRAMES:.3f}s">')
        for r, row in enumerate(frame(theta)):
            cells = [i for i, (ch, _) in enumerate(row) if ch != " "]
            if not cells:
                continue
            lead, end = cells[0], cells[-1] + 1
            # one tspan per run of same-coloured glyphs; textLength pins the grid
            runs, prev = [], None
            for ch, k in row[lead:end]:
                ch = ch.replace("&", "&amp;").replace("<", "&lt;")
                if ch != " " and k != prev:
                    runs.append([k, ""])
                    prev = k
                runs[-1][1] += ch
            spans = "".join(f'<tspan class="c{k}">{s}</tspan>' for k, s in runs)
            out.append(f'<text x="{ox + lead * CW:.1f}" y="{oy + (r + 1) * LH:.1f}" '
                       f'textLength="{(end - lead) * CW:.1f}" lengthAdjust="spacingAndGlyphs">{spans}</text>')
        out.append(f'<text class="m" x="{W - ox}" y="{H - oy + 4}" text-anchor="end">θ = {round(np.degrees(theta)):03d}°</text>')
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    print(svg())
