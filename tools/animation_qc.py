"""Check installed painted monster animation against its deterministic posed guides.

The gate checks upper-body walk registration and guide-normalized hit size, so a
deliberate arm swing or raised weapon does not fail merely for changing the
full silhouette. Ambiguous contractions, smaller motion deviations, and broad
death-entry growth are review findings. A bad guide can still produce bad
motion, so visual loop review remains necessary after this automated pass.
Foot contact also needs visual review: bottom-alpha position follows lifted
feet and extending limbs, so it is not a reliable planted-foot landmark.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image

MAX_PARITY_DRIFT = 5.0  # source pixels: 2.5 logical pixels at the painted sheet's 2x density
REVIEW_TRANSITION_RESIDUAL = 8.0
ERROR_TRANSITION_RESIDUAL = 12.0
REVIEW_BODY_RATIO = (0.80, 1.20)
ERROR_BODY_RATIO = (0.50, 1.25)  # recoil may crouch; visible growth is the stronger hard signal
REVIEW_DEATH_WIDTH_RATIO = 1.35
REVIEW_DEATH_AREA_RATIO = 1.25
REVIEW_DEATH_AREA_ALONE_RATIO = 1.55


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "review"]
    message: str

    def __str__(self) -> str:
        return f"{self.severity.upper()}: {self.message}"


def _upper_center(image: Image.Image, cell: tuple[int, int], origin: tuple[float, float]) -> tuple[float, float]:
    """Track the head/upper torso without following arms, weapons, or moving feet."""
    yy, xx = np.nonzero(np.asarray(image.getchannel("A")) >= 96)
    ox, oy = origin
    cw, ch = cell
    core = ((xx >= ox - .18 * cw) & (xx <= ox + .18 * cw)
            & (yy >= oy - .40 * ch) & (yy <= oy - .12 * ch))
    if not core.any():
        raise ValueError("painted or guide frame has no visible head/upper torso in its canvas")
    return float(np.median(xx[core])), float(np.median(yy[core]))


def _body_height(image: Image.Image, cell: tuple[int, int], origin: tuple[float, float]) -> float:
    """Robust central extent: ignores most limb and weapon silhouette extensions."""
    yy, xx = np.nonzero(np.asarray(image.getchannel("A")) >= 96)
    ox, oy = origin
    cw, ch = cell
    core = ((xx >= ox - .18 * cw) & (xx <= ox + .18 * cw)
            & (yy >= oy - .58 * ch) & (yy <= oy + .04 * ch))
    if not core.any():
        raise ValueError("painted or guide frame has no visible body in its canvas")
    return float(np.quantile(yy[core], .95) - np.quantile(yy[core], .05))


def _silhouette_mass(image: Image.Image) -> tuple[float, int]:
    """Robust width and opaque area; thin extremities should not imply body growth."""
    _, xx = np.nonzero(np.asarray(image.getchannel("A")) >= 96)
    if len(xx) == 0:
        raise ValueError("painted or guide frame has no opaque silhouette")
    return float(np.quantile(xx, .95) - np.quantile(xx, .05)), len(xx)


def audit(kind: str, painted: Mapping[str, Image.Image], guides: Mapping[str, Image.Image],
          cell: tuple[int, int], origin: tuple[float, float]) -> list[Issue]:
    """Return hard registration/growth failures and pose-dependent review findings."""
    issues: list[Issue] = []
    facings = sorted(key.split("/")[0] for key in painted if key.endswith("/walk1"))
    for facing in facings:
        names = [f"{facing}/walk{i}" for i in range(1, 9)]
        paint_center = np.array([_upper_center(painted[name], cell, origin) for name in names])
        guide_center = np.array([_upper_center(guides[name], cell, origin) for name in names])
        paint_parity = float(np.median(paint_center[1::2, 0]) - np.median(paint_center[::2, 0]))
        guide_parity = float(np.median(guide_center[1::2, 0]) - np.median(guide_center[::2, 0]))
        drift = paint_parity - guide_parity
        if abs(drift) > MAX_PARITY_DRIFT:
            issues.append(Issue("error", f"{kind}/{facing} walk parity: upper body alternates "
                                f"{drift:+.1f}px relative to guide (limit ±{MAX_PARITY_DRIFT:.0f}px)"))
        paint_step = np.roll(paint_center, -1, axis=0) - paint_center
        guide_step = np.roll(guide_center, -1, axis=0) - guide_center
        for i, residual in enumerate(np.linalg.norm(paint_step - guide_step, axis=1), 1):
            if residual > REVIEW_TRANSITION_RESIDUAL:
                next_i = i % len(names) + 1
                severity = "error" if residual > ERROR_TRANSITION_RESIDUAL else "review"
                issues.append(Issue(severity, f"{kind}/{facing} walk{i}→walk{next_i} jolt: upper-body step "
                                    f"deviates {residual:.1f}px from guide"))
        walk_ratio = float(np.median([_body_height(painted[name], cell, origin) /
                                      _body_height(guides[name], cell, origin) for name in names]))
        for index in range(1, 4):
            name = f"{facing}/hit{index}"
            ratio = (_body_height(painted[name], cell, origin) /
                     _body_height(guides[name], cell, origin) / walk_ratio)
            if not REVIEW_BODY_RATIO[0] <= ratio <= REVIEW_BODY_RATIO[1]:
                severity = "error" if not ERROR_BODY_RATIO[0] <= ratio <= ERROR_BODY_RATIO[1] else "review"
                issues.append(Issue(severity, f"{kind}/{name} body scale: {ratio:.2f}× the "
                                    "guide-normalized walk"))
        hit_name, death_name = f"{facing}/hit3", f"{facing}/death1"
        hit_paint_width, hit_paint_area = _silhouette_mass(painted[hit_name])
        hit_guide_width, hit_guide_area = _silhouette_mass(guides[hit_name])
        death_paint_width, death_paint_area = _silhouette_mass(painted[death_name])
        death_guide_width, death_guide_area = _silhouette_mass(guides[death_name])
        width_ratio = (death_paint_width / death_guide_width) / (hit_paint_width / hit_guide_width)
        area_ratio = (death_paint_area / death_guide_area) / (hit_paint_area / hit_guide_area)
        broad_growth = width_ratio > REVIEW_DEATH_WIDTH_RATIO and area_ratio > REVIEW_DEATH_AREA_RATIO
        dense_growth = area_ratio > REVIEW_DEATH_AREA_ALONE_RATIO
        if broad_growth or dense_growth:
            issues.append(Issue("review", f"{kind}/{facing} hit3→death1 death entry: "
                                f"width {width_ratio:.2f}× and area {area_ratio:.2f}× "
                                "guide-normalized hit3; inspect body mass and pose continuity"))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check painted monster animation against its posed guides")
    parser.add_argument("--kind", choices=("fallen", "skeleton", "zombie"),
                        help="audit one enhanced monster (default: all three)")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from hellward.art import figures, sprites

    print("Error limits: walk parity >5px, step deviation >12px, hit ratio outside 0.50–1.25×; "
          "review: step >8px or hit ratio outside 0.80–1.20×")
    print("Death entry review only: hit3→death1 guide-normalized width >1.35× with area >1.25×, "
          "or area >1.55× alone; inspect pose and body continuity")
    total_errors = 0
    for kind in (args.kind,) if args.kind else ("fallen", "skeleton", "zombie"):
        sheet, painted = sprites._painted_enhanced(kind)
        names = [f"{facing}/{frame}" for facing in figures.facings(kind)
                 for frame in figures.walk(kind) + figures.HIT + (figures.DEATH[0],)]
        guides = {name: figures.render(kind, *name.split("/")) for name in names}
        issues = audit(kind, painted, guides, sheet.cell, sheet.origin)
        errors = sum(issue.severity == "error" for issue in issues)
        reviews = len(issues) - errors
        print(f"{kind}: {errors} error(s), {reviews} review finding(s)")
        for issue in issues:
            print(f"  {issue}")
        total_errors += errors
    return int(total_errors > 0)


if __name__ == "__main__":
    raise SystemExit(main())
