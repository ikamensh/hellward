"""The story's painted panels (docs/story.md, hellward/story.py): reference portraits, page pictures, contact sheet.

    uv run python tools/story.py refs              # paint each missing reference portrait
    uv run python tools/story.py paint [--only KEY,KEY]  # paint each missing page picture
    uv run python tools/story.py sheet OUT.jpg     # a contact sheet of every page picture that exists

Every step keeps what it already made: delete a file to make it again. Pictures come from
Gemini 3 Pro Image through tools/intro.py's painter. The painter writes PNG to the path it is
given: each picture is painted to a temporary .png next to its target, then converted to JPEG
and the temporary file deleted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hellward.story import FRAMING, REFERENCES, RULES, STORIES, STYLES, Page  # noqa: E402
from intro import paint  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

STORY_DIR = ROOT / "godot" / "game" / "assets" / "story"   # the panels the client shows
REFS_DIR = ROOT / "hellward" / "assets" / "story" / "refs"   # what the painter is shown
PROLOGUE_DIR = STORY_DIR / "prologue"

ACT1_REFS = ("you", "akara", "priest", "lamp", "seal")
ACT2_REFS = ("necromancer", "druid", "mother_lamp")

REPAINT_PREFIX = "Repaint this picture, keeping its framing and composition: "


def prompt(page: Page, act: int) -> str:
    """The painter's prompt for a page: the act's style, what the panel shows, each named
    reference's design to keep, and the panel rules."""
    keeps = [f"Keep this design: {REFERENCES[name]}." for name in page.refs]
    return " ".join([STYLES[act], page.panel, *keeps, FRAMING, RULES])


def pictures(page: Page) -> list[Path]:
    """The pictures the painter gets with a page: first the prologue panel it edits (when
    page.base is set), then each named reference's portrait. Only files that exist."""
    pics = []
    if page.base:
        base = PROLOGUE_DIR / f"{page.base}.jpg"
        if base.exists():
            pics.append(base)
    for name in page.refs:
        ref = REFS_DIR / f"{name}.jpg"
        if ref.exists():
            pics.append(ref)
    return pics


def page_prompt(page: Page, act: int) -> tuple[str, list[Path]]:
    """A page's prompt and pictures, with the repaint prefix when it edits a prologue panel."""
    pics = pictures(page)
    text = prompt(page, act)
    if page.base and pics[:1] == [PROLOGUE_DIR / f"{page.base}.jpg"]:
        text = REPAINT_PREFIX + text
    return text, pics


def trim(image: Image.Image) -> Image.Image:
    """Cut away the paper margin the painter keeps drawing round a picture: light, flat rows and columns at the edges
    (at most an eighth of the picture on each side)."""
    grey = np.asarray(image.convert("L"), dtype=np.float32)
    h, w = grey.shape

    def paper(line: np.ndarray) -> bool:
        return float(line.mean()) > 150 and float(line.std()) < 40

    top = 0
    while top < h // 8 and paper(grey[top]):
        top += 1
    bottom = h
    while h - bottom < h // 8 and paper(grey[bottom - 1]):
        bottom -= 1
    left = 0
    while left < w // 8 and paper(grey[top:bottom, left]):
        left += 1
    right = w
    while w - right < w // 8 and paper(grey[top:bottom, right - 1]):
        right -= 1
    return image.crop((left, top, right, bottom))


def save_jpeg(tmp: Path, out: Path, quality: int, longest: int = 0, width: int = 0) -> None:
    """The painter's PNG as a JPEG, its paper margin trimmed, then delete the temporary file."""
    image = trim(Image.open(tmp).convert("RGB"))
    if longest:
        image.thumbnail((longest, longest), Image.LANCZOS)
    elif width and image.width != width:
        image = image.resize((width, int(image.height * width / image.width + 0.5)), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, "JPEG", quality=quality)
    tmp.unlink()


def refs_all() -> None:
    """Paint each missing reference portrait: the one figure or object alone, whole, on a plain dark background, in
    its act's style. No picture goes with it: a model shown other figures draws them in too."""
    for name, design in REFERENCES.items():
        out = REFS_DIR / f"{name}.jpg"
        if out.exists():
            continue
        act = 2 if name in ACT2_REFS else 1
        paint(f"{STYLES[act]} A character sheet of one subject: {design}. Only this one subject, whole and centred, on "
              f"a plain dark background, with nothing and no one else in the picture. {RULES}",
              [], out.parent / f"{out.stem}.tmp.png", "1:1")
        save_jpeg(out.parent / f"{out.stem}.tmp.png", out, quality=88, longest=1024)


def all_pages() -> list[tuple[int, Page]]:
    """Every page in STORIES order, with its act."""
    return [(story.act, page) for story in STORIES.values() for page in story.pages]


STYLE_ANCHOR = PROLOGUE_DIR / "curse.jpg"   # the prologue's ink style, shown to a painter that did not paint it


def paint_codex(prompt: str, refs: list[Path], out: Path, aspect: str) -> None:
    """Paint with Codex's image tool on the ChatGPT plan (no API credit): the references go along as attached images,
    and a prologue panel shows the style. With a base picture first, the base is edited instead."""
    import subprocess

    shown = [*refs, STYLE_ANCHOR]
    roles = "; ".join(f"image {i + 1} is {'the style to paint in' if p == STYLE_ANCHOR else 'a reference: ' + p.stem}"
                      for i, p in enumerate(shown))
    shape = "landscape 3:2 or wider" if aspect == "16:9" else "square"
    mode = "edit mode on the first attached image" if refs and refs[0].parent == PROLOGUE_DIR else "generate mode"
    task = (f"{prompt}\n\nThe attached images: {roles}. Use the built-in image_gen tool in {mode}, {shape}, with the "
            f"specification above, then copy the generated PNG to {out} (it is saved under $CODEX_HOME/generated_images). "
            f"Do not modify anything else; finish by printing the path you copied from.")
    images = [arg for p in shown for arg in ("-i", str(p))]
    result = subprocess.run(["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "-m", "gpt-5.5",
                             "-c", "model_reasoning_effort=low", "-C", str(out.parent), *images, "-"],
                            input=task, capture_output=True, text=True, timeout=900)
    if not out.exists():
        raise RuntimeError(f"codex did not write {out}:\n{(result.stdout + result.stderr)[-2000:]}")
    print(f"painted {out.name} (codex)", flush=True)


PAINTERS = {"codex": paint_codex, "openrouter": paint}


def paint_all(only: set[str], painter=paint_codex) -> int:
    """Paint each missing page picture (or only the --only keys among them). Keeps going
    past failures and reports them at the end; returns 1 if any page failed."""
    failures = []
    for act, page in all_pages():
        if only and page.key not in only:
            continue
        out = STORY_DIR / f"{page.key}.jpg"
        if out.exists():
            continue
        text, pics = page_prompt(page, act)
        tmp = out.parent / f"{out.stem}.tmp.png"
        try:
            painter(text, pics, tmp, "16:9")
        except Exception as error:  # noqa: BLE001
            print(f"failed {page.key}: {error}", flush=True)
            if tmp.exists():
                tmp.unlink()
            failures.append(page.key)
            continue
        save_jpeg(tmp, out, quality=86, width=1600)
        print(f"painted story/{page.key}.jpg", flush=True)
    if failures:
        print(f"failed: {', '.join(failures)}", flush=True)
        return 1
    return 0


def sheet(out: Path) -> int:
    """Every existing page picture as a 400 px wide thumbnail in a grid of 4 columns,
    with its key under it, saved to OUT.jpg."""
    found = [(page.key, STORY_DIR / f"{page.key}.jpg") for _, page in all_pages()]
    found = [(key, path) for key, path in found if path.exists()]
    if not found:
        print("no story panels yet", flush=True)
        return 1
    thumbs = []
    for key, path in found:
        image = Image.open(path).convert("RGB")
        thumbs.append((key, image.resize((400, int(image.height * 400 / image.width + 0.5)), Image.LANCZOS)))
    columns, pad = 4, 12
    font = ImageFont.load_default()
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    label = int(probe.textbbox((0, 0), "Ag", font=font)[3]) + 12
    rows = [thumbs[i:i + columns] for i in range(0, len(thumbs), columns)]
    heights = [max(image.height for _, image in row) + label for row in rows]
    canvas = Image.new("RGB", (columns * 400 + (columns + 1) * pad, sum(heights) + (len(rows) + 1) * pad),
                       (12, 10, 10))
    draw = ImageDraw.Draw(canvas)
    top = pad
    for row, height in zip(rows, heights):
        for n, (key, image) in enumerate(row):
            left = pad + n * (400 + pad)
            canvas.paste(image, (left, top))
            draw.text((left + 200, top + image.height + 4), key, font=font, anchor="ma",
                      fill=(222, 212, 190))
        top += height + pad
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "JPEG", quality=88)
    print(f"sheet {out} ({len(thumbs)} panels)", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("refs", help="paint each missing reference portrait")
    paint_parser = sub.add_parser("paint", help="paint each missing page picture")
    paint_parser.add_argument("--only", default="", help="comma-separated page keys")
    paint_parser.add_argument("--painter", choices=sorted(PAINTERS), default="codex",
                              help="codex (the ChatGPT plan, default) or openrouter (Gemini 3 Pro Image, API credit)")
    sheet_parser = sub.add_parser("sheet", help="a contact sheet of every page picture that exists")
    sheet_parser.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "refs":
        refs_all()
        return 0
    if args.command == "paint":
        return paint_all({k for k in args.only.split(",") if k}, PAINTERS[args.painter])
    return sheet(args.out)


if __name__ == "__main__":
    sys.exit(main())
