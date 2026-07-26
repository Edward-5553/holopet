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
WORKING_KEYFRAMES_PATH = SOURCE_DIR / "working-greymon-keyframes.png"
BUILDING_KEYFRAMES_PATH = SOURCE_DIR / "building-metalgreymon-keyframes.png"

# Existing source art is 128 x 128, while every runtime GIF uses the fixed
# portrait canvas reserved by the session UI. Keeping these dimensions separate
# lets future wide or tall frame sequences share the same display area without
# being stretched.
SIZE = 128
CANVAS_WIDTH = 130
CANVAS_HEIGHT = 180
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

SOURCE_SIZES = {
    "thinking-agumon": (CANVAS_WIDTH, CANVAS_HEIGHT),
    "notification-agumon": (CANVAS_WIDTH, CANVAS_HEIGHT),
}

POSE_NAMES = {
    "thinking-agumon-ponder",
    "thinking-agumon-idea",
    "notification-agumon-wait",
    "notification-agumon-prompt",
}

# The approved working animation is stored as a 2 x 2 contact sheet. These
# bounds omit the outer frame and the center divider drawn by image generation.
WORKING_KEYFRAME_BOXES = (
    (4, 4, 529, 736),
    (534, 4, 1060, 736),
    (4, 742, 529, 1474),
    (534, 742, 1060, 1474),
)


# MetalGreymon's build animation is a 2 x 2 portrait contact sheet: crouch,
# chest bays open, missile launch, then recovery. The source panels are taller
# than wide so the character fits the fixed session display without clipping.
BUILDING_KEYFRAME_BOXES = (
    (0, 0, 532, 738),
    (533, 0, 1065, 738),
    (0, 739, 532, 1477),
    (533, 739, 1065, 1477),
)
# Limited-animation timing: effort, charge, fireball, and recoil. Repeating
# poses provides deliberate holds while one-pixel offsets add breathing,
# charging tension, impact shake, and recovery motion.
WORKING_TIMELINE = (
    (0, 0, 0),
    (0, 0, -1),
    (0, 0, 0),
    (0, 0, 1),
    (1, 0, 1),
    (1, 0, 0),
    (1, 0, -1),
    (1, 0, 0),
    (2, -1, 0),
    (2, 1, 0),
    (2, -1, 0),
    (3, 1, 0),
    (3, 0, 0),
    (3, -1, 0),
    (3, 0, 0),
    (3, 0, 1),
    (0, 0, 1),
    (0, 0, 0),
    (0, 0, -1),
    (0, 0, 0),
)
BUILDING_TIMELINE = (
    (0, 0, 0), (0, 0, 1), (0, 0, 0), (0, 0, 0),
    (1, 0, 0), (1, 0, -1), (1, 0, 0), (1, 0, 0),
    (2, -1, 1), (2, 1, 0), (2, -1, 0), (2, 1, 1),
    (3, 0, 1), (3, 0, 0), (3, 0, 0), (3, 0, -1),
    (0, 0, 0), (0, 0, 0), (0, 0, 1), (0, 0, 0),
)



def load_sprite(name: str) -> Image.Image:
    path = SOURCE_DIR / f"{name}.png"
    image = Image.open(path).convert("RGBA")
    expected_size = SOURCE_SIZES.get(name, (SIZE, SIZE))
    if image.size != expected_size:
        raise ValueError(f"{path} must be {expected_size[0]}x{expected_size[1]}, got {image.size}")
    if image.getchannel("A").getbbox() is None:
        raise ValueError(f"{path} has no visible pixels")
    return image


def load_pose(name: str) -> Image.Image:
    if name not in POSE_NAMES:
        raise ValueError(f"unknown animation pose: {name}")
    path = SOURCE_DIR / f"{name}.png"
    image = Image.open(path).convert("RGBA")
    if image.size != (CANVAS_WIDTH, CANVAS_HEIGHT):
        raise ValueError(
            f"{path} must be {CANVAS_WIDTH}x{CANVAS_HEIGHT}, got {image.size}"
        )
    if image.getchannel("A").getbbox() is None:
        raise ValueError(f"{path} has no visible pixels")
    return image


def load_working_keyframes() -> list[Image.Image]:
    image = Image.open(WORKING_KEYFRAMES_PATH).convert("RGBA")
    if image.size != (1064, 1478):
        raise ValueError(
            f"{WORKING_KEYFRAMES_PATH} must be 1064x1478, got "
            f"{image.width}x{image.height}"
        )
    frames = [
        fit_to_session_canvas(image.crop(box), padding=2)
        for box in WORKING_KEYFRAME_BOXES
    ]
    if any(frame.getchannel("A").getbbox() is None for frame in frames):
        raise ValueError(f"{WORKING_KEYFRAMES_PATH} contains an empty keyframe")
    return frames

def load_building_keyframes() -> list[Image.Image]:
    image = Image.open(BUILDING_KEYFRAMES_PATH).convert("RGBA")
    if image.size != (1065, 1477):
        raise ValueError(
            f"{BUILDING_KEYFRAMES_PATH} must be 1065x1477, got "
            f"{image.width}x{image.height}"
        )
    frames = [fit_to_session_canvas(image.crop(box)) for box in BUILDING_KEYFRAME_BOXES]
    if any(frame.getchannel("A").getbbox() is None for frame in frames):
        raise ValueError(f"{BUILDING_KEYFRAMES_PATH} contains an empty keyframe")

    return frames
def offset_opaque_frame(frame: Image.Image, dx: int, dy: int) -> Image.Image:
    """Move a full-panel keyframe while extending its sampled dark backdrop."""
    backdrop = frame.getpixel((0, 0))
    result = Image.new("RGBA", frame.size, backdrop)
    result.alpha_composite(frame, (dx, dy))
    return result


def transformed(
    source: Image.Image,
    *,
    dx: int = 0,
    dy: int = 0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    resample: Image.Resampling = Image.Resampling.NEAREST,
) -> Image.Image:
    """Transform only the visible sprite, preserving its original floor line."""
    bbox = source.getchannel("A").getbbox()
    if bbox is None:
        return Image.new("RGBA", source.size, (0, 0, 0, 0))
    subject = source.crop(bbox)
    width = max(1, round(subject.width * scale_x))
    height = max(1, round(subject.height * scale_y))
    if (width, height) != subject.size:
        subject = subject.resize((width, height), resample)

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
    # A calm, readable hop: pause, anticipate, lift, land, settle, then pause.
    # The source is smooth line art, so use high-quality resampling for the
    # squash-and-stretch frames while keeping every other pixel-art state crisp.
    poses = [
        (0, 1.00, 1.00),
        (0, 1.00, 1.00),
        (0, 1.00, 1.00),
        (0, 1.00, 1.00),
        (1, 1.02, 0.97),
        (2, 1.05, 0.92),
        (-2, 0.98, 1.05),
        (-6, 0.98, 1.04),
        (-10, 0.99, 1.02),
        (-13, 1.00, 1.00),
        (-12, 1.00, 1.00),
        (-9, 1.00, 1.00),
        (-5, 0.99, 1.02),
        (-1, 0.99, 1.03),
        (0, 1.06, 0.91),
        (-1, 0.98, 1.04),
        (0, 1.02, 0.97),
        (0, 1.00, 1.00),
        (0, 1.00, 1.00),
        (0, 1.00, 1.00),
    ]
    return [
        transformed(
            source,
            dy=dy,
            scale_x=scale_x,
            scale_y=scale_y,
            resample=Image.Resampling.LANCZOS,
        )
        for dy, scale_x, scale_y in poses
    ]


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
    ponder = load_pose("thinking-agumon-ponder")
    idea = load_pose("thinking-agumon-idea")
    poses = (
        [source] * 4
        + [ponder] * 6
        + [source] * 2
        + [idea] * 4
        + [source] * 4
    )
    frames = []
    for index, pose in enumerate(poses):
        frame = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame)
        pulse = 1 if index % 4 in (0, 3) else 2
        draw.ellipse((5, 63, 5 + pulse, 63 + pulse), fill=(244, 193, 167, 255))
        draw.ellipse((119, 112, 121, 114), fill=(143, 224, 199, 255))
        if 4 <= index <= 9:
            draw.ellipse((16, 39, 19, 42), fill=(244, 193, 167, 255))
            draw.ellipse((9, 28, 14, 33), fill=(255, 243, 232, 255))
            star(draw, 16, 17, (255, 209, 102, 255), 2 + (index % 2))
        elif 12 <= index <= 15:
            star(draw, 114, 20, (255, 209, 102, 255), 4 if index in (13, 14) else 3)
            star(draw, 120, 50, (255, 243, 232, 255), 2)
            draw.ellipse((7, 91, 10, 94), fill=(143, 224, 199, 255))
        else:
            draw.ellipse((11, 31, 14, 34), fill=(255, 243, 232, 255))
            draw.ellipse((17, 22, 21, 26), fill=(244, 193, 167, 255))
        frame.alpha_composite(pose)
        frames.append(frame)
    return frames


def notification_frames(source: Image.Image) -> list[Image.Image]:
    waiting = load_pose("notification-agumon-wait")
    prompt = load_pose("notification-agumon-prompt")
    poses = (
        [source] * 4
        + [waiting] * 4
        + [source] * 2
        + [prompt] * 5
        + [waiting] * 2
        + [source] * 3
    )
    frames = []
    for index, pose in enumerate(poses):
        frame = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame)
        dim = (169, 77, 55, 255)
        bright = (255, 209, 102, 255)
        draw.rectangle((5, 34, 7, 36), fill=bright if index % 4 < 2 else dim)
        draw.rectangle((120, 102, 122, 104), fill=dim)
        draw.rectangle((8, 145, 9, 146), fill=(143, 224, 199, 255))
        if 4 <= index <= 7 or 15 <= index <= 16:
            draw.ellipse((8, 25, 11, 28), fill=(244, 193, 167, 255))
            draw.ellipse((14, 19, 18, 23), fill=(255, 243, 232, 255))
            draw.arc((3, 47, 21, 65), 105, 255, fill=dim, width=2)
        elif 10 <= index <= 14:
            draw.arc((3, 21, 28, 46), 105, 255, fill=bright, width=2)
            draw.arc((7, 25, 24, 42), 105, 255, fill=(244, 193, 167, 255), width=2)
            star(draw, 115, 18, bright, 3 + (index % 2))
            star(draw, 121, 61, (255, 243, 232, 255), 2)
        else:
            draw.line((112, 22, 118, 16), fill=bright, width=2)
            draw.line((118, 31, 126, 31), fill=bright, width=2)
            draw.line((113, 40, 120, 46), fill=bright, width=2)
        frame.alpha_composite(pose)
        frames.append(frame)
    return frames


def working_frames(source: Image.Image) -> list[Image.Image]:
    del source  # This state uses the approved multi-pose artwork instead.
    keyframes = load_working_keyframes()
    return [
        offset_opaque_frame(keyframes[pose_index], dx, dy)
        for pose_index, dx, dy in WORKING_TIMELINE
    ]


def building_backdrop(index: int) -> Image.Image:
    frame = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)
    scan_y = 18 + (index * 13) % 142
    draw.line((6, scan_y, 20, scan_y), fill=(143, 224, 199, 96), width=1)
    draw.line((109, 180 - scan_y, 124, 180 - scan_y), fill=(244, 193, 167, 96), width=1)
    for lane in range(3):
        y = 20 + lane * 19
        width = 5 + ((index + lane) % 3) * 3
        draw.rectangle((7, y, 7 + width, y + 1), fill=(143, 224, 199, 110))
        draw.rectangle((116 - width, y + 9, 116, y + 10), fill=(244, 193, 167, 110))
    for spark_index in range(4):
        x = 11 + (index * 17 + spark_index * 29) % 108
        y = 26 + (index * 11 + spark_index * 37) % 120
        star(draw, x, y, (255, 209, 102, 168), 2 if spark_index == index % 4 else 1)
    return frame


def building_frames(source: Image.Image) -> list[Image.Image]:
    del source  # This state uses the purpose-drawn multi-pose artwork instead.
    keyframes = load_building_keyframes()
    frames = []
    for index, (pose_index, dx, dy) in enumerate(BUILDING_TIMELINE):
        frame = offset_opaque_frame(keyframes[pose_index], dx, dy)
        backdrop = building_backdrop(index)
        backdrop.alpha_composite(frame)
        frames.append(backdrop)
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
    if not frames:
        raise ValueError("cannot quantize an empty animation")
    frame_size = frames[0].size
    if any(frame.size != frame_size for frame in frames):
        raise ValueError("all animation frames must use the same canvas size")
    width, height = frame_size
    atlas = Image.new("RGB", (width, height * len(frames)), CHROMA_KEY)
    rgb_frames: list[Image.Image] = []
    alpha_frames: list[Image.Image] = []
    for index, frame in enumerate(frames):
        alpha = frame.getchannel("A")
        binary_alpha = alpha.point(lambda value: 255 if value >= 128 else 0)
        rgb = Image.new("RGB", frame.size, CHROMA_KEY)
        rgb.paste(frame.convert("RGB"), (0, 0), binary_alpha)
        atlas.paste(rgb, (0, index * height))
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
        indexed.paste(transparency, (0, 0, width, height), transparent_mask)
        indexed_frames.append(indexed)
    return indexed_frames, transparency


def fit_to_session_canvas(frame: Image.Image, padding: int = 0) -> Image.Image:
    """Center one frame on the 130 x 180 session canvas without distortion."""
    frame = frame.convert("RGBA")
    if padding < 0 or padding * 2 >= min(CANVAS_WIDTH, CANVAS_HEIGHT):
        raise ValueError(f"invalid session canvas padding: {padding}")
    available_width = CANVAS_WIDTH - padding * 2
    available_height = CANVAS_HEIGHT - padding * 2
    if frame.width > available_width or frame.height > available_height:
        scale = min(available_width / frame.width, available_height / frame.height)
        fitted_size = (
            max(1, round(frame.width * scale)),
            max(1, round(frame.height * scale)),
        )
        frame = frame.resize(fitted_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    left = (CANVAS_WIDTH - frame.width) // 2
    top = (CANVAS_HEIGHT - frame.height) // 2
    canvas.alpha_composite(frame, (left, top))
    return canvas


def save_transparent_gif(path: Path, frames: list[Image.Image]) -> None:
    fitted_frames = [fit_to_session_canvas(frame) for frame in frames]
    indexed, transparency = rgba_to_fixed_palette(fitted_frames)
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
    fitted = {
        name: [fit_to_session_canvas(frame) for frame in frames]
        for name, frames in animations.items()
    }
    preview_frames = []
    for frame_index in range(FRAME_COUNT):
        frame = Image.new(
            "RGBA",
            (CANVAS_WIDTH * 4, CANVAS_HEIGHT * 2),
            PREVIEW_BG,
        )
        for state_index, name in enumerate(STATE_NAMES):
            x = (state_index % 4) * CANVAS_WIDTH
            y = (state_index // 4) * CANVAS_HEIGHT
            frame.alpha_composite(fitted[name][frame_index], (x, y))
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
