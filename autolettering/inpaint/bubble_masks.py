from __future__ import annotations

from statistics import median

from PIL import Image, ImageDraw, ImageFilter


def bubble_region_cleanup_mask(
    source: Image.Image,
    bbox: tuple[int, int, int, int],
    region: tuple[int, int, int, int],
    fill_color: tuple[int, int, int],
) -> Image.Image:
    crop = source.crop(bbox)
    local_region = _clip_bbox(_offset_bbox(region, bbox), crop.size)
    if local_region is None:
        return Image.new("L", crop.size, 0)

    background_like = _background_like_pixels(crop, local_region, fill_color)
    mask = Image.new("L", crop.size, 0)
    pixels = mask.load()
    lx1, ly1, lx2, ly2 = local_region

    for y in range(ly1, ly2):
        for x in range(lx1, lx2):
            if background_like[y][x]:
                pixels[x, y] = 255

    visited: set[tuple[int, int]] = set()
    for y in range(ly1, ly2):
        for x in range(lx1, lx2):
            if background_like[y][x] or (x, y) in visited:
                continue
            component = _connected_foreground_component(background_like, local_region, x, y, visited)
            if not _looks_like_external_art_component(component, local_region):
                for px, py in component:
                    pixels[px, py] = 255
    return mask


def bubble_fill_color(source: Image.Image, region: tuple[int, int, int, int]) -> tuple[int, int, int] | None:
    clipped = _clip_bbox(region, source.size)
    if clipped is None:
        return None
    pixels = [
        source.getpixel((x, y))
        for y in range(clipped[1], clipped[3])
        for x in range(clipped[0], clipped[2])
        if _luma(source.getpixel((x, y))) >= 245
    ]
    if not pixels:
        return None
    return tuple(int(median(channel)) for channel in zip(*pixels))


def soft_region_mask(
    size: tuple[int, int],
    region: tuple[int, int, int, int],
    feather_px: int,
) -> Image.Image:
    hard = Image.new("L", size, 0)
    ImageDraw.Draw(hard).rectangle(region, fill=255)
    if feather_px <= 0:
        return hard
    blurred = hard.filter(ImageFilter.GaussianBlur(radius=feather_px))
    core = _shrink_bbox(region, feather_px)
    if core is not None:
        ImageDraw.Draw(blurred).rectangle(core, fill=255)
    mask = blurred.point(lambda value: 0 if value < 16 else value, mode="L")
    if core is None:
        ImageDraw.Draw(mask).rectangle(region, fill=255)
    return mask


def _background_like_pixels(
    crop: Image.Image,
    region: tuple[int, int, int, int],
    fill_color: tuple[int, int, int],
    tolerance: int = 12,
) -> list[list[bool]]:
    width, height = crop.size
    rows = [[False for _ in range(width)] for _ in range(height)]
    lx1, ly1, lx2, ly2 = region
    min_luma = max(245, _luma(fill_color) - tolerance)
    for y in range(ly1, ly2):
        for x in range(lx1, lx2):
            pixel = crop.getpixel((x, y))
            if _luma(pixel) >= min_luma and all(abs(pixel[index] - fill_color[index]) <= tolerance for index in range(3)):
                rows[y][x] = True
    return rows


def _connected_foreground_component(
    background_like: list[list[bool]],
    region: tuple[int, int, int, int],
    start_x: int,
    start_y: int,
    visited: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    lx1, ly1, lx2, ly2 = region
    stack = [(start_x, start_y)]
    visited.add((start_x, start_y))
    component: list[tuple[int, int]] = []
    while stack:
        x, y = stack.pop()
        component.append((x, y))
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < lx1 or nx >= lx2 or ny < ly1 or ny >= ly2:
                continue
            if background_like[ny][nx] or (nx, ny) in visited:
                continue
            visited.add((nx, ny))
            stack.append((nx, ny))
    return component


def _looks_like_external_art_component(
    component: list[tuple[int, int]],
    bbox: tuple[int, int, int, int],
) -> bool:
    if not _component_touches_bbox_edge(component, bbox):
        return False
    component_bbox = _component_bbox(component)
    width = component_bbox[2] - component_bbox[0]
    height = component_bbox[3] - component_bbox[1]
    fill_ratio = len(component) / max(1, width * height)
    return fill_ratio <= 0.45 and max(width, height) >= min(width, height) * 2.2


def _component_touches_bbox_edge(
    component: list[tuple[int, int]],
    bbox: tuple[int, int, int, int],
) -> bool:
    lx1, ly1, lx2, ly2 = bbox
    return any(x in {lx1, lx2 - 1} or y in {ly1, ly2 - 1} for x, y in component)


def _component_bbox(component: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    xs = [x for x, _ in component]
    ys = [y for _, y in component]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def _shrink_bbox(
    bbox: tuple[int, int, int, int],
    inset: int,
) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = bbox
    core = x1 + inset, y1 + inset, x2 - inset, y2 - inset
    if core[0] >= core[2] or core[1] >= core[3]:
        return None
    return core


def _offset_bbox(
    inner: tuple[int, int, int, int],
    outer: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = inner
    ox1, oy1, _, _ = outer
    return x1 - ox1, y1 - oy1, x2 - ox1, y2 - oy1


def _clip_bbox(
    bbox: tuple[int, int, int, int],
    image_size: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = bbox
    width, height = image_size
    clipped = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
    if clipped[0] >= clipped[2] or clipped[1] >= clipped[3]:
        return None
    return clipped


def _luma(pixel: tuple[int, int, int]) -> int:
    return int(round(pixel[0] * 0.299 + pixel[1] * 0.587 + pixel[2] * 0.114))
