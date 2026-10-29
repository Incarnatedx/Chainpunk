"""Conservative visual matching for Chain Punks artwork."""
import io
import json
from pathlib import Path

from PIL import Image, ImageOps

INDEX_VERSION = 2
SIZE = 16
HASH_BITS = SIZE * SIZE * 2
MAX_DISTANCE = 40
MIN_MARGIN = 8


def fingerprint(image):
    """Create a 512-bit grayscale average/difference hash for an artwork image."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    resampling = Image.Resampling.LANCZOS

    average = ImageOps.fit(image, (SIZE, SIZE), method=resampling).convert("L")
    avg_values = list(average.getdata())
    avg_mean = sum(avg_values) / len(avg_values)
    avg_bits = [pixel >= avg_mean for pixel in avg_values]

    gradient = ImageOps.fit(image, (SIZE + 1, SIZE), method=resampling).convert("L")
    grad_values = list(gradient.getdata())
    diff_bits = [
        grad_values[row * (SIZE + 1) + col]
        > grad_values[row * (SIZE + 1) + col + 1]
        for row in range(SIZE)
        for col in range(SIZE)
    ]

    bits = diff_bits + avg_bits
    return f"{int(''.join('1' if bit else '0' for bit in bits), 2):0{HASH_BITS // 4}x}"


def load_index(path):
    """Load {token_id: fingerprint}; return an empty mapping if no file exists."""
    path = Path(path)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != INDEX_VERSION:
        return {}
    fingerprints = payload.get("fingerprints")
    if not isinstance(fingerprints, dict):
        raise ValueError("Invalid artwork index")
    return {int(token_id): value for token_id, value in fingerprints.items()}


def save_index(path, fingerprints):
    """Write the index atomically so interrupted builds can safely resume."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "version": INDEX_VERSION,
        "fingerprints": {
            str(token_id): fingerprints[token_id]
            for token_id in sorted(fingerprints)
        },
    }
    temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def _photo_variants(image):
    """Try centered square crops to tolerate borders and modest framing differences."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    side = min(width, height)
    center_x, center_y = width / 2, height / 2
    for scale in (1.0, 0.88, 0.76):
        crop_side = max(1, int(side * scale))
        left = int(center_x - crop_side / 2)
        top = int(center_y - crop_side / 2)
        yield image.crop((left, top, left + crop_side, top + crop_side))


def match_image(image_bytes, fingerprints, max_distance=MAX_DISTANCE, min_margin=MIN_MARGIN):
    """Return match, ambiguous, or no-match without forcing a weak visual guess."""
    if not fingerprints:
        return {"status": "no-match"}

    with Image.open(io.BytesIO(image_bytes)) as image:
        candidates = {
            fingerprint(variant)
            for variant in _photo_variants(image)
        }

    ranked = []
    for token_id, reference in fingerprints.items():
        try:
            reference_int = int(reference, 16)
        except (TypeError, ValueError):
            continue
        distance = min(
            (int(candidate, 16) ^ reference_int).bit_count()
            for candidate in candidates
        )
        ranked.append((distance, int(token_id)))

    if not ranked:
        return {"status": "no-match"}
    ranked.sort()
    best_distance, best_id = ranked[0]
    second_distance = ranked[1][0] if len(ranked) > 1 else HASH_BITS

    if best_distance > max_distance:
        return {"status": "no-match"}
    if second_distance - best_distance < min_margin:
        return {"status": "ambiguous"}
    return {
        "status": "match",
        "token_id": best_id,
        "distance": best_distance,
    }
