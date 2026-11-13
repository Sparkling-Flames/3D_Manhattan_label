"""Place the preserved doorway model at its actual manuscript size.

The model pixels and camera position are inherited unchanged. Only white
surrounding space is cropped in the viewport; the callout is vector text.
No photograph, model geometry, or scientific observation is regenerated.
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
SOURCE = PACKAGE / "source/fig06_fig15/source_model.png"
OUT = PACKAGE / "panels/fig15"
BLUE = "#0072B2"


def main():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "savefig.facecolor": "white",
    })
    im = Image.open(SOURCE).convert("RGB")
    # Current fig15_original_model.tex: 0.44 * 155 mm = 68.2 mm.
    fig = plt.figure(figsize=(68.2 / 25.4, 54.5 / 25.4))
    ax = fig.add_axes([.41, .03, .58, .94])
    ax.imshow(im, interpolation="none", extent=(0, 918, 765, 0))
    ax.set(xlim=(210, 712), ylim=(745, 20), aspect="equal")
    ax.axis("off")
    # Original callout tip transformed from the source PDF to native pixels.
    camera = ((83.80762481689453 + 12.060020446777344) / .24,
              (115.1129150390625 - 14.139739990234375) / .24)
    ax.scatter(*camera, s=16, c=BLUE, edgecolor="white", linewidth=.55, zorder=5)
    ax.annotate("Camera beneath\nthe doorframe", xy=camera,
                xytext=(.02, .54), textcoords="figure fraction",
                ha="left", va="center", fontsize=8, color=BLUE,
                arrowprops={"arrowstyle": "-", "color": BLUE, "lw": .8,
                            "connectionstyle": "angle,angleA=0,angleB=65,rad=0"})
    for ext in ("pdf", "svg", "png"):
        fig.savefig(OUT / f"original_model_clean.{ext}", dpi=600)
    plt.close(fig)
    # The adjoining panel embeds the unchanged native panorama at 0.54*155 mm.
    panorama_path = PACKAGE / "source/fig06_fig15/source_panorama.png"
    panorama = Image.open(panorama_path)
    width_mm = 83.7
    height_mm = width_mm * panorama.height / panorama.width
    fig = plt.figure(figsize=(width_mm / 25.4, height_mm / 25.4))
    photo_ax = fig.add_axes([0, 0, 1, 1])
    photo_ax.imshow(panorama, interpolation="none")
    photo_ax.axis("off")
    for ext in ("pdf", "svg", "png"):
        fig.savefig(OUT / f"b_panorama.{ext}", dpi=600)
    plt.close(fig)
    a = np.asarray(im)
    ys, xs = np.nonzero(a.min(axis=-1) < 250)
    record = {
        "source": str(SOURCE.relative_to(PACKAGE)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "native_source_size": list(im.size),
        "nonwhite_content_bounds": [int(xs.min()), int(ys.min()),
                                    int(xs.max()) + 1, int(ys.max()) + 1],
        "viewport": [210, 20, 712, 745],
        "all_nonwhite_content_retained": bool(xs.min() > 210 and xs.max() < 712
                                               and ys.min() > 20 and ys.max() < 745),
        "camera_pixel": list(camera),
        "final_width_mm": 68.2, "final_height_mm": 54.5,
        "callout_font_pt": 8,
        "model_pixels_or_geometry_changed": False,
        "panorama_changed": False,
        "panorama_source_sha256": hashlib.sha256(panorama_path.read_bytes()).hexdigest(),
    }
    assert record["all_nonwhite_content_retained"]
    (HERE / "verification.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
