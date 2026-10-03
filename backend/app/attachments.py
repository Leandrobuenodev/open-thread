"""Private local image storage. Only generated references cross the storage boundary."""

import io
import re
import warnings

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 16_000_000
ALLOWED = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


def validate_image(raw, declared_type, filename):
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(413, "Image exceeds the 2 MiB limit.")
    if declared_type not in ALLOWED.values():
        raise HTTPException(415, "Only PNG, JPEG and WebP images are supported.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if (
                    ALLOWED.get(image.format) != declared_type
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise ValueError("Unsupported image")
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError("Image dimensions too large")
                image.load()
                image = ImageOps.exif_transpose(image).convert("RGB")
                # GPT-4.1 mini patch cost <= ceil(64 * 1.62) = 104 tokens.
                image.thumbnail((256, 256))
                output = io.BytesIO()
                image.save(output, format="PNG")
                width, height = image.size
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(415, "Invalid, animated or oversized image.") from None
    safe_name = (
        re.sub(r"[^\w. -]", "_", filename.replace("\\", "/").split("/")[-1])[
            :120
        ].strip(" .")
        or "image"
    )
    return output.getvalue(), safe_name, width, height
