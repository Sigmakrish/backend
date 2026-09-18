import io
import os
import re
from typing import Optional

import httpx


# ============================================================
# FETCH FULL TEXT
# ============================================================

async def fetch_fulltext(url: str) -> Optional[dict]:
    """
    Fetch legally accessible full-text content from a supplied URL.
    """

    if not url:
        return {
            "success": False,
            "error": "No full-text URL provided."
        }

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0
        ) as client:

            response = await client.get(url)

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }

            content_type = (
                response.headers.get("content-type", "")
                .lower()
            )

            content = response.content

            # ------------------------------------------------
            # Plain text
            # ------------------------------------------------

            if "text/plain" in content_type:
                text = content.decode(
                    "utf-8",
                    errors="ignore"
                )

                return {
                    "success": True,
                    "content_type": "text",
                    "text": clean_text(text),
                    "source_url": url
                }

            # ------------------------------------------------
            # HTML
            # ------------------------------------------------

            if "text/html" in content_type:
                text = extract_html_text(content)

                return {
                    "success": True,
                    "content_type": "html",
                    "text": clean_text(text),
                    "source_url": url
                }

            # ------------------------------------------------
            # PDF
            # ------------------------------------------------

            if (
                "application/pdf" in content_type
                or url.lower().endswith(".pdf")
            ):
                text = extract_pdf_text(content)

                if not text.strip():
                    return {
                        "success": False,
                        "error": (
                            "PDF appears to be scanned or "
                            "contains no extractable text. "
                            "Gemini OCR is required."
                        ),
                        "content_type": "pdf_scanned",
                        "source_url": url,
                        "pdf_bytes": content
                    }

                return {
                    "success": True,
                    "content_type": "pdf",
                    "text": clean_text(text),
                    "source_url": url
                }

            return {
                "success": False,
                "error": (
                    f"Unsupported content type: {content_type}"
                )
            }

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Full-text request timed out."
        }

    except httpx.HTTPError as exc:
        return {
            "success": False,
            "error": f"HTTP error: {str(exc)}"
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"Unexpected error: {str(exc)}"
        }


# ============================================================
# HTML EXTRACTION
# ============================================================

def extract_html_text(content: bytes) -> str:
    """
    Extract readable text from HTML.
    """

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        content,
        "html.parser"
    )

    for element in soup(
        ["script", "style", "nav", "footer", "header"]
    ):
        element.decompose()

    return soup.get_text(
        separator="\n"
    )


# ============================================================
# PDF TEXT EXTRACTION
# ============================================================

def extract_pdf_text(content: bytes) -> str:
    """
    Extract text from a text-based PDF.

    Scanned or badly encoded PDFs may return
    little or garbled text and can later be
    processed using Gemini OCR.
    """

    try:
        from pypdf import PdfReader

        reader = PdfReader(
            io.BytesIO(content)
        )

        pages = []

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                pages.append(page_text)

        return "\n\n".join(pages)

    except Exception:
        return ""


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:
    """
    Normalize extracted text before chunking.
    """

    if not text:
        return ""

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# ============================================================
# GEMINI OCR
# ============================================================

async def gemini_ocr_image(
    image_bytes: bytes,
    mime_type: str = "image/png"
) -> dict:
    """
    Use Gemini Vision to extract text from a page image.

    This is an alternative to Tesseract and is
    particularly useful for scanned or legacy-font PDFs.
    """

    if not image_bytes:
        return {
            "success": False,
            "error": "No image data provided."
        }

    try:
        from google import genai
        from google.genai import types

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            return {
                "success": False,
                "error": "GEMINI_API_KEY is not configured."
            }

        client = genai.Client(
            api_key=api_key
        )

        prompt = """
You are performing OCR on a historical or rare-book page.

Extract the visible text from this page as accurately as possible.

Important instructions:

1. Preserve the original language.
2. Preserve the original script.
3. Do not translate the text.
4. Do not summarize.
5. Do not invent missing words.
6. Preserve paragraph breaks where possible.
7. Preserve headings and section structure.
8. If the page contains Hindi, Bengali, Sanskrit,
   Urdu, or another Indic language, reproduce the
   actual script rather than transliterating it.
9. If the page contains a legacy or unusual font,
   identify the characters based on their visual glyphs.
10. Ignore page numbers, decorative borders,
    watermarks, and unrelated visual elements when
    they are clearly not part of the book text.

Return ONLY the extracted text.
"""

        response = await client.aio.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type
                ),
                prompt
            ]
        )

        text = ""

        if response and response.text:
            text = response.text

        text = clean_text(text)

        if not text:
            return {
                "success": False,
                "error": "Gemini returned no OCR text."
            }

        return {
            "success": True,
            "content_type": "ocr",
            "text": text
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"Gemini OCR failed: {str(exc)}"
        }


# ============================================================
# PDF → IMAGE
# ============================================================

def render_pdf_page(page, scale=1.5):
    """
    Render a PDF page at a controlled resolution.

    Lower resolution reduces the amount of visual input
    Gemini has to process while remaining suitable for OCR.
    """
    matrix = fitz.Matrix(scale, scale)

    pix = page.get_pixmap(
        matrix=matrix,
        alpha=False
    )

    return pix.tobytes("png")

# ============================================================
# PDF → GEMINI OCR
# ============================================================

async def gemini_ocr_pdf(
    pdf_bytes: bytes,
    max_pages: Optional[int] = None
) -> dict:
    """
    Render PDF pages as images and process them
    with Gemini Vision OCR.

    Stops immediately if Gemini quota is exceeded.
    """

    if not pdf_bytes:
        return {
            "success": False,
            "error": "No PDF data provided."
        }

    try:
        import fitz

        document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        total_pages = len(document)

        document.close()

        if total_pages == 0:
            return {
                "success": False,
                "error": "PDF contains no pages."
            }

        # --------------------------------------------------------
        # Page limit
        # --------------------------------------------------------

        pages_to_process = total_pages

        if max_pages is not None:
            pages_to_process = min(
                total_pages,
                max_pages
            )

        extracted_pages = []

        print(
            f"Gemini OCR: processing "
            f"{pages_to_process} page(s) "
            f"out of {total_pages}"
        )

        # --------------------------------------------------------
        # OCR each page
        # --------------------------------------------------------

        for page_number in range(
            pages_to_process
        ):

            print(
                f"OCR page "
                f"{page_number + 1}/"
                f"{pages_to_process}..."
            )

            image_bytes = render_pdf_page(
                pdf_bytes,
                page_number
            )

            if not image_bytes:
                print(
                    f"Could not render page "
                    f"{page_number + 1}"
                )
                continue

            try:
                result = await gemini_ocr_image(
                    image_bytes,
                    "image/png"
                )

            except Exception as exc:

                error_text = str(exc)

                print(
                    f"Gemini OCR error on page "
                    f"{page_number + 1}: "
                    f"{error_text}"
                )

                # ------------------------------------------------
                # Gemini quota detection
                # ------------------------------------------------

                if (
                    "429" in error_text
                    or "RESOURCE_EXHAUSTED"
                    in error_text.upper()
                    or "quota"
                    in error_text.lower()
                ):
                    print(
                        "Gemini quota exceeded."
                    )

                    print(
                        "Stopping OCR immediately."
                    )

                    return {
                        "success": False,
                        "error_code": "GEMINI_QUOTA",
                        "error": (
                            "Gemini quota is temporarily "
                            "exceeded. OCR stopped."
                        ),
                        "pages_processed": len(
                            extracted_pages
                        ),
                        "total_pages": total_pages
                    }

                # ------------------------------------------------
                # Other page errors
                # ------------------------------------------------

                print(
                    "Skipping this page and "
                    "continuing OCR."
                )

                continue

            # ----------------------------------------------------
            # Successful OCR
            # ----------------------------------------------------

            if result.get("success"):

                page_text = str(
                    result.get(
                        "text",
                        ""
                    )
                ).strip()

                if page_text:

                    extracted_pages.append(
                        f"[Page {page_number + 1}]\n"
                        f"{page_text}"
                    )

        # --------------------------------------------------------
        # No text extracted
        # --------------------------------------------------------

        if not extracted_pages:
            return {
                "success": False,
                "error": (
                    "Gemini could not extract "
                    "text from the PDF."
                ),
                "pages_processed": 0,
                "total_pages": total_pages
            }

        # --------------------------------------------------------
        # Return OCR text
        # --------------------------------------------------------

        return {
            "success": True,
            "content_type": "pdf_ocr",
            "text": clean_text(
                "\n\n".join(
                    extracted_pages
                )
            ),
            "pages_processed": len(
                extracted_pages
            ),
            "total_pages": total_pages
        }

    except Exception as exc:

        error_text = str(exc)

        # --------------------------------------------------------
        # Catch quota errors outside page processing
        # --------------------------------------------------------

        if (
            "429" in error_text
            or "RESOURCE_EXHAUSTED"
            in error_text.upper()
            or "quota"
            in error_text.lower()
        ):
            return {
                "success": False,
                "error_code": "GEMINI_QUOTA",
                "error": (
                    "Gemini quota is temporarily "
                    "exceeded. OCR stopped."
                )
            }

        return {
            "success": False,
            "error": (
                f"PDF OCR failed: "
                f"{error_text}"
            )
        }

# ============================================================
# ACCESS RECORD → FULL TEXT
# ============================================================

async def fetch_book_fulltext_from_access(
    access_record: dict
) -> dict:
    """
    Retrieve legally accessible book content.

    Strategy:
    1. Try normal PDF text extraction.
    2. If extracted text is good, return it immediately.
    3. If text is empty/short/garbled, use Gemini OCR.
    4. OCR only the first 10 pages.
    """

    if not access_record:
        return {
            "success": False,
            "error": "No access record provided."
        }


    pdf_url = str(
        access_record.get(
            "pdf_url",
            ""
        ) or ""
    ).strip()

    download_url = str(
        access_record.get(
            "download_url",
            ""
        ) or ""
    ).strip()

    # --------------------------------------------------------
    # Helper: OCR a PDF using Gemini.
    # --------------------------------------------------------

    async def try_gemini_ocr(url: str):

        try:

            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=60.0
            ) as client:

                response = await client.get(
                    url
                )

                if response.status_code != 200:
                    print(
                        f"PDF download failed: "
                        f"{response.status_code}"
                    )

                    return None

                content_type = (
                    response.headers.get(
                        "content-type",
                        ""
                    ).lower()
                )

                # Make sure we actually received a PDF.
                if (
                    "pdf" not in content_type
                    and not response.content.startswith(
                        b"%PDF"
                    )
                ):
                    print(
                        "URL did not return a PDF."
                    )

                    return None

                print(
                    "Starting Gemini OCR "
                    "for first 20 pages..."
                )

                ocr_result = await gemini_ocr_pdf(
                    response.content,
                    max_pages=20
                )

                if ocr_result.get(
                    "success"
                ):

                    ocr_result[
                        "source_url"
                    ] = url

                    return ocr_result

                return ocr_result

        except Exception as exc:

            print(
                f"Gemini OCR error: {exc}"
            )

            return {
                "success": False,
                "error": str(exc)
            }

    # ========================================================
    # 1. TRY PDF TEXT EXTRACTION
    # ========================================================

    if pdf_url:

        print(
            "\nTrying normal PDF text extraction..."
        )

        result = await fetch_fulltext(
            pdf_url
        )

        if result.get("success"):

            text = str(
                result.get(
                    "text",
                    ""
                ) or ""
            ).strip()

            # ------------------------------------------------
            # Good selectable text.
            # Return it without Gemini.
            # ------------------------------------------------

            if not looks_like_garbled_text(
                text
            ):

                print(
                    "Good selectable PDF text found."
                )

                return {
                    **result,
                    "content_type": "pdf_text",
                    "ocr_used": False
                }

            # ------------------------------------------------
            # PDF opened, but text is poor.
            # Use OCR.
            # ------------------------------------------------

            print(
                "PDF text is empty/short/garbled."
            )

            print(
                "Falling back to Gemini OCR..."
            )

            ocr_result = await try_gemini_ocr(
                pdf_url
            )

            if (
                ocr_result
                and ocr_result.get("success")
            ):

                ocr_result[
                    "ocr_used"
                ] = True

                return ocr_result

            # If OCR failed, preserve the original
            # extraction result if it contained anything.
            if text:

                return {
                    **result,
                    "content_type": "pdf_text",
                    "ocr_used": False,
                    "ocr_fallback_failed": True
                }

        else:

            # ------------------------------------------------
            # PDF text extraction completely failed.
            # Try Gemini OCR directly.
            # ------------------------------------------------

            print(
                "Normal PDF text extraction failed."
            )

            print(
                "Trying Gemini OCR..."
            )

            ocr_result = await try_gemini_ocr(
                pdf_url
            )

            if (
                ocr_result
                and ocr_result.get("success")
            ):

                ocr_result[
                    "ocr_used"
                ] = True

                return ocr_result

    # ========================================================
    # 2. TRY DIRECT DOWNLOAD URL
    # ========================================================

    if (
        download_url
        and download_url != pdf_url
    ):

        print(
            "\nTrying direct downloadable file..."
        )

        result = await fetch_fulltext(
            download_url
        )

        if result.get("success"):

            text = str(
                result.get(
                    "text",
                    ""
                ) or ""
            ).strip()

            if not looks_like_garbled_text(
                text
            ):

                print(
                    "Good text found from download."
                )

                return {
                    **result,
                    "content_type": "download_text",
                    "ocr_used": False
                }

            print(
                "Downloaded text is poor."
            )

            print(
                "Trying Gemini OCR..."
            )

            ocr_result = await try_gemini_ocr(
                download_url
            )

            if (
                ocr_result
                and ocr_result.get("success")
            ):

                ocr_result[
                    "ocr_used"
                ] = True

                return ocr_result

    # ========================================================
    # 3. NOTHING USABLE
    # ========================================================

    return {
        "success": False,
        "error": (
            "No legally accessible extractable "
            "full-text file found."
        )
    }

# ============================================================
# GARBLED TEXT DETECTION
# ============================================================

def looks_like_garbled_text(
    text: str
) -> bool:
    """
    Detect obvious PDF encoding/mojibake problems.

    This is intentionally conservative.
    """

    if not text:
        return True

    stripped = text.strip()

    if len(stripped) < 50:
        return True

    # Common mojibake indicators.
    suspicious_patterns = [
        "‚",
        "√",
        "ƒ",
        "„",
        "‰",
        "Â",
        "Ã",
        "�",
        "à",
        "â",
        "ð",
        "þ",
    ]

    suspicious_count = sum(
        stripped.count(pattern)
        for pattern in suspicious_patterns
    )

    # If suspicious characters make up a
    # noticeable part of the text, OCR it.
    if suspicious_count >= 5:
        return True

    return False