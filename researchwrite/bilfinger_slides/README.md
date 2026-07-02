# Bilfinger progress slides

Supervisor/industry-facing progress deck for the thesis
**"Detection and Manipulation of Semi-Occluded Objects"** (barrel detection in
3D point clouds). Prepared to share with Bilfinger ahead of a requirements telecon.

## Output (the deliverable)
- `Semi-Occluded_Object_Detection_Progress.pptx` — editable PowerPoint (16:9, 10 slides)
- `Semi-Occluded_Object_Detection_Progress.pdf` — flat PDF export for emailing

## Slides
1. Title  2. Approach (method-agnostic benchmark → Isaac Sim)  3. Synthetic
validation  4. Real-capture transfer  5. Four geometric detectors  6. Accuracy
table  7. Implemented vs pending  8. Simulation + fusion  9. Requirement
specifications & dataset request  10. Summary / telecon ask.

## Rebuild
```bash
python3 make_figures.py        # 2D matplotlib projections  -> assets/*.png
python3 make_figures_3d.py     # Open3D 3D renders (EGL headless) -> assets/*.png
python3 build_deck.py          # assembles the .pptx
libreoffice --headless --convert-to pdf Semi-Occluded_Object_Detection_Progress.pptx
```
Figures are rendered from the project's own clouds (`data/`) and each method's
`predictions.json`; nothing is hand-drawn. `make_figures_3d.py` needs Open3D with
EGL offscreen rendering (works headless on this machine).

## Before sending — confirm
- Slide 9 carries the 200 L drum dimensions as a *question* (`Ø572×851 mm?`);
  keep as a question or set to Bilfinger's actual standard.
- Date on the title slide (`DATELINE` in `build_deck.py`).

## Numbers (sourced from the live scoreboard / predictions.json)
Real `xtion02_crop` RANSAC fit: radius 4.63 cm vs 4.25 cm physical (0.38 cm),
axis-angle 1.85°. Synthetic top methods: P=R=F1=1.00, radius RMSE <0.5 cm,
axis <0.5°. See the `methods-status-and-results` memory for the full table.
