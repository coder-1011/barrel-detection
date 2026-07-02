#!/usr/bin/env python3
"""
Build the methods-comparison EVALUATION deck (.pptx).

Sparse "talking" deck: title + 9 content slides, every result slide shows the
actual figure/table (the student narrates). Reuses the look & feel of
bilfinger_slides/build_deck.py (blank layout, accent band, footer, pic_fit).

Run AFTER:
  - researchwrite/make_eval_figures.py            (pipeline_flow.png, station1_pile_raw.png)
  - the synthetic noise-sweep job                 (synth_noise_sweep.png + eval/*.csv sweep rows)

Slide 5's synthetic table is read straight from eval/<method>.csv (sweep_* rows),
so its numbers are the real measured values, never hand-typed.

Output: researchwrite/evaluation_presentation.pptx
"""
import csv
import glob
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

HERE = os.path.dirname(os.path.abspath(__file__))
MASTERS = os.path.abspath(os.path.join(HERE, ".."))
ASSETS = os.path.join(HERE, "presentation_assets")
BILF = os.path.join(HERE, "bilfinger_slides", "assets")
OUT = os.path.join(HERE, "evaluation_presentation.pptx")

# ---- title-slide metadata (brief: don't guess — left as placeholders) -------
THESIS_TITLE = "Detection and Robotic Manipulation of Partially Occluded Object(s)"
PROBLEM_LINE = ("Detecting partially occluded cylindrical objects for robotic "
                "manipulation: a multi-method comparison in 3D point clouds")
PRESENTER = "[FILL: presenter]"
SUPERVISOR = "[FILL: supervisor]"
DATELINE = "[FILL: date]"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]

DARK = RGBColor(0x1F, 0x2D, 0x3D)
ACCENT = RGBColor(0x0B, 0x5C, 0x8A)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
AMBER = RGBColor(0xB7, 0x6E, 0x00)
RED = RGBColor(0xB0, 0x2A, 0x2A)
GREY = RGBColor(0x55, 0x55, 0x55)
LIGHT = RGBColor(0xF2, 0xF5, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


# ----------------------------------------------------------------- helpers
def slide():
    return prs.slides.add_slide(BLANK)


def box(s, l, t, w, h):
    tb = s.shapes.add_textbox(l, t, w, h)
    tb.text_frame.word_wrap = True
    return tb.text_frame


def setp(p, text, size=18, bold=False, color=DARK, align=PP_ALIGN.LEFT,
         space_after=6, level=0, italic=False):
    p.text = text
    p.alignment = align
    p.level = level
    p.space_after = Pt(space_after)
    for r in p.runs:
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = color
        r.font.name = "Calibri"


def add_para(tf, *a, **k):
    p = tf.add_paragraph()
    setp(p, *a, **k)
    return p


def bullet(tf, text, size=15, color=DARK, level=0, bold=False, first=False,
           space_after=6, italic=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    pre = "• " if level == 0 else "– "
    setp(p, pre + text, size=size, bold=bold, color=color, level=level,
         space_after=space_after, italic=italic)
    return p


def band(s, color=ACCENT, h=Inches(1.15)):
    sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, h)
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.fill.background(); sh.shadow.inherit = False
    return sh


def title_band(s, title, sub=None):
    band(s)
    tf = box(s, Inches(0.5), Inches(0.12), Inches(12.3), Inches(0.95))
    setp(tf.paragraphs[0], title, size=27, bold=True, color=WHITE)
    if sub:
        add_para(tf, sub, size=14, color=RGBColor(0xD6, 0xE6, 0xF0))


def footer(s, n):
    tf = box(s, Inches(0.4), Inches(7.05), Inches(12.0), Inches(0.35))
    setp(tf.paragraphs[0], THESIS_TITLE, size=9, color=GREY)
    tn = box(s, Inches(12.6), Inches(7.05), Inches(0.6), Inches(0.35))
    setp(tn.paragraphs[0], str(n), size=10, color=GREY, align=PP_ALIGN.RIGHT)


def pic_fit(s, path, l, t, w, h):
    from PIL import Image
    iw, ih = Image.open(path).size
    boxr, imgr = w / h, iw / ih
    if imgr > boxr:
        nw, nh = w, int(w / imgr)
    else:
        nh, nw = h, int(h * imgr)
    nl = l + (w - nw) // 2
    nt = t + (h - nh) // 2
    s.shapes.add_picture(path, Emu(int(nl)), Emu(int(nt)),
                         width=Emu(int(nw)), height=Emu(int(nh)))


def caption(s, text, l, t, w, color=GREY):
    tf = box(s, l, t, w, Inches(0.35))
    setp(tf.paragraphs[0], text, size=12, color=color, align=PP_ALIGN.CENTER)


def dark_bg(s):
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    bg.fill.solid(); bg.fill.fore_color.rgb = DARK
    bg.line.fill.background(); bg.shadow.inherit = False


def table(s, rows, l, t, w, h, col_widths, head_color=ACCENT, fontsize=13,
          head_fontsize=14):
    nr, nc = len(rows), len(rows[0])
    tbl = s.shapes.add_table(nr, nc, l, t, w, h).table
    for i, cw in enumerate(col_widths):
        tbl.columns[i].width = cw
    for r in range(nr):
        for c in range(nc):
            cell = tbl.cell(r, c)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_top = Pt(2); cell.margin_bottom = Pt(2)
            p = cell.text_frame.paragraphs[0]
            p.text = str(rows[r][c])
            p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
            run = p.runs[0] if p.runs else p.add_run()
            run.font.size = Pt(head_fontsize if r == 0 else fontsize)
            run.font.bold = (r == 0)
            run.font.name = "Calibri"
            if r == 0:
                run.font.color.rgb = WHITE
                cell.fill.solid(); cell.fill.fore_color.rgb = head_color
            else:
                run.font.color.rgb = DARK
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT if r % 2 else WHITE
    return tbl


# ---------------- slide-5 synthetic numbers, read from eval/*.csv ------------
SWEEP_METHODS = [("ls_cylinder", "Nonlinear LS"),
                 ("ransac_cylinder", "RANSAC fit"),
                 ("efficient_ransac", "Efficient RANSAC"),
                 ("3dtk_hough", "3DTK Hough (baseline)")]
# wall-clock per scene, measured during the sweep (full run_detection.sh call)
SPEED = {"ls_cylinder": "~16.6 s", "ransac_cylinder": "~3.3 s",
         "efficient_ransac": "~2.3 s", "3dtk_hough": "~1.4 s"}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def read_sweep(method):
    """Return list of sweep_* rows for a method from eval/<method>.csv."""
    path = os.path.join(MASTERS, "eval", f"{method}.csv")
    out = []
    if not os.path.isfile(path):
        return out
    with open(path) as f:
        for row in csv.DictReader(f):
            if row.get("scene", "").startswith("sweep_"):
                out.append(row)
    return out


def synth_table_rows():
    """Aggregate over all sweep_* scenes per method -> deck table rows."""
    rows = [("Method", "P / R / F1", "radius RMSE", "axis err")]
    for m, label in SWEEP_METHODS:
        rs = read_sweep(m)
        if not rs:
            rows.append((label, "(no sweep data)", "—", "—"))
            continue
        tp = sum(int(_f(r["tp"]) or 0) for r in rs)
        fp = sum(int(_f(r["fp"]) or 0) for r in rs)
        fn = sum(int(_f(r["fn"]) or 0) for r in rs)
        P = tp / (tp + fp) if (tp + fp) else 0.0
        R = tp / (tp + fn) if (tp + fn) else 0.0
        F = 2 * P * R / (P + R) if (P + R) else 0.0
        radii = [_f(r["radius_rmse_m"]) for r in rs if _f(r["radius_rmse_m"]) is not None]
        axes = [_f(r["axis_angle_mean_deg"]) for r in rs if _f(r["axis_angle_mean_deg"]) is not None]
        rr = (f"{min(radii)*100:.2f}–{max(radii)*100:.2f} cm" if radii else "—")
        aa = (f"{min(axes):.1f}–{max(axes):.1f}°" if axes else "—")
        rows.append((label, f"{P:.2f}/{R:.2f}/{F:.2f}", rr, aa))
    return rows


# =====================================================================
# TITLE
# =====================================================================
s = slide()
dark_bg(s)
band(s, ACCENT, Inches(0.18))
tf = box(s, Inches(0.9), Inches(1.9), Inches(11.6), Inches(2.6))
setp(tf.paragraphs[0], THESIS_TITLE, size=36, bold=True, color=WHITE)
add_para(tf, PROBLEM_LINE, size=20, color=RGBColor(0x9F, 0xC5, 0xDD),
         space_after=18)
tf2 = box(s, Inches(0.9), Inches(5.4), Inches(11.6), Inches(1.6))
setp(tf2.paragraphs[0], "Master's thesis  ·  evaluation review", size=18,
     color=RGBColor(0xC9, 0xD6, 0xE0))
add_para(tf2, f"{PRESENTER}   ·   supervisor: {SUPERVISOR}   ·   {DATELINE}",
         size=15, color=RGBColor(0xC9, 0xD6, 0xE0))

# =====================================================================
# 1. PROBLEM STATEMENT
# =====================================================================
s = slide()
title_band(s, "Problem statement",
           "Recover each barrel's pose (centre, axis, radius) from a single, "
           "partial 3D view — for robotic manipulation")
pic_fit(s, os.path.join(ASSETS, "station1_pile_raw.png"),
        Inches(0.4), Inches(1.45), Inches(8.4), Inches(5.2))
caption(s, "Real survey LiDAR: tumbled, partially-buried 200 L drums "
           "(r = 0.286 m), one viewpoint", Inches(0.4), Inches(6.55),
        Inches(8.4))
tf = box(s, Inches(9.0), Inches(1.6), Inches(4.1), Inches(5.2))
bullet(tf, "Drums are buried, mutually occluding, in arbitrary orientations.",
       size=15, first=True, bold=True)
bullet(tf, "One viewpoint ⇒ each barrel shows only a thin arc (~120–200°).",
       size=15)
bullet(tf, "Thin arc ⇒ radius & axis ambiguous; naive fitting fails.", size=15,
       color=AMBER)
bullet(tf, "Which detection method works best — and why — under occlusion?",
       size=15, color=ACCENT, bold=True)
bullet(tf, "Empirical comparison, not a fixed hypothesis.", size=14, italic=True,
       color=GREY)
footer(s, 1)

# =====================================================================
# 2. EXISTING SOLUTIONS
# =====================================================================
s = slide()
title_band(s, "Existing solutions — three method families",
           "Advantages / disadvantages specifically under occlusion "
           "(from the 18-method literature survey)")
rows = [
    ("Family", "Advantage under occlusion", "Disadvantage under occlusion"),
    ("LiDAR geometric\n(Hough, RANSAC, LS)",
     "No training data; a partial arc still votes / fits; cheap reference point.",
     "Hough needs accumulator mass; RANSAC tolerates partial arcs but needs a "
     "good proposer; clutter merges adjacent drums."),
    ("LiDAR learned\n(PointNet++, BtcDet)",
     "Learns partial-shape cues; can complete/flag occluded barrels — "
     "BarrelNet beats LS fitting.",
     "Needs labelled occluded examples we don't have yet; sim-to-real gap; "
     "annotation/training cost."),
    ("Camera + LiDAR fusion\n(frustum, painting)",
     "One modality compensates when the other is occluded; best recall on the "
     "safety-critical classes.",
     "Fails together when calibration drifts; still mostly LiDAR-reliant when "
     "the LiDAR leg is occluded."),
]
table(s, rows, Inches(0.4), Inches(1.5), Inches(12.55), Inches(3.5),
      [Inches(2.55), Inches(4.9), Inches(5.1)], fontsize=12, head_fontsize=13)
tf = box(s, Inches(0.45), Inches(5.2), Inches(12.4), Inches(1.8))
bullet(tf, "Why these for the thesis: breadth-first; no-training-data methods "
           "first; reuse existing code, don't reimplement.", size=14,
       first=True, bold=True, color=ACCENT)
bullet(tf, "Proposer/fit separation lets us swap one stage and compare fairly; "
           "BarrelNet is the nearest learned prior (no public code → deferred).",
       size=13, color=GREY)
footer(s, 2)

# =====================================================================
# 3. METHODS CHOSEN
# =====================================================================
s = slide()
title_band(s, "Methods chosen to evaluate — four geometric detectors",
           "All LiDAR-only, no training data; identical input & output schema")
pic_fit(s, os.path.join(ASSETS, "architecture_diagram.png"),
        Inches(0.4), Inches(1.5), Inches(6.6), Inches(5.2))
tf = box(s, Inches(7.25), Inches(1.6), Inches(5.7), Inches(5.3))
bullet(tf, "3dtk_hough — baseline; randomized 2-step Hough.", size=15,
       first=True, bold=True)
bullet(tf, "ransac_cylinder — shared proposer + normals2step fit.", size=15,
       bold=True)
bullet(tf, "ls_cylinder — shared proposer + nonlinear least-squares fit.",
       size=15, bold=True)
bullet(tf, "efficient_ransac — Schnabel RANSAC (CGAL), no proposer.", size=15,
       bold=True)
bullet(tf, "RANSAC & LS share one proposer → a clean fit-quality comparison.",
       size=13, color=GREY)
bullet(tf, "Efficient RANSAC finds cylinders directly → removes the "
           "shared-proposer confound.", size=13, color=GREY)
footer(s, 3)

# =====================================================================
# 4. EVALUATION METHOD
# =====================================================================
s = slide()
title_band(s, "Evaluation method — one harness, one metric for every method")
pic_fit(s, os.path.join(ASSETS, "pipeline_flow.png"),
        Inches(0.3), Inches(1.35), Inches(12.7), Inches(3.0))
tf = box(s, Inches(0.5), Inches(4.5), Inches(12.3), Inches(2.4))
bullet(tf, "Shared schema: gt.json vs predictions.json, both in metres "
           "(data/GT_TEMPLATE.json).", size=15, first=True)
bullet(tf, "Method contract: run_detection.sh <scene> → "
           "results/<scene>/predictions.json.", size=15)
bullet(tf, "eval/evaluate.py matches detections to ground truth and reports "
           "precision / recall / F1, radius RMSE, axis-angle error, runtime.",
       size=15, color=ACCENT, bold=True)
footer(s, 4)

# =====================================================================
# 5. SYNTHETIC EVALUATION  (new noise sweep)
# =====================================================================
s = slide()
title_band(s, "Evaluating the methods — synthetic noise sweep",
           "33 clouds, fixed ~120° arc, Gaussian noise 0.0–0.6 cm × 3 seeds — "
           "noise isolated as the single variable")
pic_fit(s, os.path.join(ASSETS, "synth_noise_sweep.png"),
        Inches(0.3), Inches(1.5), Inches(7.4), Inches(5.2))
caption(s, "accuracy / error vs Gaussian noise, one line per method",
        Inches(0.3), Inches(6.55), Inches(7.4))
table(s, synth_table_rows(), Inches(7.85), Inches(1.7), Inches(5.15),
      Inches(2.2),
      [Inches(1.75), Inches(1.3), Inches(1.25), Inches(0.85)],
      fontsize=11, head_fontsize=11)
tf = box(s, Inches(7.85), Inches(4.25), Inches(5.15), Inches(2.7))
bullet(tf, "RANSAC + LS detect at every noise level (F1 = 1.0 across the whole "
           "sweep).", size=13, first=True, color=GREEN)
bullet(tf, "Efficient RANSAC degrades fastest — axis err ~4° by σ=0.2 and it "
           "drops detections mid-range.", size=13, color=AMBER)
bullet(tf, "3DTK Hough is erratic: misses the clean scenes, only locks on at "
           "high noise.", size=13, color=AMBER)
bullet(tf, "LS best axis (≤0.1°) but slowest (~17 s/scene, ~5–10× the others).",
       size=13, color=GREY)
bullet(tf, "Table aggregates all sweep_* scenes, read live from eval/*.csv.",
       size=10, italic=True, color=GREY)
footer(s, 5)

# =====================================================================
# 6. METHODS ON REAL DATA
# =====================================================================
s = slide()
title_band(s, "Methods on real data",
           "Lab Xtion barrel (clean) and the occluded survey drum (hard)")
pic_fit(s, os.path.join(ASSETS, "real_fits_ransac_ls.png"),
        Inches(0.3), Inches(1.45), Inches(6.4), Inches(3.2))
pic_fit(s, os.path.join(ASSETS, "real_fits_on_cloud.png"),
        Inches(6.85), Inches(1.45), Inches(6.2), Inches(3.2))
caption(s, "occluded survey drum (station1_pit_barrels_seg00): per-method "
           "cross-sections (left) and cylinders on the real cloud (right)",
        Inches(0.3), Inches(4.75), Inches(12.7))
rows_a = [("xtion02_crop  (clean Xtion)", "P/R/F1", "radius", "axis"),
          ("ransac / ls / efficient_ransac", "1.0/1.0/1.0", "0.4–0.9 cm",
           "0.1–1.9°"),
          ("3dtk_hough (phantom 2nd cyl)", "0.50/1.0/0.67", "0.09 cm", "1.53°")]
rows_b = [("station1_seg00  (occluded)", "axis err", "ctr→axis", "F1"),
          ("ls_cylinder (near-miss 1.1 cm)", "17.1°", "11.1 cm", "0"),
          ("ransac / eff_ransac / hough", "69°/—/—", "54 cm/—/—", "0")]
table(s, rows_a, Inches(0.3), Inches(5.15), Inches(6.3), Inches(1.5),
      [Inches(3.0), Inches(1.4), Inches(1.1), Inches(0.8)], fontsize=10,
      head_fontsize=10, head_color=GREEN)
table(s, rows_b, Inches(6.85), Inches(5.15), Inches(6.2), Inches(1.5),
      [Inches(3.0), Inches(1.2), Inches(1.1), Inches(0.6)], fontsize=10,
      head_fontsize=10, head_color=AMBER)
footer(s, 6)

# =====================================================================
# 7. PROBLEMS WITH THE PIPELINE  (data / methodology)
# =====================================================================
s = slide()
title_band(s, "Problems with the pipeline — data & methodology limits")
tf = box(s, Inches(0.55), Inches(1.4), Inches(12.3), Inches(5.5))
bullet(tf, "Synthetic generator can't make genuinely occluded scenes — only a "
           "single idealized arc + Gaussian noise (no mutual occlusion, "
           "burial, clutter, multipath).", size=15, first=True, bold=True)
bullet(tf, "Synthetic noise is i.i.d. Gaussian; real Xtion / survey-LiDAR noise "
           "is structured (range-dependent, occlusion-shadow gaps) — real "
           "radius error ran ~6–8× synthetic, and all 4 scored F1=0 on the "
           "first real occluded drum.", size=15)
bullet(tf, "Not enough data to train/validate learned methods — no labelled "
           "occluded real scenes; the synthetic set is essentially one "
           "occlusion level.", size=15)
bullet(tf, "Can't yet accurately measure the geometric methods either — only "
           "one real occluded GT exists, and its coarse crop caught two "
           "coaxial drums as one blob, so the reference axis is itself "
           "suspect.", size=15, color=AMBER)
bullet(tf, "Net: the harness works, but it can't yet support \"A beats B under "
           "occlusion\" or \"ready to train a detector\" — both need the Isaac "
           "Sim data plan.", size=15, bold=True, color=ACCENT)
footer(s, 7)

# =====================================================================
# 8. FUTURE PIPELINE
# =====================================================================
s = slide()
title_band(s, "Future pipeline — Isaac Sim closes the data gap")
pic_fit(s, os.path.join(ASSETS, "roadmap.png"),
        Inches(0.4), Inches(1.45), Inches(6.6), Inches(5.2))
tf = box(s, Inches(7.25), Inches(1.6), Inches(5.7), Inches(5.3))
bullet(tf, "Isaac Sim dataset: full ground truth, true occlusion % per barrel.",
       size=15, first=True, bold=True)
bullet(tf, "Occlusion sweep: recall + pose error vs occlusion % — the headline "
           "result.", size=15, color=ACCENT, bold=True)
bullet(tf, "Learned methods (PointNet++ / BarrelNet-style) once training data "
           "exists.", size=15)
bullet(tf, "Camera + LiDAR fusion (camera-first frustum + LiDAR-first "
           "painting).", size=15)
bullet(tf, "Calibration-noise injection — where does fusion's advantage "
           "degrade?", size=15)
footer(s, 8)

# =====================================================================
# 9. GENERAL PROBLEMS / OPEN RISKS
# =====================================================================
s = slide()
title_band(s, "General problems & open risks")
tf = box(s, Inches(0.55), Inches(1.4), Inches(12.3), Inches(5.5))
bullet(tf, "Accuracy degrades sharply with occlusion — a known pattern, not "
           "unique to us.", size=16, first=True, bold=True, color=ACCENT)
bullet(tf, "KITTI Easy/Mod/Hard: PointRCNN car AP 88.9 → 78.6 → 77.4 "
           "(~11.5 pt) [Shi'19, arXiv:1812.04244]. Controlled occlusion: "
           "LiDAR-only mAP 64.7 → 34.1 (−47%) [Kumar'25, arXiv:2511.04347].",
       size=13, level=1)
bullet(tf, "LiDAR-only alone isn't robust enough for mission-critical use — "
           "motivates fusion.", size=16, bold=True, color=ACCENT)
bullet(tf, "Fusion beats LiDAR-only even on clean data (68.5 vs 64.7 mAP) and "
           "is far more robust to camera occlusion (−4 pt) than LiDAR-only is "
           "to LiDAR occlusion (−47 pt) — but still loses ~27 pt when the "
           "LiDAR leg itself is occluded [Kumar'25].", size=13, level=1)
bullet(tf, "Project risks: sim-to-real gap (sim LiDAR is cleaner); the "
           "manipulation half of the title not yet started; annotation cost as "
           "a fairness concern for geometric-vs-learned; scope / timeline.",
       size=14, color=GREY)
footer(s, 9)

prs.save(OUT)
print("wrote", OUT)
print("slides:", len(prs.slides._sldIdLst))
