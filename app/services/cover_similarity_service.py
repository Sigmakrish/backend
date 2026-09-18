from io import BytesIO

import requests

from PIL import (
    Image,
    ImageOps,
    ImageEnhance,
)

import imagehash


# ============================================================
# IMAGE DOWNLOAD
# ============================================================

def download_image(url: str) -> Image.Image | None:
    """
    Download a candidate cover image.
    """

    if not url:
        return None

    try:
        response = requests.get(
            url,
            timeout=8,
            headers={
                "User-Agent": "RareBookAI/1.0"
            }
        )

        response.raise_for_status()

        image = Image.open(
            BytesIO(response.content)
        )

        # Correct rotated images using EXIF data
        image = ImageOps.exif_transpose(
            image
        )

        return image.convert("RGB")

    except Exception as e:

        print(
            f"Cover download error: {e}"
        )

        return None


# ============================================================
# RESIZE IMAGE
# ============================================================

def resize_image(
    image: Image.Image,
    max_size: int = 1200
) -> Image.Image:
    """
    Resize large images while keeping aspect ratio.
    """

    image = image.copy()

    image.thumbnail(
        (max_size, max_size),
        Image.Resampling.LANCZOS
    )

    return image


# ============================================================
# CREATE IMAGE VARIANTS
# ============================================================

def create_image_variants(
    image: Image.Image
) -> list[Image.Image]:
    """
    Create multiple versions of an image.

    This helps when the uploaded image is:
    - hazy
    - low contrast
    - slightly blurry
    - cropped
    - photographed under poor lighting
    """

    image = ImageOps.exif_transpose(
        image
    ).convert("RGB")

    image = resize_image(
        image
    )

    variants = []

    # --------------------------------------------------------
    # 1. Original
    # --------------------------------------------------------

    variants.append(
        image
    )

    # --------------------------------------------------------
    # 2. Auto contrast
    # --------------------------------------------------------

    auto_contrast = ImageOps.autocontrast(
        image
    )

    variants.append(
        auto_contrast
    )

    # --------------------------------------------------------
    # 3. Sharpened
    # --------------------------------------------------------

    sharpened = ImageEnhance.Sharpness(
        image
    ).enhance(2.0)

    variants.append(
        sharpened
    )

    # --------------------------------------------------------
    # 4. Increased contrast
    # --------------------------------------------------------

    high_contrast = ImageEnhance.Contrast(
        image
    ).enhance(1.5)

    variants.append(
        high_contrast
    )

    # --------------------------------------------------------
    # 5. Grayscale
    # --------------------------------------------------------

    grayscale = ImageOps.grayscale(
        image
    ).convert("RGB")

    variants.append(
        grayscale
    )

    # --------------------------------------------------------
    # 6. Sharpen + auto contrast
    # --------------------------------------------------------

    enhanced = ImageEnhance.Sharpness(
        auto_contrast
    ).enhance(2.0)

    variants.append(
        enhanced
    )

    # --------------------------------------------------------
    # 7. Center crop - 90%
    # --------------------------------------------------------

    width, height = image.size

    crop_ratio = 0.90

    crop_width = int(
        width * crop_ratio
    )

    crop_height = int(
        height * crop_ratio
    )

    left = (
        width - crop_width
    ) // 2

    top = (
        height - crop_height
    ) // 2

    center_crop_90 = image.crop(
        (
            left,
            top,
            left + crop_width,
            top + crop_height
        )
    )

    variants.append(
        center_crop_90
    )

    # --------------------------------------------------------
    # 8. Center crop - 75%
    # --------------------------------------------------------

    crop_ratio = 0.75

    crop_width = int(
        width * crop_ratio
    )

    crop_height = int(
        height * crop_ratio
    )

    left = (
        width - crop_width
    ) // 2

    top = (
        height - crop_height
    ) // 2

    center_crop_75 = image.crop(
        (
            left,
            top,
            left + crop_width,
            top + crop_height
        )
    )

    variants.append(
        center_crop_75
    )

    return variants


# ============================================================
# HASH SIMILARITY
# ============================================================

def hash_similarity(
    image1: Image.Image,
    image2: Image.Image
) -> float:
    """
    Calculate visual similarity between two images.

    Uses:
    - pHash
    - dHash

    Returns:
        0 to 100
    """

    try:

        # ----------------------------------------------------
        # Perceptual hash
        # ----------------------------------------------------

        phash1 = imagehash.phash(
            image1
        )

        phash2 = imagehash.phash(
            image2
        )

        phash_distance = (
            phash1 - phash2
        )

        phash_score = max(
            0,
            100
            - (
                phash_distance
                * 100
                / 64
            )
        )

        # ----------------------------------------------------
        # Difference hash
        # ----------------------------------------------------

        dhash1 = imagehash.dhash(
            image1
        )

        dhash2 = imagehash.dhash(
            image2
        )

        dhash_distance = (
            dhash1 - dhash2
        )

        dhash_score = max(
            0,
            100
            - (
                dhash_distance
                * 100
                / 64
            )
        )

        # ----------------------------------------------------
        # Combined score
        #
        # pHash is more important because it captures
        # overall visual structure.
        # ----------------------------------------------------

        final_score = (
            phash_score * 0.70
            + dhash_score * 0.30
        )

        return round(
            final_score,
            2
        )

    except Exception as e:

        print(
            f"Hash comparison error: {e}"
        )

        return 0.0


# ============================================================
# COVER SIMILARITY
# ============================================================

def calculate_cover_similarity(
    uploaded_image: Image.Image,
    cover_url: str | None
) -> float | None:
    """
    Compare the uploaded book image with a candidate
    catalog cover.

    Multiple image variants are tested to handle:
    - hazy photos
    - low contrast
    - blur
    - cropping
    - lighting differences

    Returns:
        Similarity score from 0 to 100.
    """

    if uploaded_image is None:
        return None

    if not cover_url:
        return None

    # ========================================================
    # DOWNLOAD CANDIDATE COVER
    # ========================================================

    candidate_image = download_image(
        cover_url
    )

    if candidate_image is None:
        return None

    # ========================================================
    # CREATE VARIANTS
    # ========================================================

    uploaded_variants = (
        create_image_variants(
            uploaded_image
        )
    )

    candidate_variants = (
        create_image_variants(
            candidate_image
        )
    )

    # ========================================================
    # COMPARE ALL VARIANTS
    # ========================================================

    best_score = 0.0

    for uploaded_variant in uploaded_variants:

        for candidate_variant in candidate_variants:

            score = hash_similarity(
                uploaded_variant,
                candidate_variant
            )

            if score > best_score:
                best_score = score

    # ========================================================
    # RETURN BEST SCORE
    # ========================================================

    return round(
        best_score,
        2
    )