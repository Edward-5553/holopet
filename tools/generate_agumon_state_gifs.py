#!/usr/bin/env python3
"""Animate the generated Agumon-line state sprites for the HoloCubic UI."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "art" / "agumon-states" / "png"
OUTPUT_DIR = ROOT / "package" / "assets" / "agumon" / "session"
PREVIEW_PATH = ROOT / "art" / "agumon-states" / "agumon-state-animated-preview.gif"

SIZE = 128
FRAME_COUNT = 20
FRAME_DURATION_MS = 95
CHROMA_KEY = (255, 0, 255)
PREVIEW_BG = (15, 4, 8, 255)

STATE_NAMES = [
    "idle-koromon",
    "sleeping-koromon",
    "thinking-agumon",
    "notification-agumon",
    "working-greymon",
    "building-metalgreymon",
    "done-wargreymon",
    "error-skullgreymon",
]


def load_sprite(name: str) -> Image.Image:
    path = SOURCE_DIR / f"{name}.png"
    image = Image.open(path).convert("RGBA")
    if image.size != (SIZE, SIZE):
        raise ValueError(f"{path} must be {SIZE}x{SIZE}, got {image.size}")
    if image.getchannel("A").getbbox() is None:
        raise ValueError(f"{path} has no visible pixels")
    return image


def transformed(
    source: Image.Image,
    *,
    dx: int = 0,
    dy: int = 0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> Image.Image:
    """Transform only the visible sprite, preserving its original floor line."""
    bbox = source.getchannel("A").getbbox()
    if bbox is None:
        return Image.new("RGBA", source.size, (0, 0, 0, 0))
    subject = source.crop(bbox)
    width = max(1, round(subject.width * scale_x))
    height = max(1, round(subject.height * scale_y))
    if (width, height) != subject.size:
        subject = subject.resize((width, height), Image.Resampling.NEAREST)

    center_x = (bbox[0] + bbox[2]) / 2
    left = round(center_x - width / 2 + dx)
    top = round(bbox[3] - height + dy)
    canvas = Image.new("RGBA", source.size, (0, 0, 0, 0))
    canvas.alpha_composite(subject, (left, top))
    return canvas


def star(draw: ImageDraw.ImageDraw, x: int, y: int, color: tuple[int, int, int, int], radius: int) -> None:
    draw.rectangle((x - radius, y, x + radius, y + 1), fill=color)
    draw.rectangle((x, y - radius, x + 1, y + radius), fill=color)
    if radius >= 3:
        draw.point((x - 1, y - 1), fill=color)
        draw.point((x + 2, y + 2), fill=color)


def z_glyph(draw: ImageDraw.ImageDraw, x: int, y: int, scale: int, color: tuple[int, int, int, int]) -> None:
    draw.rectangle((x, y, x + 3 * scale - 1, y + scale - 1), fill=color)
    draw.rectangle((x + 2 * scale, y + scale, x + 3 * scale - 1, y + 2 * scale - 1), fill=color)
    draw.rectangle((x + scale, y + 2 * scale, x + 2 * scale - 1, y + 3 * scale - 1), fill=color)
    draw.rectangle((x, y + 3 * scale, x + 3 * scale - 1, y + 4 * scale - 1), fill=color)


def idle_frames(source: Image.Image) -> list[Image.Image]:
    frames = []
    for index in range(FRAME_COUNT):
        wave = math.sin(index * math.tau / FRAME_COUNT)
        frames.append(transformed(source, dy=round(-wave), scale_x=1.0 - 0.008 * wave, scale_y=1.0 + 0.018 * wave))
    return frames


def sleeping_frames(source: Image.Image) -> list[Image.Image]:
    frames = []
    for index in range(FRAME_COUNT):
        wave = math.sin(index * math.tau / FRAME_COUNT)
        frame = transformed(source, scale_x=1.0 + 0.01 * wave, scale_y=1.0 - 0.018 * wave)
        draw = ImageDraw.Draw(frame)
        drift = index // 4
        z_glyph(draw, 90 + drift, 25 - drift, 1, (244, 193, 167, 255))
        if index >= 7:
            z_glyph(draw, 105 + drift // 2, 12 - drift // 2, 1, (255, 243, 232, 255))
        frames.append(frame)
    return frames


def thinking_frames(source: Image.Image) -> list[Image.Image]:
    frames = []
    for index in range(FRAME_COUNT):
        wave = math.sin(index * math.tau / FRAME_COUNT)
        frame = transformed(source, dy=round(-1.5 * max(0.0, wave)))
        draw = ImageDraw.Draw(frame)
        pulse = 2 + (1 if index % 10 in (3, 4, 5, 6) else 0)
        star(draw, 91, 19, (255, 209, 102, 255), pulse)
        if index % 10 in (5, 6):
            star(draw, 102, 31, (244, 193, 167, 255), 1)
        frames.append(frame)
    return frames


def notification_frames(source: Image.Image) -> list[Image.Image]:
    bounce = [0, -2, -5, -8, -5, -2, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    frames = []
    for index in range(FRAME_COUNT):
        shake = (-1 if index % 2 else 1) if 2 <= index <= 7 else 0
        frame = transformed(source, dx=shake, dy=bounce[index])
        draw = ImageDraw.Draw(frame)
        if 1 <= index <= 8:
            color = (255, 209, 102, 255)
            draw.rectangle((105, 23, 108, 31), fill=color)
            draw.rectangle((106, 35, 108, 37), fill=color)
            draw.line((96, 27, 91, 23), fill=color, width=2)
            draw.line((115, 27, 121, 23), fill=color, width=2)
        frames.append(frame)
    return frames


def working_frames(source: Image.Image) -> list[Image.Image]:
    frames = []
    for index in range(FRAME_COUNT):
        wave = math.sin(index * math.tau / FRAME_COUNT)
        effects = Image.new("RGBA", source.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(effects)
        for lane in range(3):
            x = 8 + ((index * 7 + lane * 29) % 42)
            y = 47 + lane * 18
            draw.rectangle((x, y, x + 13 + lane * 3, y + 2), fill=(244, 193, 167, 210))
        frame = transformed(source, dx=round(2 * wave), dy=-1 if index % 4 in (1, 2) else 0)
        effects.alpha_composite(frame)
        frames.append(effects)
    return frames


def building_frames(source: Image.Image) -> list[Image.Image]:
    frames = []
    spark_positions = [(26, 101), (38, 91), (48, 108), (18, 87), (57, 97)]
    for index in range(FRAME_COUNT):
        strike = index % 10
        frame = transformed(source, dy=2 if strike in (4, 5) else 0)
        draw = ImageDraw.Draw(frame)
        if strike in (4, 5, 6):
            count = 5 if strike == 5 else 3
            for spark_index, (x, y) in enumerate(spark_positions[:count]):
                radius = 3 if spark_index == 0 else 1
                star(draw, x, y, (255, 209, 102, 255), radius)
        frames.append(frame)
    return frames


def done_frames(source: Image.Image) -> list[Image.Image]:
    frames = []
    for index in range(FRAME_COUNT):
        wave = math.sin(index * math.tau / FRAME_COUNT)
        frame = transformed(source, dy=round(-2 - 2 * wave), scale_x=1.0 - 0.008 * wave, scale_y=1.0 + 0.012 * wave)
        draw = ImageDraw.Draw(frame)
        star(draw, 102, 26, (255, 209, 102, 255), 3 if index % 10 < 5 else 1)
        star(draw, 25, 45, (143, 224, 199, 255), 2 if index % 10 >= 5 else 1)
        if index in (3, 4, 13, 14):
            star(draw, 111, 62, (255, 243, 232, 255), 2)
        frames.append(frame)
    return frames


def glitch_frame(frame: Image.Image, index: int) -> Image.Image:
    if index not in (3, 4, 10, 11, 16):
        return frame
    result = frame.copy()
    offsets = [(31, 4, 3), (55, -5, 4), (78, 3, 3), (96, -3, 2)]
    for y, dx, height in offsets:
        strip = result.crop((0, y, SIZE, min(SIZE, y + height)))
        ImageDraw.Draw(result).rectangle((0, y, SIZE - 1, min(SIZE - 1, y + height - 1)), fill=(0, 0, 0, 0))
        result.alpha_composite(strip, (dx, y))
    draw = ImageDraw.Draw(result)
    red = (255, 82, 82, 255)
    for lane in range(4):
        x = 9 + ((index * 17 + lane * 29) % 91)
        y = 24 + lane * 23
        draw.rectangle((x, y, x + 7 + lane * 2, y + 2), fill=red)
        draw.rectangle((x + 3, y + 4, x + 5, y + 5), fill=(120, 12, 20, 255))
    return result


def error_frames(source: Image.Image) -> list[Image.Image]:
    frames = []
    for index in range(FRAME_COUNT):
        jitter_x = (0, 1, 0, -1)[index % 4]
        jitter_y = -1 if index in (3, 10, 16) else 0
        frame = transformed(source, dx=jitter_x, dy=jitter_y)
        frames.append(glitch_frame(frame, index))
    return frames


ANIMATORS: dict[str, Callable[[Image.Image], list[Image.Image]]] = {
    "idle-koromon": idle_frames,
    "sleeping-koromon": sleeping_frames,
    "thinking-agumon": thinking_frames,
    "notification-agumon": notification_frames,
    "working-greymon": working_frames,
    "building-metalgreymon": building_frames,
    "done-wargreymon": done_frames,
    "error-skullgreymon": error_frames,
}


def rgba_to_fixed_palette(frames: list[Image.Image]) -> tuple[list[Image.Image], int]:
    """Quantize every frame against one palette so LVGL sees stable colors."""
    atlas = Image.new("RGB", (SIZE, SIZE * len(frames)), CHROMA_KEY)
    rgb_frames: list[Image.Image] = []
    alpha_frames: list[Image.Image] = []
    for index, frame in enumerate(frames):
        alpha = frame.getchannel("A")
        binary_alpha = alpha.point(lambda value: 255 if value >= 128 else 0)
        rgb = Image.new("RGB", frame.size, CHROMA_KEY)
        rgb.paste(frame.convert("RGB"), (0, 0), binary_alpha)
        atlas.paste(rgb, (0, index * SIZE))
        rgb_frames.append(rgb)
        alpha_frames.append(alpha)

    master = atlas.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette = master.getpalette()
    if palette is None:
        raise RuntimeError("failed to build GIF palette")
    palette_seed = Image.new("P", (1, 1))
    palette_seed.putpalette(palette)

    palette_size = len(palette) // 3
    transparency = min(
        range(palette_size),
        key=lambda index: sum(
            (palette[index * 3 + channel] - CHROMA_KEY[channel]) ** 2
            for channel in range(3)
        ),
    )

    indexed_frames: list[Image.Image] = []
    for rgb, alpha in zip(rgb_frames, alpha_frames):
        indexed = rgb.quantize(palette=palette_seed, dither=Image.Dither.NONE)
        transparent_mask = alpha.point(lambda value: 255 if value < 128 else 0)
        indexed.paste(transparency, (0, 0, SIZE, SIZE), transparent_mask)
        indexed_frames.append(indexed)
    return indexed_frames, transparency


def save_transparent_gif(path: Path, frames: list[Image.Image]) -> None:
    indexed, transparency = rgba_to_fixed_palette(frames)
    indexed[0].save(
        path,
        save_all=True,
        append_images=indexed[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        transparency=transparency,
        disposal=2,
        optimize=False,
    )


def save_preview(animations: dict[str, list[Image.Image]]) -> None:
    preview_frames = []
    for frame_index in range(FRAME_COUNT):
        frame = Image.new("RGBA", (SIZE * 4, SIZE * 2), PREVIEW_BG)
        for state_index, name in enumerate(STATE_NAMES):
            x = (state_index % 4) * SIZE
            y = (state_index // 4) * SIZE
            frame.alpha_composite(animations[name][frame_index], (x, y))
        preview_frames.append(frame.convert("RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT))
    preview_frames[0].save(
        PREVIEW_PATH,
        save_all=True,
        append_images=preview_frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        disposal=2,
        optimize=False,
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    animations: dict[str, list[Image.Image]] = {}
    for name in STATE_NAMES:
        frames = ANIMATORS[name](load_sprite(name))
        if len(frames) != FRAME_COUNT:
            raise ValueError(f"{name} generated {len(frames)} frames, expected {FRAME_COUNT}")
        path = OUTPUT_DIR / f"{name}.gif"
        save_transparent_gif(path, frames)
        animations[name] = frames
        print(f"{path.relative_to(ROOT)}\t{path.stat().st_size} bytes")
    save_preview(animations)
    print(f"{PREVIEW_PATH.relative_to(ROOT)}\t{PREVIEW_PATH.stat().st_size} bytes")


if __name__ == "__main__":
    main()
