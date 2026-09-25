"""The intro, told twice: as generated video and as painted panels with captions (docs/intro.md).

    uv run python tools/intro.py paint OUT      # reference sheet, film keyframes, comic panels
    uv run python tools/intro.py voice OUT      # the Bone Priest's lines and the timeline they set
    uv run python tools/intro.py animate OUT    # one video clip per shot
    uv run python tools/intro.py score OUT      # the music
    uv run python tools/intro.py cut OUT        # OUT/intro-film.mp4 and OUT/intro-comic.mp4

Every step keeps what it already made: delete a file to make it again.  Pictures come from
Gemini 3 Pro Image (OpenRouter), clips from Grok Imagine Video, the voice from xAI's speech API
(its takes judged by Gemini listening) and the music from Lyria 3; the sound effects are the
game's own cues.  A shot with an opening still and no clip plays its two stills as a flare.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PAINTED = ROOT / "hellward" / "assets" / "painted"
SECRETS = Path("~/secrets/llm-providers.md").expanduser()

IMAGE_MODEL = "google/gemini-3-pro-image"
VIDEO_MODEL = "grok-imagine-video-1.5"
RESOLUTION = "1080p"
VOICE = "leo"            # of xAI's nineteen male voices, the one that sounds most like a man until he says who he is
LISTENER = "google/gemini-3.1-pro-preview"   # judges the takes: this pipeline has no ears of its own
W, H, FPS = 1920, 1080, 24
RATE = 44_100

FILM = ("Dark painterly fantasy key art in the manner of the first reference painting: gothic horror in the spirit of "
        "Diablo, deep blacks, candlelight and hellfire, volumetric light, rich detail. A cinematic film still. "
        "No text, letters or watermark.")
COMIC = ("A panel from a gothic horror graphic novel: heavy black ink shadows over most of the frame, bold brush "
         "contours, flat muted colours of bone, rust and dried-blood crimson, and the magic as the only glowing "
         "colour; rough paper grain. Keep the designs of the reference images, redrawn in this ink style. "
         "No text, speech bubbles or panel borders.")

LAMP = ("the sanctuary lamp: a heavy lamp of deep ruby-red glass in a pierced, gilded brass cage shaped like a small "
        "cathedral spire, hanging on three long brass chains, one flame inside")
PRIEST = ("the Bone Priest: a skeleton in a ragged brown hooded cassock, a gold crown with violet-tipped spikes on his "
          "bare skull, small green lights in his eye sockets, a crimson priest's stole embroidered with a gold cross "
          "hanging down his chest, a tall bone staff topped by a caged green orb")


@dataclass(frozen=True)
class Shot:
    key: str
    line: str             # what the Bone Priest says over it; after a " / " the line runs on over the cut to the next shot
    picture: str          # the still: the comic panel, and the film's keyframe
    motion: str           # what moves, for the video model
    refs: tuple[str, ...] = ("title",)
    base: str = ""        # paint by editing this shot's picture (the same framing) instead of from the references
    opening: str = ""     # the clip starts on this edit of the picture and ends on the picture itself
    least: float = 2.0    # the shortest this shot is on screen, in seconds
    comic: str = "wide"   # "wide" fills the screen; "strip" is one of four upright panels side by side
    sounds: tuple[tuple, ...] = ()   # (game cue or "piece:<name>", when it starts in the shot[, gain])
    gap: tuple[float, float] = (0.3, 0.45)       # silence before and after its line
    speed: float = 1.0    # how fast the film plays its clip: below 1 slows it, for a clip whose good part is short
    visions: tuple[str, ...] = ()   # edits of the comic panel it flickers through, faster and faster


SHOTS = (
    Shot("glass", "Your saints built this cathedral on the door to hell... / and lit a lamp, to keep it shut.",
         "A towering gothic stained-glass window in a dark cathedral, lit from behind. Its leaded panes tell a legend "
         "from bottom to top: at the bottom a pit of fire crowded with red demon faces; above it haloed saints in "
         f"white robes raise the walls of a cathedral over the pit; at the top hangs {LAMP}, whose golden rays drive "
         "the demons down into the fire. Coloured light falls in shafts through drifting dust.",
         "The camera tilts slowly up the window from the fiery pit to the red lamp at its top; dust drifts through the "
         "coloured shafts of light; the lamp in the glass glows.",
         refs=("title", "lamp"), least=3.0, sounds=(("wave", 0.3),)),
    Shot("lamp", "Nine hundred years, it burned. Tonight... it gutters.",
         f"Close-up of {LAMP}, hanging in the dark before the glowing golden sanctuary gate. The flame inside is small, "
         "bent and weak. Red light on old stone; candles far behind, out of focus.",
         "The flame flickers, gutters and leans, nearly going out; the lamp sways slightly on its chains; its red glow "
         "on the stone pulses weaker.",
         refs=("title", "lamp"), least=4.5),
    Shot("breach", "",
         "Looking down a long dark cathedral nave along a torn crimson carpet with gold crosses: at its far end the "
         "stone floor has split open into a swirling red vortex of hellfire, and a horde climbs out of it: small red "
         "horned imps with knives, skeletons with round shields, goat-headed demons, a winged gargoyle taking off. "
         "Everything is lit red from below; candles gutter on either side.",
         "The floor cracks wider, the red vortex swirls and flares, and the horde pours out and charges up the carpet "
         "toward the camera; dust falls from the vaults; the camera shakes.",
         least=3.5, sounds=(("piece:stone_crumble", 0.0, 0.5), ("piece:azazel_cry", 0.6, 0.3),
                            ("piece:fallen_cry", 1.6, 0.25), ("piece:goatman_cry", 2.2, 0.25))),
    Shot("wake", "So you wake what the old house still holds.",
         "In the gloom of the nave four cold, dark towers stand along the crimson carpet: a squat stone tower crowned "
         "with an unlit iron fire basket, a black runed obelisk with a dull crystal above it, a stone plinth of dull "
         "grey ice crystals, a column of stacked horned skulls. Far down the nave, a red glow and the dark silhouettes "
         "of the coming horde.",
         "Slow push in along the dark towers; the red glow at the end of the nave grows; a single ember glints.",
         refs=("title", "towers"), least=3.0, speed=0.6),
    Shot("fire", "Its fire.",
         "Close on the Pyre, one single tower: a squat round gothic stone tower whose top is an iron fire basket with "
         "a skull on its front, full of roaring orange flame, throwing embers and orange light over the dark nave "
         "and the crimson carpet. The fire burns on top of the tower itself.",
         "The flames roar up and embers stream into the dark.",
         refs=("title", "towers"), opening="The same picture with the fire basket cold, dark and unlit; the nave in gloom.",
         least=1.7, comic="strip", sounds=(("fireball", 0.1),), gap=(0.1, 0.4)),
    Shot("thunder", "Its thunder.",
         "Close on the Storm Obelisk: a tall black stone obelisk carved with glowing blue runes, a blue crystal floating "
         "above its tip, lightning crackling down its sides into the floor.",
         "Lightning crackles down the obelisk and the blue runes blaze.",
         refs=("title", "towers"), opening="The same picture with the obelisk cold and dark: the runes unlit, the crystal dull, no lightning.",
         least=1.7, comic="strip", sounds=(("lightning", 0.05),), gap=(0.1, 0.4)),
    Shot("frost", "Its frost.",
         "Close on the Frost Shrine: a stone plinth from which tall pale-blue ice crystals burst upward, breathing "
         "freezing mist over the carpet; frost creeps across the flagstones.",
         "The ice crystals shoot upward and freezing mist rolls out across the floor.",
         refs=("title", "towers"), opening="The same picture with only a bare stone plinth and a thin film of frost; no crystals yet.",
         least=1.7, comic="strip", sounds=(("frost", 0.05),), gap=(0.1, 0.4)),
    Shot("dead", "And its dead.",
         "Close on the Plague Totem: a column of stacked skulls crowned with curling ram horns on a stone plinth, its "
         "eye sockets burning poison green, green venom dripping down the bone.",
         "The skulls' eye sockets ignite green and venom drips.",
         refs=("title", "towers"), opening="The same picture with the skulls' eye sockets dark and empty, no glow, no venom.",
         least=2.2, comic="strip", sounds=(("venom_cast", 0.0, 0.3), ("piece:bones", 1.3, 0.35)), gap=(0.15, 0.7)),
    Shot("priest", "I know this house. I kept its lamp, once.",
         f"In the middle of a crimson cathedral carpet, a blur of charging demons rushes past on both sides, and one "
         f"figure stands perfectly still, staring straight at the viewer: {PRIEST}.",
         "Demons rush past on both sides in a blur; the priest stays still, then slowly tilts his skull; the green "
         "lights in his eyes brighten.",
         refs=("title", "priest"), least=4.0, sounds=(("ponder", 0.2),), gap=(0.8, 0.5), speed=0.5),
    Shot("bones", "Now I cast the bones... and watch the fight <slow>a hundred times</slow>, before it begins.",
         "Close on dark flagstones: a skeletal hand has just thrown a handful of small bones and teeth. They glow "
         "violet and lie in the shape of a winding path, and above them hover small ghostly violet visions of the "
         "battle, like a translucent model of it: tiny towers, tiny flames, a tiny gate, tiny demons.",
         "The bones settle; violet ghost images of towers, fire and demons rise from them and flicker, changing "
         "rapidly from one version of the battle to another, again and again.",
         refs=("title", "priest"), least=5.0, sounds=(("piece:bones", 0.0), ("chant", 1.5)),
         visions=("In the violet vision above the bones the towers have fallen and demons pour through a broken gate.",
                  "In the violet vision above the bones a tower stands caged in bones while demons swarm a gate.",
                  "In the violet vision above the bones a burning tower collapses and a winged demon dives at it.")),
    Shot("curse", "I know which tower to break. And when.",
         "In a stone arch across the crimson carpet stands a gate of iron-banded oak glowing with golden runes; demons "
         "pile against it, battering it, while the Pyre beside it rains fire on them. From the left a violet beam "
         "lances from the Bone Priest's staff into the Pyre, and a cage of huge curved bones bursts out of the floor "
         "around the tower, choking its flame.",
         "The violet beam strikes; bones erupt from the floor and close round the tower like ribs; its fire gutters "
         "to grey smoke; the demons at the gate surge forward.",
         refs=("title", "priest", "towers"), least=3.5,
         sounds=(("curse", 0.2), ("piece:bones", 0.5), ("door_hit", 1.2), ("door_hit", 2.1))),
    Shot("ember", "In every night I have seen... [pause] the lamp goes out.",
         "The same picture, but the flame inside the lamp has shrunk to a dying ember and the long shadow of a "
         "skeletal hand reaches across the lamp and the gate behind it.",
         "The hand's shadow closes over the lamp; the ember flickers weaker and dies; the picture sinks into darkness.",
         base="lamp", least=4.5, sounds=(("leak", 1.2),), gap=(0.3, 1.4)),
)
TITLE_SECONDS = 5.5


# -- Keys and payloads --------------------------------------------------------------------


def secret(name: str) -> str:
    for line in SECRETS.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    raise KeyError(f"{name} is not in {SECRETS}")


def data_url(path: Path, longest: int = 1536) -> str:
    image = Image.open(path).convert("RGB")
    image.thumbnail((longest, longest))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def post(url: str, body: dict, key: str, timeout: float = 600) -> bytes:
    request = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{url}: {error.code} {error.read().decode()[:800]}") from error


# -- Pictures -----------------------------------------------------------------------------


def paint(prompt: str, refs: list[Path], out: Path, aspect: str) -> None:
    content = [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": data_url(p)}} for p in refs]
    body = {"model": IMAGE_MODEL, "modalities": ["image", "text"], "messages": [{"role": "user", "content": content}],
            "image_config": {"aspect_ratio": aspect, "image_size": "2K"}}
    response = json.loads(post("https://openrouter.ai/api/v1/chat/completions", body, secret("OPENROUTER_API_KEY")))
    images = response["choices"][0]["message"].get("images") or []
    if not images:
        raise RuntimeError(f"{IMAGE_MODEL} returned no image for {out.name}: {json.dumps(response)[:800]}")
    encoded = re.match(r"data:image/\w+;base64,(.*)", images[0]["image_url"]["url"], re.S).group(1)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB").save(out)
    print(f"painted {out.relative_to(out.parents[1])}", flush=True)


def sprite_cell(sheet: str, key: str, scale: int) -> Image.Image:
    meta = json.loads((PAINTED / f"{sheet}.json").read_text())
    cell = next(c for c in meta["cells"] if c["key"] == key)
    w, h = meta["cell"]
    image = Image.open(PAINTED / f"{sheet}.png").convert("RGBA").crop((cell["col"] * w, cell["row"] * h, (cell["col"] + 1) * w, (cell["row"] + 1) * h))
    return image.resize((w * scale, h * scale), Image.LANCZOS)


def on_grey(image: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", image.size, (70, 66, 64, 255))
    canvas.alpha_composite(image)
    return canvas.convert("RGB")


def references(out: Path) -> dict[str, Path]:
    """The designs every picture shares: the title painting, the lamp, the Bone Priest and the four towers."""
    refs = out / "refs"
    refs.mkdir(parents=True, exist_ok=True)
    paths = {"title": PAINTED / "title.jpg", "lamp": refs / "lamp.png", "priest": refs / "priest.png", "towers": refs / "towers.png"}
    if not paths["towers"].exists():
        towers = Image.open(PAINTED / "towers.png").convert("RGBA")
        top = towers.crop((0, towers.height * 2 // 3, towers.width, towers.height))
        on_grey(top.resize((top.width * 3, top.height * 3), Image.LANCZOS)).save(paths["towers"])
    sprite = refs / "priest-sprite.png"
    if not sprite.exists():
        on_grey(sprite_cell("mon-priest", "front/walk1", 4)).save(sprite)
    if not paths["priest"].exists():
        paint(f"A full-length character portrait of {PRIEST}, standing on plain dark grey, lit by candlelight. Keep the "
              "design of the small game sprite (second image) exactly and paint it in the style of the first image. "
              "No text.", [paths["title"], sprite], paths["priest"], "2:3")
    if not paths["lamp"].exists():
        paint(f"A single object portrait of {LAMP}, lit from within, on plain black. It belongs in the cathedral of the "
              "reference painting. No text.", [paths["title"]], paths["lamp"], "2:3")
    return paths


def paint_all(out: Path, only: set[str]) -> None:
    refs = references(out)
    for style, look in (("film", FILM), ("comic", COMIC)):
        for shot in SHOTS:
            if only and shot.key not in only:
                continue
            path = out / style / f"{shot.key}.png"
            aspect = "9:16" if style == "comic" and shot.comic == "strip" else "16:9"
            if not path.exists():
                if shot.base:
                    paint(f"Edit this image: {shot.picture} Keep everything else, the framing and the style exactly.",
                          [out / style / f"{shot.base}.png"], path, aspect)
                else:
                    paint(f"{shot.picture}\n\n{look}", [refs[r] for r in shot.refs], path, aspect)
            for n, vision in enumerate(shot.visions if style == "comic" else ()):
                variant = out / style / f"{shot.key}-v{n}.png"
                if not variant.exists():
                    paint(f"Edit this image: {vision} Keep the hand, the bones, the floor, the candles, the framing and "
                          "the style exactly; change only the ghostly vision.", [path], variant, aspect)
            opening = out / style / f"{shot.key}-open.png"
            if style == "film" and shot.opening and not opening.exists():
                paint(f"Edit this image: {shot.opening} Keep everything else, the framing and the style exactly.",
                      [path], opening, aspect)


# -- The voice ----------------------------------------------------------------------------


def read_audio(path: Path) -> np.ndarray:
    """Any audio file as float32 stereo at RATE."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(RATE), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def write_wav(path: Path, clip: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ac", "2", "-ar", str(RATE), "-i", "-", str(path)],
                   input=np.ascontiguousarray(clip, np.float32).tobytes(), check=True)


def speak(text: str, out: Path, voice: str = VOICE, speed: float = 1.0) -> None:
    body = {"text": text, "voice_id": voice, "language": "en", "speed": speed,
            "output_format": {"codec": "wav", "sample_rate": RATE}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(post("https://api.x.ai/v1/tts", body, secret("GROK_API_KEY")))


def octave_down(mono: np.ndarray) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-i", "-", "-af",
                          f"asetrate={RATE // 2},aresample={RATE},atempo=2.0", "-f", "f32le", "-"],
                         input=np.ascontiguousarray(mono, np.float32).tobytes(), check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32)


def priestly(dry: np.ndarray, unmasked: bool) -> np.ndarray:
    """A shade lower and in a stone room: the voice of something that was a man.  Once he has said who he
    is, the mask slips and something an octave under him speaks along."""
    from sagaforge.synth import highpass, reverb
    mono = dry.mean(axis=1)
    loud = np.flatnonzero(np.abs(mono) > 0.01)
    mono = mono[max(0, loud[0] - int(0.03 * RATE)):]
    lower = np.interp(np.arange(0, len(mono), 0.96), np.arange(len(mono)), mono)   # most of a semitone down, 4% slower
    if unmasked:
        under = octave_down(lower)[: len(lower)]
        lower = lower + 0.32 * np.pad(under, (0, len(lower) - len(under)))
    lower = highpass(lower, 70.0)
    windows = np.sqrt(np.convolve(lower ** 2, np.ones(2205) / 2205, "valid"))
    lower = lower * (0.1 / np.percentile(windows[windows > 0.01], 90))
    wet = reverb(lower, decay=3.2, mix=0.32, predelay=0.03, damping=3800.0, seed=11)
    trimmed = np.trim_zeros(np.abs(wet).max(axis=1) > 0.004, "b")
    return wet[: len(trimmed) + int(0.05 * RATE)]


def listen(question: str, clips: list[tuple[str, Path]]) -> str:
    """Ask the listening model about labelled audio clips."""
    content = [{"type": "text", "text": question}]
    for label, path in clips:
        mp3 = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-b:a", "64k", "-f", "mp3", "-"],
                             check=True, capture_output=True).stdout
        content += [{"type": "text", "text": label},
                    {"type": "input_audio", "input_audio": {"data": base64.b64encode(mp3).decode(), "format": "mp3"}}]
    body = {"model": LISTENER, "messages": [{"role": "user", "content": content}]}
    return json.loads(post("https://openrouter.ai/api/v1/chat/completions", body, secret("OPENROUTER_API_KEY")))["choices"][0]["message"]["content"]


def plain(line: str) -> str:
    """A line as written, without its speech tags (" / " marks where it runs over a cut)."""
    return re.sub(r"\s*\[[a-z-]+\]\s*", " ", re.sub(r"</?[a-z-]+>", "", line)).strip()


def said(line: str) -> str:
    """A line as the speech model gets it."""
    return line.replace(" / ", " ")


TAKES = 3
BRIEF = ("The narrator of a gothic horror game intro is a dead priest risen as a skeletal demon: old, dry, calm, "
         "quietly menacing, certain. ")


def voice_all(out: Path) -> None:
    reveal = next(i for i, shot in enumerate(SHOTS) if shot.key == "priest")
    for i, shot in enumerate(SHOTS):
        if not shot.line:
            continue
        raw, done = out / "voice" / f"{shot.key}-dry.wav", out / "voice" / f"{shot.key}.wav"
        if not raw.exists():
            takes = [out / "voice" / f"{shot.key}-take{n}.wav" for n in range(TAKES)]
            for take in takes:
                if not take.exists():
                    speak(said(shot.line), take)
            verdict = listen(f"{BRIEF}Three takes of his line \"{said(plain(shot.line))}\". Which take is delivered best: "
                             "clear, unhurried, stress where the meaning is, no odd pause or artifact? Answer with "
                             "the take number alone on the first line, then one sentence why.",
                             [(f"Take {n}", take) for n, take in enumerate(takes)])
            best = int(re.search(r"\d", verdict).group())
            print(f"{shot.key}: take {best} -- {verdict.splitlines()[-1][:160]}", flush=True)
            raw.write_bytes(takes[best].read_bytes())
        if not done.exists():
            write_wav(done, priestly(read_audio(raw), unmasked=i >= reveal))
    (out / "timeline.json").write_text(json.dumps(timeline(out), indent=1))


def speech_span(dry: np.ndarray) -> tuple[float, float, float]:
    """A take once lowered: how long it speaks from first sound to last, and the longest pause inside it
    (its start and end), where a line that runs over a cut is split."""
    envelope = np.convolve(np.abs(dry).max(axis=1), np.ones(441) / 441, "same") > 0.01
    loud = np.flatnonzero(envelope)
    first, last = loud[0], loud[-1]
    quiet = ~envelope[first:last]
    edges = np.flatnonzero(np.diff(np.concatenate(([0], quiet.astype(np.int8), [0]))))
    runs = edges.reshape(-1, 2)
    begin, end = max(runs, key=lambda r: r[1] - r[0]) if len(runs) else (last - first, last - first)
    return (last - first) / RATE / 0.96, begin / RATE / 0.96, end / RATE / 0.96


def timeline(out: Path) -> dict:
    """When each shot starts and how long it lasts (long enough for its line, never shorter than its least),
    and when each part of a line is said."""
    shots, words, clock, carry = [], [], 0.0, None
    for shot in SHOTS:
        at = clock + shot.gap[0]
        if carry:   # the end of the previous shot's line, said over this shot's opening
            text, length = carry
            words.append({"text": text, "at": round(clock, 3), "length": round(length, 3)})
            at = clock + length + shot.gap[0]
            carry = None
        length = max(shot.least, at - clock)
        if shot.line:
            speech, pause, resume = speech_span(read_audio(out / "voice" / f"{shot.key}-dry.wav"))
            parts = plain(shot.line).split(" / ")
            words.append({"text": parts[0], "at": round(at, 3), "voice": shot.key,
                          "length": round(pause if len(parts) > 1 else speech, 3)})
            if len(parts) > 1:
                carry = (parts[1], speech - resume)
                length = max(shot.least, at - clock + resume)
            else:
                length = max(shot.least, at - clock + speech + shot.gap[1])
        shots.append({"key": shot.key, "start": round(clock, 3), "length": round(length, 3)})
        clock += length
    shots.append({"key": "title", "start": round(clock, 3), "length": TITLE_SECONDS})
    return {"shots": shots, "words": words}


# -- The clips ----------------------------------------------------------------------------


def animate(first: Path, last: Path | None, prompt: str, seconds: int, out: Path) -> None:
    body = {"model": VIDEO_MODEL, "prompt": prompt, "image": {"url": data_url(first, 1920)}, "duration": seconds,
            "aspect_ratio": "16:9", "resolution": RESOLUTION}
    if last:
        body["last_frame"] = {"url": data_url(last, 1920)}
    key = secret("GROK_API_KEY")
    request_id = json.loads(post("https://api.x.ai/v1/videos/generations", body, key))["request_id"]
    while True:
        time.sleep(8)
        poll = urllib.request.Request(f"https://api.x.ai/v1/videos/{request_id}", headers={"Authorization": "Bearer " + key})
        status = json.load(urllib.request.urlopen(poll, timeout=60))
        if status["status"] == "done":
            break
        if status["status"] in ("failed", "expired"):
            raise RuntimeError(f"{out.name}: {status}")
    out.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(status["video"]["url"], out)
    cost = status.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10
    print(f"animated {out.name}: {seconds} s, ${cost:.2f}", flush=True)


def animate_all(out: Path, only: set[str]) -> None:
    rows = {row["key"]: row for row in json.loads((out / "timeline.json").read_text())["shots"]}
    for shot in SHOTS:
        clip = out / "clips" / f"{shot.key}.mp4"
        if clip.exists() or (only and shot.key not in only):
            continue
        still = out / "film" / f"{shot.key}.png"
        opening = out / "film" / f"{shot.key}-open.png"
        first, last = (opening, still) if shot.opening else (still, None)
        seconds = min(15, max(2, math.ceil(rows[shot.key]["length"] * shot.speed + 0.3)))
        animate(first, last, f"{shot.motion} Dark gothic cinematic, slow and heavy; no text.", seconds, clip)


# -- The music ----------------------------------------------------------------------------


def minute(t: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def score(out: Path) -> None:
    """Lyria 3 writes the music.  The prompt asks for each section where its shots start, but Lyria keeps no
    time: on 2026-09-25 it swelled steadily for 67 s.  The cut fades it out where the lamp goes out."""
    path = out / "music.mp3"
    if path.exists():
        return
    at = {row["key"]: row["start"] for row in json.loads((out / "timeline.json").read_text())["shots"]}
    prompt = (
        "Instrumental cinematic underscore for the intro of a gothic horror game set in a desecrated cathedral. "
        "No vocals with words.\n"
        f"[0:00] A low pipe organ drone and one far cathedral bell in a vast stone hall; mournful, sparse, very quiet.\n"
        f"[{minute(at['lamp'])}] A lone low cello over the drone, uneasy, fading.\n"
        f"[{minute(at['breach'])}] A sudden heavy impact: deep drums and low brass, rumbling.\n"
        f"[{minute(at['wake'])}] A driving low string ostinato and a heartbeat drum, four heavy hits building.\n"
        f"[{minute(at['priest'])}] It drops to an eerie hush: a whispering wordless low choir, a ticking pulse, dread.\n"
        f"[{minute(at['curse'])}] A dissonant swell of choir and organ rising to a peak.\n"
        f"[{minute(at['ember'] + 2.5)}] Everything cuts off dead into silence.\n"
        f"[{minute(at['title'] + 1.0)}] One soft sustained organ chord, hopeful but dark, to the end at {minute(at['title'] + 5.5)}.")
    body = {"model": "google/lyria-3-pro-preview", "modalities": ["audio", "text"], "stream": True,
            "audio": {"format": "mp3"}, "messages": [{"role": "user", "content": prompt}]}
    request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + secret("OPENROUTER_API_KEY"),
                                              "Content-Type": "application/json"})
    audio = b""
    with urllib.request.urlopen(request, timeout=900) as stream:
        for raw in stream:
            line = raw.decode().strip()
            if not line.startswith("data: {"):
                continue
            for choice in json.loads(line[6:]).get("choices", []):
                piece = choice.get("delta", {}).get("audio")
                if piece:
                    audio += base64.b64decode(piece["data"])
    if not audio:
        raise RuntimeError("Lyria sent no audio")
    path.write_bytes(audio)
    (out / "music-prompt.txt").write_text(prompt)
    print(f"scored {path.name}", flush=True)


# -- The cut ------------------------------------------------------------------------------


def cue(name: str) -> np.ndarray:
    from hellward.audio import cues, pieces
    if name.startswith("piece:"):
        clip = cues.finish(pieces.take(name.split(":", 1)[1], 0), cues.BATTLE, cues.PEAKS["battle"])
    else:
        clip = cues.CUES[name].render(0)
    clip = np.asarray(clip, np.float32)
    return np.stack([clip, clip], axis=1) if clip.ndim == 1 else clip


def lay(track: np.ndarray, clip: np.ndarray, at: float, gain: float = 1.0) -> None:
    start = int(at * RATE)
    end = min(len(track), start + len(clip))
    track[start:end] += clip[: end - start] * gain


def soundtrack(out: Path, plan: dict) -> np.ndarray:
    """The music under the priest's voice, the game's cues on the shots, the relit lamp under the title."""
    from sagaforge.synth import soft_clip
    shots = plan["shots"]
    total = shots[-1]["start"] + shots[-1]["length"]
    track = np.zeros((int(total * RATE) + RATE, 2), np.float32)
    voice = np.zeros_like(track)
    for words in plan["words"]:
        if "voice" in words:
            lay(voice, read_audio(out / "voice" / f"{words['voice']}.wav"), words["at"])
    music = read_audio(out / "music.mp3")[: len(track)]
    music = np.pad(music, ((0, len(track) - len(music)), (0, 0))) / max(1e-6, np.abs(music).max())
    t = np.arange(len(track)) / RATE
    ember = next(row for row in shots if row["key"] == "ember")
    gone = ember["start"] + 1.6   # the hand closes over the lamp and the music with it
    envelope = np.clip((gone + 1.2 - t) / 1.2, 0.0, 1.0)
    speech = np.convolve(np.abs(voice).max(axis=1), np.ones(RATE // 5) / (RATE // 5), "same")
    duck = 1.0 - 0.6 * np.clip(speech / 0.05, 0.0, 1.0)
    track += music * (0.4 * envelope * duck)[:, None] + 1.25 * voice
    for shot, row in zip(SHOTS, shots):
        for name, at, *gain in shot.sounds:
            lay(track, cue(name), row["start"] + at, gain[0] if gain else 0.45)
    title = shots[-1]["start"]
    lay(track, cue("cleanse"), title + 0.9, 0.6)
    lay(track, cue("cleared"), title + 1.9, 0.5)
    lay(track, cue("wave"), title + 2.0, 0.3)
    speaking = speech > 0.02
    level = np.sqrt((track[speaking] ** 2).mean())
    return soft_clip(track * (10 ** (-18 / 20) / level), 1.1)   # the voice at -18 dB; only the loudest hits are rounded off


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(f"/System/Library/Fonts/Supplemental/{name}", size)


def caption(frame: Image.Image, text: str, alpha: float, *, boxed: bool) -> None:
    """The line under the picture: small subtitles on the film, a parchment box on the comic."""
    if alpha <= 0 or not text:
        return
    face = font("Baskerville.ttc", 46)
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if not boxed:   # a shadow along the bottom, so the words read over bright glass or fire
        shade = np.linspace(0, 1, 260) ** 1.6 * 170 * alpha
        band = np.zeros((260, W, 4), np.uint8)
        band[..., 3] = shade[:, None].astype(np.uint8)
        layer.alpha_composite(Image.fromarray(band), (0, H - 260))
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=face) > W * 0.62 and current:
            lines.append(current)
            current = word
        else:
            current = trial
    lines.append(current)
    step = face.size + 10
    height = step * len(lines)
    top = H - 90 - height
    if boxed:
        width = max(draw.textlength(line, font=face) for line in lines) + 70
        box = (W / 2 - width / 2, top - 26, W / 2 + width / 2, top + height + 18)
        draw.rectangle(box, fill=(222, 206, 170, int(235 * alpha)), outline=(60, 30, 20, int(255 * alpha)), width=4)
        ink = (40, 18, 12, int(255 * alpha))
    else:
        ink = (232, 222, 200, int(255 * alpha))
    for i, line in enumerate(lines):
        outline = {} if boxed else {"stroke_width": 3, "stroke_fill": (0, 0, 0, int(230 * alpha))}
        draw.text((W / 2, top + i * step), line, font=face, fill=ink, anchor="ma", **outline)
    frame.alpha_composite(layer)


def title_card(t: float, lamp: Image.Image) -> Image.Image:
    """Black; the lamp catches again, flickering; HELLWARD; the dare."""
    kindle = min(1.0, max(0.0, (t - 0.9) / 1.2))
    flicker = 1.0 + 0.14 * kindle * math.sin(23 * t) * math.sin(7 * t + 1.0)
    frame = Image.eval(lamp, lambda v, k=0.5 * kindle * flicker: min(255, int(v * k))).convert("RGBA")
    draw = ImageDraw.Draw(frame)
    word = min(1.0, max(0.0, (t - 2.0) / 1.0))
    dare = min(1.0, max(0.0, (t - 3.0) / 0.8))
    draw.text((W / 2 + 4, H * 0.30 + 4), "HELLWARD", font=font("Luminari.ttf", 150), fill=(0, 0, 0, int(230 * word)), anchor="mm")
    draw.text((W / 2, H * 0.30), "HELLWARD", font=font("Luminari.ttf", 150), fill=(236, 186, 100, int(255 * word)), anchor="mm")
    draw.text((W / 2, H * 0.30 + 120), "Keep it burning.", font=font("Baskerville.ttc", 52), fill=(222, 212, 190, int(255 * dare)),
              anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0, int(200 * dare)))
    return frame


def cover(image: Image.Image, zoom: float, dx: float, dy: float) -> Image.Image:
    """*image* scaled to cover the screen at *zoom*, its centre moved by (dx, dy) of the slack."""
    scale = max(W / image.width, H / image.height) * zoom
    size = (int(image.width * scale + 0.5), int(image.height * scale + 0.5))
    big = image.resize(size, Image.BICUBIC)
    left = (size[0] - W) / 2 * (1 + dx)
    top = (size[1] - H) / 2 * (1 + dy)
    return big.crop((int(left), int(top), int(left) + W, int(top) + H))


class Clip:
    """A generated video's frames, read at the film's rate and size."""

    def __init__(self, path: Path) -> None:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={FPS},scale={W}:{H}:flags=lanczos",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
        self.frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)

    def at(self, t: float) -> Image.Image:
        position = min(len(self.frames) - 1.001, t * FPS)
        index, share = int(position), position - int(position)
        pair = self.frames[index].astype(np.float32) * (1 - share) + self.frames[index + 1].astype(np.float32) * share
        return Image.fromarray(pair.astype(np.uint8)).convert("RGBA")


class Ignition:
    """A shot with no clip, made from its dark opening and its lit picture: a flare, the light, a push in."""

    def __init__(self, dark: Path, lit: Path) -> None:
        self.dark = np.asarray(cover(Image.open(dark).convert("RGB"), 1.0, 0, 0), np.float32)
        self.lit = np.asarray(cover(Image.open(lit).convert("RGB"), 1.0, 0, 0), np.float32)

    def at(self, t: float) -> Image.Image:
        light = min(1.0, max(0.0, (t - 0.08) / 0.3)) ** 0.7
        flare = 1.0 + 0.55 * math.exp(-((t - 0.3) / 0.12) ** 2)
        frame = np.clip((self.dark * (1 - light) + self.lit * light) * flare, 0, 255).astype(np.uint8)
        return cover(Image.fromarray(frame), 1.0 + 0.05 * t, 0.0, 0.0).convert("RGBA")


def film_frame(out: Path, shot: Shot, t: float, clips: dict) -> Image.Image:
    if shot.key not in clips:
        clips.clear()   # one clip in memory at a time
        clip = out / "clips" / f"{shot.key}.mp4"
        clips[shot.key] = Clip(clip) if clip.exists() else Ignition(out / "film" / f"{shot.key}-open.png", out / "film" / f"{shot.key}.png")
    return clips[shot.key].at(t * shot.speed)


STRIP = [s.key for s in SHOTS if s.comic == "strip"]


def unframed(image: Image.Image, most: float = 0.06) -> Image.Image:
    """The picture without the paper border and frame line the painter sometimes draws round a panel."""
    pixels = np.asarray(image, np.int16)
    paper = pixels[2, 2]

    def inset(lines: np.ndarray) -> int:   # lines: (count, length, 3), outermost first
        n = 0
        while n < int(len(lines) * most):
            line = lines[n]
            flat = (np.abs(line - paper).max(axis=1) < 40).mean() > 0.9 or (line.max(axis=1) < 45).mean() > 0.97
            if not flat:
                break
            n += 1
        return n

    top, bottom = inset(pixels), inset(pixels[::-1])
    left, right = inset(pixels.transpose(1, 0, 2)), inset(pixels.transpose(1, 0, 2)[::-1])
    if not (top or bottom or left or right):
        return image
    pad = 6   # the anti-aliased edge of the frame line
    return image.crop((left + pad, top + pad, image.width - right - pad, image.height - bottom - pad))


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    scale = max(size[0] / image.width, size[1] / image.height)
    fitted = image.resize((int(image.width * scale + 0.5), int(image.height * scale + 0.5)), Image.BICUBIC)
    left, top = (fitted.width - size[0]) // 2, (fitted.height - size[1]) // 2
    return fitted.crop((left, top, left + size[0], top + size[1]))


def comic_frame(out: Path, shot: Shot, t: float, length: float, cache: dict) -> Image.Image:
    def panel(name: str) -> Image.Image:
        if name not in cache:
            cache[name] = unframed(Image.open(out / "comic" / f"{name}.png").convert("RGB"))
        return cache[name]

    if shot.comic == "strip":   # four dark panels; each catches light on its word
        frame = Image.new("RGBA", (W, H), (12, 10, 10, 255))
        gutter = 18
        size = ((W - gutter * (len(STRIP) + 1)) // len(STRIP), H - 2 * gutter)
        now = STRIP.index(shot.key)
        for i, key in enumerate(STRIP):
            lit = np.asarray(fit(panel(key), size), np.float32)
            dark = lit.mean(axis=2, keepdims=True) * 0.22 + lit * 0.05
            share = 1.0 if i < now else 0.0 if i > now else min(1.0, t / 0.3)
            flare = 1.0 + (0.5 * math.exp(-((t - 0.25) / 0.1) ** 2) if i == now else 0.0)
            pixels = np.clip((dark * (1 - share) + lit * share) * flare, 0, 255).astype(np.uint8)
            frame.paste(Image.fromarray(pixels), (gutter + i * (size[0] + gutter), gutter))
        return frame
    name = shot.key
    if shot.visions:   # the futures he tries, each shown for less time than the one before
        faces = [shot.key] + [f"{shot.key}-v{n}" for n in range(len(shot.visions))]
        clock, hold, n = 1.4, 0.8, 0
        while clock < t:
            clock, hold, n = clock + hold, max(0.12, hold * 0.72), n + 1
        name = faces[n % len(faces)]
    progress = t / max(length, 0.01)
    drift = {"glass": (0.0, 0.9 - 1.8 * min(1.0, progress * 1.3)), "priest": (0.0, -0.2)}.get(shot.key, (0.3 - 0.6 * progress, 0.0))
    return cover(panel(name), 1.06 + 0.06 * progress, *drift).convert("RGBA")


def render(out: Path, style: str, plan: dict, audio: Path) -> Path:
    target = out / f"intro-{style}.mp4"
    shots, words = plan["shots"], plan["words"]
    total = shots[-1]["start"] + shots[-1]["length"]
    ends = [min(w["at"] + w["length"] + 0.4, nxt["at"]) for w, nxt in zip(words, words[1:] + [{"at": total}])]
    encoder = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                                "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-crf", "18", "-preset",
                                "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", str(target)],
                               stdin=subprocess.PIPE)
    lamp = cover(Image.open(out / style / "lamp.png").convert("RGB"), 1.0, 0.0, 0.0)
    cache: dict = {}
    for n in range(int(total * FPS)):
        t = n / FPS
        index = max(i for i, row in enumerate(shots) if row["start"] <= t)
        row = shots[index]
        local = t - row["start"]
        if row["key"] == "title":
            frame = title_card(local, lamp)
        else:
            shot = SHOTS[index]
            frame = film_frame(out, shot, local, cache) if style == "film" else comic_frame(out, shot, local, row["length"], cache)
            if index == 0:
                frame = Image.eval(frame, lambda v, k=min(1.0, local / 1.5): int(v * k))
            if shot.key == "ember":   # into the dark
                sink = min(1.0, max(0.0, (row["length"] - local) / 1.2))
                frame = Image.eval(frame, lambda v, k=sink: int(v * k))
        for w, end in zip(words, ends):
            if w["at"] <= t < end:
                alpha = min(1.0, (t - w["at"]) / 0.3, (end - t) / 0.3)
                caption(frame, w["text"].replace("...", "…"), alpha, boxed=style == "comic")
        encoder.stdin.write(frame.convert("RGB").tobytes())
    encoder.stdin.close()
    if encoder.wait():
        raise RuntimeError(f"ffmpeg failed on {target}")
    print(f"cut {target}", flush=True)
    return target


def cut(out: Path, styles: list[str]) -> None:
    plan = json.loads((out / "timeline.json").read_text())
    audio = out / "soundtrack.wav"
    write_wav(audio, soundtrack(out, plan))
    for style in styles:
        render(out, style, plan, audio)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=("paint", "voice", "animate", "score", "cut"))
    parser.add_argument("out", type=Path)
    parser.add_argument("--only", default="", help="comma-separated shot keys")
    parser.add_argument("--style", default="film,comic", help="for cut: film, comic or both")
    args = parser.parse_args()
    only = {k for k in args.only.split(",") if k}
    if args.step == "paint":
        paint_all(args.out, only)
    elif args.step == "voice":
        voice_all(args.out)
    elif args.step == "animate":
        animate_all(args.out, only)
    elif args.step == "score":
        score(args.out)
    else:
        cut(args.out, args.style.split(","))


if __name__ == "__main__":
    sys.exit(main())
