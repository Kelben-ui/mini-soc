#!/usr/bin/env python3
"""Render docs/images/architecture.png.

Self-contained: standard library only (``zlib`` + ``struct`` for the PNG and a
small built-in 5x7 bitmap font for the text). No Pillow / Graphviz / draw.io
CLI needed. Re-run after editing:

    python docs/images/render_architecture.py

The matching editable source is ``architecture.drawio`` (same boxes); use
draw.io if you want a GUI and export a hand-drawn variant.
"""

import math
import os
import struct
import zlib

W, H = 1500, 1040

BG = (255, 255, 255)
INK = (30, 30, 30)
GREY = (140, 140, 140)
AMBER = (250, 240, 214)
ROSE = (248, 222, 226)
BLUE = (216, 230, 248)
GREEN = (216, 240, 218)
VIO = (232, 224, 248)
MINT = (218, 244, 242)

FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".###.", "#...#", "#....", ".###.", "....#", "#...#", ".###."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#...#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": (".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "#....", "####.", "....#", "#...#", ".###."),
    "6": (".###.", "#...#", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "#...#", ".###."),
    ":": (".....", "..#..", "..#..", ".....", "..#..", "..#..", "....."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    "_": (".....", ".....", ".....", ".....", ".....", ".....", "#####"),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
}

buf = bytearray(W * H * 3)


def px(x, y, c):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i], buf[i + 1], buf[i + 2] = c[0], c[1], c[2]


def fill(x, y, w, h, c):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            px(xx, yy, c)


def rect(x, y, w, h, fillc=None, border=INK, t=2):
    if fillc is not None:
        fill(x, y, w, h, fillc)
    if border is not None:
        fill(x, y, w, t, border)
        fill(x, y + h - t, w, t, border)
        fill(x, y, t, h, border)
        fill(x + w - t, y, t, h, border)


def line(x0, y0, x1, y1, c=INK, t=2):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        for ox in range(t):
            for oy in range(t):
                px(x0 + ox, y0 + oy, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def arrow(x0, y0, x1, y1, c=INK, t=2):
    line(x0, y0, x1, y1, c, t)
    ang = math.atan2(y1 - y0, x1 - x0)
    for da in (2.6, -2.6):
        a = ang + da
        line(x1, y1, int(x1 + 15 * math.cos(a)), int(y1 + 15 * math.sin(a)), c, t)


def text(x, y, s, scale=2, c=INK):
    cx = x
    for ch in s.upper():
        g = FONT.get(ch, FONT[" "])
        for r in range(7):
            for col in range(5):
                if g[r][col] == "#":
                    for oy in range(scale):
                        for ox in range(scale):
                            px(cx + col * scale + ox, y + r * scale + oy, c)
        cx += 6 * scale
    return cx


def text_w(s, scale=2):
    return len(s) * 6 * scale


def wrap(s, maxpx, scale=2):
    words, lines, cur = s.upper().split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_w(trial, scale) <= maxpx or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def box(x, y, w, h, title, sub, color):
    rect(x, y, w, h, fillc=color, border=INK, t=2)
    ty = y + 9
    for ln in wrap(title, w - 16, 2):
        text(x + 10, ty, ln, 2)
        ty += 18
    if sub:
        ty += 3
        for ln in wrap(sub, w - 16, 1):
            text(x + 10, ty, ln, 1, GREY)
            ty += 11
    return (x, y, w, h)


def ctr(b):
    return (b[0] + b[2] // 2, b[1] + b[3] // 2)


def border_point(b, tx, ty):
    x, y, w, h = b
    cx, cy = x + w / 2, y + h / 2
    dx, dy = tx - cx, ty - cy
    ts = []
    if dx:
        ts.append((x - cx) / dx if dx < 0 else ((x + w) - cx) / dx)
    if dy:
        ts.append((y - cy) / dy if dy < 0 else ((y + h) - cy) / dy)
    t = min((v for v in ts if v >= 0), default=0)
    return int(cx + dx * t), int(cy + dy * t)


def link(a, b, c=INK):
    ax, ay = ctr(a)
    bx, by = ctr(b)
    x0, y0 = border_point(a, bx, by)
    x1, y1 = border_point(b, ax, ay)
    arrow(x0, y0, x1, y1, c)


# --- drawing ----------------------------------------------------------------
fill(0, 0, W, H, BG)
text(40, 20, "MINI SOC - SYSTEM ARCHITECTURE", 3, INK)
text(40, 60, "one EC2 instance; detection and response are local", 1, GREY)

text(40, 110, "INTERNET / ATTACKERS", 2, INK)
kali = box(40, 148, 300, 72, "KALI VM", "primary source", ROSE)
hot = box(40, 240, 300, 72, "PHONE HOTSPOT", "second source (fp demo)", ROSE)
scan = box(40, 332, 300, 72, "INTERNET", "background scanners", ROSE)

rect(372, 96, 1078, 900, fillc=None, border=GREY, t=2)
text(392, 110, "AWS EC2 INSTANCE - MINI-SOC (UBUNTU 24.04, T3.SMALL)", 1, GREY)

sg = box(400, 150, 300, 76, "SECURITY GROUP", "22/80 world, 443 analyst", AMBER)
nft = box(400, 258, 300, 96, "NFTABLES", "SOC_DROP / SOC_ACCEPT / SOC_OUT", AMBER)

dvwa = box(760, 150, 330, 76, "NGINX :80 DVWA", "web target", BLUE)
sshd = box(760, 258, 330, 76, "SSHD :22", "ssh target (testuser)", BLUE)
dash = box(760, 366, 330, 76, "NGINX :443 DASHBOARD", "spa + /api, analyst only", BLUE)
anly = box(1150, 150, 280, 120, "ANALYST BROWSER", "https 443", (240, 240, 240))

ids = box(760, 486, 330, 76, "IDS/IPS", "live_ids_ips.py: journal + dns", MINT)
agent = box(760, 594, 330, 76, "LOG AGENT", "tails files, spools", MINT)
coll = box(760, 702, 330, 76, "COLLECTOR", "parsers to events", MINT)
det = box(1150, 702, 280, 76, "DETECTION ENGINE", "rules to alerts", MINT)

api = box(400, 470, 300, 76, "BACKEND API", "fastapi :8000", GREEN)
mariadb = box(400, 578, 300, 76, "MARIADB", "dvwa data", VIO)
pg = box(400, 686, 300, 76, "POSTGRESQL 16", "events, alerts, incidents", VIO)

# edges
for b in (kali, hot, scan):
    arrow(b[0] + b[2], b[1] + b[3] // 2, 400, 188)
link(sg, nft)
link(nft, dvwa)
link(nft, sshd)
link(nft, dash)
link(dash, api)
link(anly, dash)
link(nft, ids)
link(ids, agent)
link(agent, coll)
link(coll, det)
link(det, pg)
link(api, pg)
link(dvwa, mariadb)

# legend
rect(40, 900, 22, 22, fillc=ROSE, border=INK, t=2)
text(72, 904, "external source", 1)
rect(320, 900, 22, 22, fillc=AMBER, border=INK, t=2)
text(352, 904, "perimeter / firewall", 1)
rect(620, 900, 22, 22, fillc=BLUE, border=INK, t=2)
text(652, 904, "exposed service", 1)
rect(900, 900, 22, 22, fillc=MINT, border=INK, t=2)
text(932, 904, "soc process", 1)
rect(1120, 900, 22, 22, fillc=VIO, border=INK, t=2)
text(1152, 904, "data store", 1)

text(40, 948, "NGINX :80 + SSHD :22 are world-open (security group); :443 dashboard is analyst-only.", 1, GREY)
text(40, 964, "nftables logs SOC_DROP / SOC_ACCEPT / SOC_OUT; IDS reads the journal + raw DNS.", 1, GREY)


def write_png(path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture.png")
    write_png(out)
    print("wrote", out)
