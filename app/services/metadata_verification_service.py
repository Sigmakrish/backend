from typing import Any

from app.services.ranking_service import (
    similarity,
    normalize,
    normalize_isbn
)


# ============================================================
# TEXT MATCH
# ============================================================

def text_match(
    value1: Any,
    value2: Any
) -> float:
    """
    Compare two text values.
    Returns 0-100.
    """

    if not value1 or not value2:
        return 0.0

    return round(
        similarity(
            normalize(value1),
            normalize(value2)
        ) * 100,
        2
    )


# ============================================================
# YEAR MATCH
# ============================================================

def year_match(
    year1: Any,
    year2: Any
) -> float:
    """
    Compare publication years.

    Exact year = 100
    Difference <= 2 = 50
    Otherwise = 0
    """

    if not year1 or not year2:
        return 0.0

    try:
        year1 = int(year1)
        year2 = int(year2)

    except (ValueError, TypeError):
        return 0.0

    if year1 == year2:
        return 100.0

    if abs(year1 - year2) <= 2:
        return 50.0

    return 0.0


# ============================================================
# ISBN MATCH
# ============================================================

def isbn_match(
    book1: dict[str, Any],
    book2: dict[str, Any]
) -> float:
    """
    Compare ISBN values between two sources.
    """

    isbn1 = set()

    isbn2 = set()

    # -----------------------------------------
    # First source
    # -----------------------------------------

    for value in book1.get(
        "isbn_list",
        []
    ):

        normalized = normalize_isbn(
            value
        )

        if normalized:
            isbn1.add(
                normalized
            )

    single_isbn = normalize_isbn(
        book1.get("isbn")
    )

    if single_isbn:
        isbn1.add(
            single_isbn
        )

    # -----------------------------------------
    # Second source
    # -----------------------------------------

    for value in book2.get(
        "isbn_list",
        []
    ):

        normalized = normalize_isbn(
            value
        )

        if normalized:
            isbn2.add(
                normalized
            )

    single_isbn = normalize_isbn(
        book2.get("isbn")
    )

    if single_isbn:
        isbn2.add(
            single_isbn
        )

    # -----------------------------------------
    # Compare
    # -----------------------------------------

    if not isbn1 or not isbn2:
        return 0.0

    if isbn1.intersection(isbn2):
        return 100.0

    return 0.0


# ============================================================
# VERIFY TWO SOURCES
# ============================================================

def verify_metadata(
    book1: dict[str, Any],
    book2: dict[str, Any]
) -> dict[str, Any]:
    """
    Compare metadata from two independent sources.
    """

    title_score = text_match(
        book1.get("title"),
        book2.get("title")
    )

    author_score = text_match(
        book1.get("author"),
        book2.get("author")
    )

    year_score = year_match(
        book1.get("publication_year")
        or book1.get("first_publish_year"),

        book2.get("publication_year")
        or book2.get("first_publish_year")
    )

    publisher_score = text_match(
        book1.get("publisher"),
        book2.get("publisher")
    )

    isbn_score = isbn_match(
        book1,
        book2
    )

    # ========================================================
    # WEIGHTS
    # ========================================================

    weights = {
        "title": 35,
        "author": 30,
        "year": 15,
        "publisher": 10,
        "isbn": 10,
    }

    total_score = (
        title_score
        * weights["title"]
        / 100
        +

        author_score
        * weights["author"]
        / 100
        +

        year_score
        * weights["year"]
        / 100
        +

        publisher_score
        * weights["publisher"]
        / 100
        +

        isbn_score
        * weights["isbn"]
        / 100
    )

    # ========================================================
    # VERIFICATION STATUS
    # ========================================================

    if (
        isbn_score == 100
        and title_score >= 80
    ):
        status = "Verified edition"

    elif (
        title_score >= 85
        and author_score >= 80
    ):
        status = "Strongly verified"

    elif (
        title_score >= 70
        and author_score >= 60
    ):
        status = "Partially verified"

    else:
        status = "Unverified"

    return {
        "verification_score": round(
            total_score,
            2
        ),

        "verification_status": status,

        "field_matches": {
            "title": round(
                title_score,
                2
            ),

            "author": round(
                author_score,
                2
            ),

            "year": round(
                year_score,
                2
            ),

            "publisher": round(
                publisher_score,
                2
            ),

            "isbn": round(
                isbn_score,
                2
            ),
        }
    }


# ============================================================
# VERIFY CANDIDATE SOURCES
# ============================================================

def verify_candidate_sources(
    candidate: dict[str, Any]
) -> dict[str, Any]:
    """
    Verify a merged candidate that may contain
    metadata from multiple sources.
    """

    sources = candidate.get(
        "sources",
        []
    )

    # --------------------------------------------------------
    # If only one source exists
    # --------------------------------------------------------

    if len(sources) < 2:

        return {
            "verification_score": None,
            "verification_status": (
                "Single source"
            ),
            "field_matches": {}
        }

    # --------------------------------------------------------
    # Build source-specific records
    # --------------------------------------------------------

    source_records = (
        candidate.get(
            "source_records",
            []
        )
    )

    if len(source_records) < 2:

        return {
            "verification_score": None,
            "verification_status": (
                "Multiple sources detected, "
                "but metadata comparison unavailable"
            ),
            "field_matches": {}
        }

    # --------------------------------------------------------
    # Compare first two sources
    # --------------------------------------------------------

    result = verify_metadata(
        source_records[0],
        source_records[1]
    )

    return result