"""Genera los SVG del perfil: banner (retrato dithered + vim profile.yml) y radares.

Uso:  python assets/source/gen.py
Requiere: pillow, numpy. El retrato sale de assets/source/portrait.png
(PNG con fondo transparente o negro; se recomienda foto frontal, buena luz).
"""
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# ---------------------------------------------------------------- contenido
YAML = [
    ("profile:", None, 0),
    ("name", "Mateo Chancusi", 1),
    ("role", "Software Engineer", 1),
    ("origin", "Quito, Ecuador", 1),
    ("focus", "Full Stack · Microservicios · APIs", 1),
    ("status", "Construyendo · Integrando · Desplegando", 1),
    ("education", "Ingeniería en Sistemas", 1),
    ("stack:", None, 0),
    ("frontend", "React · Angular · TypeScript · Tailwind", 1),
    ("backend", "Spring Boot · .NET · FastAPI · Node.js", 1),
    ("languages", "Java · Python · Go · C# · Kotlin", 1),
    ("data", "PostgreSQL · MySQL · MongoDB · Oracle", 1),
    ("devops", "Docker · AWS · GitHub Actions · Terraform", 1),
    ("contact:", None, 0),
    ("linkedin", "/in/kevin-mateo-chancusi-montoya", 1),
    ("github", "kevinseya", 1),
    ("timezone", "UTC-5 · Quito", 1),
]

# Autoevaluación (0-100) — ajústalo a gusto
SKILLS = {
    "Backend": 90, "Frontend": 85, "Microservicios": 85,
    "Bases de datos": 80, "DevOps / Cloud": 65, "Testing": 60,
}
# Repos públicos (no forks) por lenguaje principal
LANGS = {"Python": 15, "Java": 11, "JavaScript": 11, "Go": 5, "C#": 5, "Kotlin": 4}

THEMES = {
    "dark": dict(
        bg="#0A0F1E", frame="#0D1628", panel="#101B30", line="#25344C",
        muted="#8291A8", text="#E6EDF3", key="#7AA2F7", accent="#FFD166",
        accent2="#EF476F", dot="#FFD166", badge_text="#0A0F1E",
    ),
    "light": dict(
        bg="#FFFFFF", frame="#F6F8FA", panel="#FFFFFF", line="#D0D7DE",
        muted="#57606A", text="#1F2328", key="#0550AE", accent="#B7791F",
        accent2="#CF222E", dot="#1F2328", badge_text="#FFFFFF",
    ),
}


# ---------------------------------------------------------------- capas (retrato + logos)
from PIL import ImageChops, ImageDraw, ImageFilter

BOX_W, BOX_H = 300, 340


def fs_dither(a):
    """Floyd–Steinberg serpentina sobre una matriz 0..1 → puntos (x, y)."""
    a = a.copy()
    h, w = a.shape
    out = np.zeros_like(a, dtype=bool)
    for y in range(h):
        rng = range(w) if y % 2 == 0 else range(w - 1, -1, -1)
        d = 1 if y % 2 == 0 else -1
        for x in rng:
            old = a[y, x]
            new = 1.0 if old > 0.5 else 0.0
            out[y, x] = new > 0
            err = old - new
            if 0 <= x + d < w:
                a[y, x + d] += err * 7 / 16
            if y + 1 < h:
                if 0 <= x - d < w:
                    a[y + 1, x - d] += err * 3 / 16
                a[y + 1, x] += err * 5 / 16
                if 0 <= x + d < w:
                    a[y + 1, x + d] += err * 1 / 16
    return out


def portrait_points(invert=False):
    im = Image.open(SRC / "portrait.png").convert("RGBA")
    alpha = im.getchannel("A")
    # desvanece los bordes donde la foto está recortada (abajo y derecha)
    w0, h0 = im.size
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rectangle((-w0, h0 * 0.08, w0 * 0.93, h0 * 0.84), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(w0 * 0.06))
    alpha = ImageChops.multiply(alpha, m)
    gray = ImageOps.autocontrast(im.convert("L"), cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.25)
    if invert:  # tema claro: los puntos marcan las zonas oscuras
        gray = ImageOps.invert(gray)
    gray = Image.composite(gray, Image.new("L", im.size, 0), alpha)
    gray.thumbnail((BOX_W, BOX_H), Image.LANCZOS)
    a = (np.asarray(gray, dtype=np.float32) / 255.0) ** 1.35
    out = fs_dither(a)
    h, w = a.shape
    ox, oy = (BOX_W - w) // 2, BOX_H - h
    return [(x + ox, y + oy) for y, x in zip(*np.nonzero(out))]


def logo_points(name):
    """Silueta blanca sobre negro (300x340) → puntos con degradado diagonal."""
    m = np.asarray(Image.open(SRC / f"{name}.png").convert("L"), dtype=np.float32) / 255.0
    yy, xx = np.mgrid[0:BOX_H, 0:BOX_W]
    grad = 0.30 + 0.32 * ((xx / BOX_W + yy / BOX_H) / 2)
    out = fs_dither(m * grad)
    return [(x, y) for y, x in zip(*np.nonzero(out))]


def runs(points):
    """Agrupa puntos contiguos en la misma fila en segmentos h<n>."""
    rows = {}
    for x, y in points:
        rows.setdefault(y, []).append(x)
    segs = []
    for y, xs in rows.items():
        xs.sort()
        start = prev = xs[0]
        for x in xs[1:]:
            if x == prev + 1:
                prev = x
                continue
            segs.append((start, y, prev - start + 1))
            start = prev = x
        segs.append((start, y, prev - start + 1))
    return segs


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Ciclo: retrato → Java → TypeScript → retrato. Fracciones del ciclo (entra, sale).
CYCLE = 15  # segundos
WINDOWS = [(0.92, 0.28), (0.30, 0.60), (0.62, 0.90)]
MORPH = 0.05  # duración de cada transición (fracción del ciclo)


def banner(theme, layers):
    t = THEMES[theme]
    W, H = 1180, 610
    px, py = 94, 150  # origen del área de puntos dentro del panel izquierdo
    random.seed(7)
    groups = 24
    anim = f'begin="1s" dur="{CYCLE}s" repeatCount="indefinite"'

    g_parts, labels = [], []
    for li, ((label, points), (t_in, t_out)) in enumerate(zip(layers, WINDOWS)):
        buckets = [[] for _ in range(groups)]
        for seg in runs(points):
            buckets[random.randrange(groups)].append(seg)
        for segs in buckets:
            if not segs:
                continue
            j = random.uniform(0, 0.02)  # desfase por grupo: efecto orgánico
            ang = random.uniform(0, 2 * math.pi)
            dist = random.uniform(25, 70)
            s_ = f"{dist * math.cos(ang):.1f} {dist * math.sin(ang):.1f}"
            i1, i2 = t_in + j, t_in + j + MORPH
            o1, o2 = t_out + j, t_out + j + MORPH
            if li == 0:  # visible al inicio; sale y vuelve a entrar al final del ciclo
                kt = f"0;{o1:.3f};{o2:.3f};{i1:.3f};{i2:.3f};1"
                tv, ov, base = f"0 0;0 0;{s_};{s_};0 0;0 0", "1;1;0;0;1;1", "1"
            else:
                kt = f"0;{i1:.3f};{i2:.3f};{o1:.3f};{o2:.3f};1"
                tv, ov, base = f"{s_};{s_};0 0;0 0;{s_};{s_}", "0;0;1;1;0;0", "0"
            d = "".join(f"M{x + px} {y + py}h{n}" for x, y, n in segs)
            g_parts.append(
                f'<g opacity="{base}"><path d="{d}" stroke="{t["dot"]}" stroke-width="1" opacity=".92"/>'
                f'<animateTransform attributeName="transform" type="translate" {anim} keyTimes="{kt}" values="{tv}"/>'
                f'<animate attributeName="opacity" {anim} keyTimes="{kt}" values="{ov}"/></g>'
            )
        # etiqueta del modo actual en la cabecera del panel
        if li == 0:
            kt, ov, base = f"0;{t_out:.3f};{t_out + 0.01:.3f};{t_in + 0.03:.3f};{t_in + 0.04:.3f};1", "1;1;0;0;1;1", "1"
        else:
            kt, ov, base = f"0;{t_in + 0.03:.3f};{t_in + 0.04:.3f};{t_out:.3f};{t_out + 0.01:.3f};1", "0;0;1;1;0;0", "0"
        labels.append(
            f'<text x="438" y="111" text-anchor="end" fill="{t["muted"]}" font-size="11" opacity="{base}">'
            f'MODE: <tspan fill="{t["accent"]}">{label}</tspan> / 1-BIT'
            f'<animate attributeName="opacity" {anim} keyTimes="{kt}" values="{ov}"/></text>'
        )
    points = layers[0][1]

    # panel yaml
    lines = []
    y0 = 158
    for i, (k, v, ind) in enumerate(YAML):
        y = y0 + i * 21
        n = f'<text x="512" y="{y}" text-anchor="end" fill="{t["muted"]}" font-size="11" opacity=".7">{i + 1}</text>'
        x = 530 + ind * 18
        if v is None:
            body = f'<text x="{x}" y="{y}" fill="{t["text"]}" font-size="13" font-weight="700">{esc(k)}</text>'
        else:
            body = (f'<text x="{x}" y="{y}" font-size="13"><tspan fill="{t["key"]}">{esc(k)}:</tspan>'
                    f'<tspan fill="{t["text"]}"> {esc(v)}</tspan></text>')
        lines.append(
            f'<g>{n}{body}</g>'
        )
    last_y = y0 + (len(YAML) - 1) * 21
    k, v, ind = YAML[-1]
    cx = 530 + ind * 18 + (len(k) + len(v) + 3) * 7.8
    cursor = (f'<rect x="{cx:.0f}" y="{last_y - 11}" width="8" height="15" fill="{t["accent"]}">'
              f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" repeatCount="indefinite"/></rect>')

    n_pts = len(points)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
<title id="title">Mateo Chancusi — Software Engineer</title>
<desc id="desc">Perfil animado estilo terminal con retrato dithered y profile.yml.</desc>
<defs>
<filter id="shadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#02050B" flood-opacity="{'.28' if theme == 'dark' else '.08'}"/></filter>
<clipPath id="vc"><rect x="49" y="124" width="390" height="414" rx="3"/></clipPath>
<linearGradient id="scan" x1="0" x2="0" y1="0" y2="1"><stop stop-color="{t["accent"]}" stop-opacity="0"/><stop offset="1" stop-color="{t["accent"]}" stop-opacity=".12"/></linearGradient>
</defs>
<g font-family="{MONO}">
<rect width="{W}" height="{H}" rx="18" fill="{t["bg"]}"/>
<rect x="13" y="13" width="1154" height="584" rx="13" fill="{t["frame"]}" stroke="{t["line"]}" filter="url(#shadow)"/>
<path d="M13 62H1167" stroke="{t["line"]}"/>
<circle cx="38" cy="38" r="6" fill="#FF5F57"/><circle cx="59" cy="38" r="6" fill="#FEBC2E"/><circle cx="80" cy="38" r="6" fill="#28C840"/>
<text x="590" y="43" text-anchor="middle" fill="{t["muted"]}" font-size="13">vim profile.yml</text>

<rect x="35" y="88" width="418" height="472" rx="6" fill="{t["panel"]}" stroke="{t["line"]}"/>
<path d="M35 124H453" stroke="{t["line"]}"/>
<text x="49" y="111" fill="{t["text"]}" font-size="13" font-weight="700" letter-spacing="1.2">VISUAL.MAP</text>
{"".join(labels)}
<path d="M49 141h12M49 141v12M439 141h-12M439 141v12M49 539h12M49 539v-12M439 539h-12M439 539v-12" fill="none" stroke="{t["accent"]}" opacity=".6"/>
<g clip-path="url(#vc)" shape-rendering="crispEdges">
{"".join(g_parts)}
<rect x="49" y="100" width="390" height="24" fill="url(#scan)"><animate attributeName="y" values="100;540" dur="4.5s" repeatCount="indefinite"/></rect>
</g>
<text x="58" y="552" fill="{t["muted"]}" font-size="10">PTS {n_pts} · FS/SERPENTINE · 3 LAYERS</text>

<rect x="477" y="88" width="668" height="472" rx="6" fill="{t["panel"]}" stroke="{t["line"]}"/>
<path d="M477 124H1145" stroke="{t["line"]}"/>
<text x="495" y="111" font-size="13" font-weight="700"><tspan fill="{t["text"]}">profile.yml</tspan><tspan fill="{t["muted"]}" font-size="10" font-weight="400"> [YAML]</tspan></text>
<rect x="1010" y="98" width="120" height="20" rx="10" fill="{t["line"]}"/>
<text x="1070" y="112" text-anchor="middle" fill="{t["text"]}" font-size="12" font-weight="700">@kevinseya</text>
{"".join(lines)}
{cursor}
<path d="M477 522H1145" stroke="{t["line"]}"/>
<rect x="487" y="530" width="62" height="18" rx="3" fill="{t["accent"]}"/>
<text x="518" y="543" text-anchor="middle" fill="{t["badge_text"]}" font-size="10" font-weight="700">NORMAL</text>
<text x="562" y="543" fill="{t["text"]}" font-size="11" font-weight="700">profile.yml</text>
<text x="760" y="543" fill="{t["muted"]}" font-size="10">[utf-8]</text>
<text x="1132" y="543" text-anchor="end" fill="{t["muted"]}" font-size="10">{len(YAML)}L · 100% · UTC-5</text>
</g>
</svg>'''
    (ROOT / f"banner-{theme}.svg").write_text(svg, encoding="utf-8")


# ---------------------------------------------------------------- radares
def radar(theme, data, name, title, max_v=None, width=440):
    t = THEMES[theme]
    H = 330
    cx, cy, R = width / 2, 176, 100
    labels = list(data)
    vals = list(data.values())
    mv = max_v or max(vals)
    n = len(labels)
    pt = lambda i, r: (cx + r * math.sin(2 * math.pi * i / n), cy - r * math.cos(2 * math.pi * i / n))
    rings = "".join(
        f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, R * k / 4) for i in range(n)))}" fill="none" stroke="{t["line"]}"/>'
        for k in range(1, 5))
    spokes = "".join(f'<line x1="{cx}" y1="{cy}" x2="{pt(i, R)[0]:.1f}" y2="{pt(i, R)[1]:.1f}" stroke="{t["line"]}"/>' for i in range(n))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, R * v / mv) for i, v in enumerate(vals)))
    dots = "".join(f'<circle cx="{pt(i, R * v / mv)[0]:.1f}" cy="{pt(i, R * v / mv)[1]:.1f}" r="3.5" fill="{t["accent"]}"/>' for i, v in enumerate(vals))
    lab = ""
    for i, (l, v) in enumerate(data.items()):
        x, y = pt(i, R + 22)
        anchor = "middle" if abs(x - cx) < 5 else ("start" if x > cx else "end")
        suffix = f" {v}" if max_v is None else ""
        lab += f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="{anchor}" fill="{t["text"]}" font-size="12">{esc(l)}<tspan fill="{t["muted"]}">{suffix}</tspan></text>'
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{H}" viewBox="0 0 {width} {H}" role="img"><title>{esc(title)}</title>
<g font-family="{MONO}">
<rect x="1" y="1" width="{width - 2}" height="{H - 2}" rx="12" fill="{t["frame"]}" stroke="{t["line"]}"/>
<text x="18" y="30" fill="{t["accent"]}" font-size="13" font-weight="700">{esc(title)}</text>
{rings}{spokes}
<polygon points="{poly}" fill="{t["accent"]}" fill-opacity=".18" stroke="{t["accent"]}" stroke-width="2"><animate attributeName="fill-opacity" values=".1;.3;.1" dur="4s" repeatCount="indefinite"/></polygon>
{dots}{lab}
</g></svg>'''
    (ROOT / f"{name}-{theme}.svg").write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    logos = [("JAVA", logo_points("java")), ("TYPESCRIPT", logo_points("typescript"))]
    for th in THEMES:
        layers = [("PORTRAIT", portrait_points(invert=th == "light"))] + logos
        banner(th, layers)
        radar(th, SKILLS, "radar", "skill_radar", max_v=100)
        radar(th, LANGS, "radar-langs", "repos_por_lenguaje")
    print("ok")
