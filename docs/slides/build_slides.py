"""Build the Mini SOC overview slide deck (Phase 9.8).

    python docs/slides/build_slides.py

Writes ``docs/slides/mini-soc-overview.pptx`` (16:9). Re-run after editing the
content below to regenerate; the deck is committed alongside this script so the
slides are reproducible without a PowerPoint GUI.

Requires ``python-pptx`` (see ``requirements-dev.txt``).
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "mini-soc-overview.pptx"
ARCH = ROOT / "docs" / "images" / "architecture.png"
SHOTS = ROOT / "docs" / "images" / "screenshots"

NAVY = RGBColor(0x0F, 0x1B, 0x2E)
ACCENT = RGBColor(0x2F, 0x6F, 0xED)
LIGHT = RGBColor(0xF2, 0xF4, 0xF8)
GREY = RGBColor(0x55, 0x5F, 0x70)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xC0, 0x39, 0x2B)

W = Inches(13.333)
H = Inches(7.5)


def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _rect(slide, x, y, w, h, color):
    from pptx.enum.shapes import MSO_SHAPE

    box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    box.fill.solid()
    box.fill.fore_color.rgb = color
    box.line.fill.background()
    box.shadow.inherit = False
    return box


def _text(slide, x, y, w, h, runs, *, size=18, color=NAVY, bold=False,
          align=PP_ALIGN.LEFT, space_after=6, font="Segoe UI", italic=False):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for item in runs:
        if isinstance(item, str):
            item = (0, item, {})
        level, text, opts = item
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.level = level
        para.alignment = opts.get("align", align)
        para.space_after = Pt(opts.get("space_after", space_after))
        run = para.add_run()
        run.text = text
        f = run.font
        f.size = Pt(opts.get("size", size if level == 0 else size - 3))
        f.bold = opts.get("bold", bold)
        f.color.rgb = opts.get("color", color)
        f.name = font
        if opts.get("mono"):
            f.name = "Consolas"
        if opts.get("italic", italic):
            f.italic = True
    return tb


def title_slide(prs):
    s = _blank(prs)
    _rect(s, 0, 0, W, H, NAVY)
    _rect(s, Inches(0.9), Inches(3.05), Inches(1.6), Inches(0.09), ACCENT)
    _text(s, Inches(0.9), Inches(1.7), Inches(11.6), Inches(1.4),
          ["Mini SOC Platform"], size=48, bold=True, color=WHITE)
    _text(s, Inches(0.9), Inches(3.35), Inches(11.6), Inches(1.2),
          ["Detection, correlation, investigation and response on a single "
           "internet-facing EC2 host"], size=20, color=RGBColor(0xC9, 0xD3, 0xE3))
    _text(s, Inches(0.9), Inches(6.3), Inches(11.6), Inches(0.6),
          ["Live EC2 lab \u00b7 13 detection rules \u00b7 replay + live attack simulation "
           "\u00b7 real nftables containment"], size=13, color=GREY)
    return s


def section(prs, kicker, heading):
    s = _blank(prs)
    _rect(s, 0, 0, Inches(0.28), H, ACCENT)
    _text(s, Inches(0.8), Inches(0.55), Inches(11.8), Inches(0.5),
          [kicker.upper()], size=14, bold=True, color=ACCENT)
    _text(s, Inches(0.8), Inches(1.05), Inches(11.8), Inches(1.0),
          [heading], size=32, bold=True, color=NAVY)
    _rect(s, Inches(0.85), Inches(2.05), Inches(1.3), Inches(0.06), ACCENT)
    return s


def bullets(prs, kicker, heading, items, *, note=None):
    s = section(prs, kicker, heading)
    _text(s, Inches(0.9), Inches(2.35), Inches(11.5), Inches(4.6), items,
          size=19, color=NAVY, space_after=10)
    if note:
        _text(s, Inches(0.9), Inches(6.75), Inches(11.5), Inches(0.6),
              [note], size=12, italic=True, color=GREY)
    return s


def image_slide(prs, kicker, heading, image, *, caption=None):
    from PIL import Image

    s = section(prs, kicker, heading)
    area_w, area_h = Inches(11.6), Inches(4.45)
    with Image.open(image) as im:
        ratio = im.width / im.height
    w = area_w
    h = Emu(int(w / ratio))
    if h > area_h:
        h = area_h
        w = Emu(int(h * ratio))
    x = Inches((13.333 - (w / 914400)) / 2)
    s.shapes.add_picture(str(image), x, Inches(2.35), width=w, height=h)
    if caption:
        _text(s, Inches(0.9), Inches(6.85), Inches(11.5), Inches(0.5),
              [caption], size=12, italic=True, color=GREY)
    return s


def kpi_row(prs, kicker, heading, kpis, items):
    s = section(prs, kicker, heading)
    n = len(kpis)
    gap = Inches(0.3)
    card_w = Emu(int((Inches(11.6) - gap * (n - 1)) / n))
    x = Inches(0.9)
    for value, label in kpis:
        card = _rect(s, x, Inches(2.3), card_w, Inches(1.5), LIGHT)
        _text(s, x, Inches(2.5), card_w, Inches(0.8),
              [(0, str(value), {"size": 40, "bold": True, "color": ACCENT,
                                "align": PP_ALIGN.CENTER})])
        _text(s, x, Inches(3.25), card_w, Inches(0.5),
              [(0, label, {"size": 11, "color": GREY,
                           "align": PP_ALIGN.CENTER})])
        x = Emu(int(x + card_w + gap))
    _text(s, Inches(0.9), Inches(4.15), Inches(11.6), Inches(3.0), items,
          size=18, color=NAVY, space_after=9)
    return s


def build():
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H

    title_slide(prs)

    bullets(prs, "The gap", "Why a SOC platform?", [
        (0, "Individual security tools answer \u201cdid something happen?\u201d "
            "\u2014 a SOC has to answer \u201cwhat is happening, how bad, and what do we do?", {}),
        (0, "One noisy alert is easy to miss; a coherent kill chain is not.", {}),
        (0, "Response must be enforceable, not a dashboard flag.", {}),
        (0, "This project builds the whole loop end to end on infrastructure "
            "we own and can attack safely.", {}),
    ], note="Scope: one internet-facing EC2 instance; attack from a local Kali VM.")

    bullets(prs, "What it is", "A self-contained detection & response pipeline",
            [
                (0, "Collect \u2014 nginx access/error, auth.log, a custom IDS "
                    "(AF_PACKET + nftables), syslog via systemd.", {"bold": True}),
                (0, "Normalize \u2014 one event schema across every source.", {"bold": True}),
                (0, "Detect \u2014 13 rules (pattern + threshold) over a rolling window.", {"bold": True}),
                (0, "Correlate \u2014 alerts from one source become a chain, then an incident.", {"bold": True}),
                (0, "Respond \u2014 block IP via a sudo-confined helper into nftables.", {"bold": True}),
                (0, "Operate \u2014 a React dashboard: overview, alerts, chains, "
                    "incidents, events, rules, reports, users.", {"bold": True}),
            ])

    if ARCH.exists():
        image_slide(prs, "Architecture", "One host, two faces: the target and the SOC",
                    ARCH, caption="Full diagram: docs/images/architecture.png")

    bullets(prs, "Detection rules", "13 rules across three families",
            [
                (0, "Web (8): SQLi, LFI/path traversal, command injection, XSS, "
                    "scanner User-Agent, login brute force, HTTP flood, plus the "
                    "shared web parser.", {"size": 18}),
                (0, "Auth (2): SSH brute force (\u226510 fails / 5 min) and "
                    "login-success-after-brute-force (CRITICAL).", {"size": 18}),
                (0, "Network/IDS (3): port scan (\u226520 ports / 60 s), IDS signature, "
                    "unusual outbound, unusual DNS (over-long labels).", {"size": 18}),
                (0, "Every rule: a YAML definition, a severity, a MITRE mapping, and "
                    "a page in the playbook.", {"size": 18}),
            ], note="Replay suite drives all 13 rules through the same engine: 13/13 pass.")

    bullets(prs, "The lab", "How it is tested without a real victim",
            [
                (0, "Single Ubuntu 24.04 t3.small EC2 instance, Elastic IP, "
                    "Security Group locked to 22 / 80 / 443-from-analyst.", {"size": 18}),
                (0, "DVWA (deliberately vulnerable) serves as the web target on :80.", {"size": 18}),
                (0, "attack-sim/ scripts run from a local Kali VM: nmap, hydra, "
                    "sqlmap, Nikto, and the host-originated outbound/DNS sims.", {"size": 18}),
                (0, "Rules of engagement: only our own instance, brief and "
                    "non-sustained; HTTP flood is replay-only.", {"size": 18}),
            ])

    bullets(prs, "Demo story", "One attacker, 13 alerts, 45 seconds",
            [
                (0, "Recon \u2014 NET-PORTSCAN-001, IDS-SIG-001.", {"size": 18}),
                (0, "Web exploitation \u2014 WEB-SQLI / XSS / CMD / LFI / SCAN / BF / FLOOD.", {"size": 18}),
                (0, "Credential attack \u2014 SSH-BF-001 \u2192 SSH-SUCCESS-001 (CRITICAL).", {"size": 18}),
                (0, "Post-compromise \u2014 NET-OUTBOUND-001, DNS-ANOMALY-001.", {"size": 18}),
                (0, "All 13 from one src_ip \u2192 chain 1 \u2192 incident INC-2026-0001.", {"size": 18}),
            ], note="Timeline is from the real detection engine (seed_demo.py).")

    bullets(prs, "Correlation", "13 alerts are one story, not 13 tickets",
            [
                (0, "Rules key on src_ip + a time window; alerts from one source "
                    "inside the window share a chain_id.", {"size": 18}),
                (0, "The dashboard surfaces the chain timeline and offers "
                    "promote-to-incident.", {"size": 18}),
                (0, "Deduplication: a repeated pattern updates the same alert's "
                    "count/last_seen instead of creating a new one.", {"size": 18}),
                (0, "The incident is the unit of response \u2014 notes, actions, "
                    "status history (\u2192 contained \u2192 resolved \u2192 closed).", {"size": 18}),
            ])

    bullets(prs, "Response", "Containment is real, not a dashboard flag",
            [
                (0, "block IP \u2192 POST /api/actions/{id}/execute (confirm: true) \u2192 "
                    "sudo /usr/local/sbin/soc-block add <ipv4> [timeout]", {"mono": True, "size": 15}),
                (0, "The helper re-validates the address and refuses allow-listed "
                    "or non-IPv4 targets \u2014 even when called directly.", {"size": 18}),
                (0, "Result lands in nftables: inet filter blocklist (default 3600 s).", {"size": 18}),
                (0, "Proof: nft list set inet filter blocklist; the attacker's "
                    "connection now times out.", {"mono": True, "size": 15}),
                (0, "sudoers grants the backend nothing but that one script.", {"size": 18}),
            ])

    bullets(prs, "False positives", "A second, benign source must stay quiet",
            [
                (0, "A phone hotspot provides a genuinely different public IP.", {"size": 18}),
                (0, "Benign page loads from it raise nothing (sub-threshold); "
                    "exploitation-shaped traffic from the attacker raises 13.", {"size": 18}),
                (0, "The rules key on payload and volume \u2014 not on traffic existing.", {"size": 18}),
                (0, "Stray benign hits are triaged FALSE POSITIVE and the source "
                    "is allow-listed.", {"size": 18}),
            ], note="See docs/testing/second-source-ip.md and reports/incident-reports.md (0002).")

    for name, heading in (
        ("01-overview.png", "Overview \u2014 live posture"),
        ("03-alert-detail.png", "Alert detail \u2014 evidence + linked events"),
        ("07-incident-detail.png", "Incident \u2014 timeline, notes, response actions"),
    ):
        img = SHOTS / name
        if img.exists():
            image_slide(prs, "Dashboard", heading, img)

    kpi_row(prs, "Quality", "What is verified, and how",
            [("13/13", "rules fire in replay"),
             ("116", "python tests passed"),
             ("18", "frontend tests"),
             ("0", "open High security findings")],
            [
                (0, "Detection replay: 13/13 rules, dedupe and chain formation.", {"size": 18}),
                (0, "pytest across ids / backend / collector / agents; vitest + build for the frontend.", {"size": 18}),
                (0, "CI (.github/workflows/ci.yml) runs all of it on every push.", {"size": 18}),
                (0, "Security review: injection, JWT tampering, RBAC, upload, exposed ports, helper injection.", {"size": 18}),
            ], )

    bullets(prs, "Deliverables", "What ships",
            [
                (0, "Code \u2014 collector, detection engine, IDS, backend API, React dashboard, agents.", {"size": 18}),
                (0, "Rules \u2014 13 YAML definitions + the response playbook.", {"size": 18}),
                (0, "Infra \u2014 deploy/install.sh (one command) + the EC2 host-config snapshot.", {"size": 18}),
                (0, "Docs \u2014 lab setup, architecture, contracts, analyst user guide (with screenshots), "
                    "test plan, results, security review, incident reports.", {"size": 18}),
                (0, "Attack simulation + replay suite for reproducible testing.", {"size": 18}),
            ])

    bullets(prs, "Wrap-up", "Lessons and next steps",
            [
                (0, "Detection is easy to demo; correlation is what makes it useful.", {"size": 18}),
                (0, "Containment must be enforceable and auditable \u2014 a real firewall action.", {"size": 18}),
                (0, "Low false positives are a design goal, tested with a second benign source.", {"size": 18}),
                (0, "Next: key-only SSH, alerting integrations (email/Slack), and a "
                    "second host to exercise cross-host correlation.", {"size": 18}),
            ])

    return prs


def main():
    prs = build()
    prs.save(str(OUT))
    print(f"wrote {OUT}  ({len(prs.slides._sldIdLst)} slides)")


if __name__ == "__main__":
    main()
