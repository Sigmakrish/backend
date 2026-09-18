import re
from typing import Any
from unidecode import unidecode
from difflib import SequenceMatcher


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(value: Any) -> str:
    """
    Normalize text for comparison.

    Keeps + and # because:
        C++
        C#

    are meaningful.
    """

    if value is None:
        return ""

    text = str(value).lower().strip()

    text = re.sub(
        r"[^a-z0-9+#\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


# ============================================================
# AUTHOR NORMALIZATION
# ============================================================

def normalize_author(value: Any) -> str:

    if not value:
        return ""

    text = normalize_text(value)

    tokens = []

    for token in text.split():

        # Remove middle initials.
        if len(token) == 1:
            continue

        tokens.append(token)

    return " ".join(tokens)


def author_tokens(value: Any) -> set[str]:

    author = normalize_author(value)

    if not author:
        return set()

    return set(
        author.split()
    )


# ============================================================
# ISBN
# ============================================================

def normalize_isbn(isbn: Any) -> str:

    if not isbn:
        return ""

    return re.sub(
        r"[^0-9xX]",
        "",
        str(isbn)
    ).upper()


def get_candidate_isbns(
    book: dict[str, Any]
) -> set[str]:

    isbns = set()

    isbn = normalize_isbn(
        book.get("isbn")
    )

    if isbn:
        isbns.add(isbn)

    for value in book.get(
        "isbn_list",
        []
    ):

        normalized = normalize_isbn(
            value
        )

        if normalized:
            isbns.add(normalized)

    for field in (
        "isbn10",
        "isbn13"
    ):

        normalized = normalize_isbn(
            book.get(field)
        )

        if normalized:
            isbns.add(normalized)

    return isbns


# ============================================================
# TITLE NORMALIZATION
# ============================================================

EDITION_PATTERNS = [
    r"\b\d+(?:st|nd|rd|th)?\s+edition\b",
    r"\bedition\s+\d+\b",
    r"\b\d+(?:st|nd|rd|th)?\s+ed\b",
    r"\bvolume\s+\d+\b",
    r"\bvol\s+\d+\b",
    r"\bpart\s+\d+\b",
    r"\brevised\b",
    r"\bupdated\b",
    r"\bnew\b",
]


def title_core(value: Any) -> str:

    text = normalize_text(value)

    if not text:
        return ""

    for pattern in EDITION_PATTERNS:

        text = re.sub(
            pattern,
            " ",
            text
        )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


# ============================================================
# TITLE TOKENS
# ============================================================

TITLE_STOP_WORDS = {
    "the",
    "a",
    "an",
    "of",
    "for",
    "and",
    "in",
    "to",
    "on",
    "from",
    "by",
    "with",
    "at",
    "into",
    "through",
}


def title_tokens(
    value: Any
) -> set[str]:

    text = title_core(value)

    if not text:
        return set()

    return set(
        text.split()
    )


def ordered_title_tokens(
    value: Any,
    remove_stop_words: bool = False
) -> list[str]:

    text = title_core(value)

    if not text:
        return []

    tokens = text.split()

    if remove_stop_words:

        tokens = [
            token
            for token in tokens
            if token not in TITLE_STOP_WORDS
        ]

    return tokens


# ============================================================
# PRIMARY TITLE
# ============================================================

def primary_title(
    value: Any
) -> str:
    """
    Example:

        Let Us C: Authentic Guide to C Programming Language

    becomes:

        Let Us C
    """

    text = title_core(value)

    if not text:
        return ""

    text = text.split(":")[0].strip()

    return text


def primary_title_tokens(
    value: Any,
    remove_stop_words: bool = False
) -> list[str]:

    text = primary_title(value)

    if not text:
        return []

    tokens = text.split()

    if remove_stop_words:

        tokens = [
            token
            for token in tokens
            if token not in TITLE_STOP_WORDS
        ]

    return tokens


# ============================================================
# PROGRAMMING TERMS
# ============================================================

PROGRAMMING_TERMS = {
    "c++",
    "c#",
    "javascript",
    "java",
    "python",
    "php",
    "sql",
    "ruby",
    "perl",
    "kotlin",
    "swift",
    "rust",
}


# ============================================================
# PROGRAMMING LANGUAGE DETECTION
# ============================================================

def detect_programming_language(
    value: Any
) -> str | None:

    text = normalize_text(value)

    if not text:
        return None

    terms = sorted(
        PROGRAMMING_TERMS,
        key=len,
        reverse=True
    )

    for term in terms:

        if re.search(
            rf"(?<![a-z0-9+#]){re.escape(term)}(?![a-z0-9+#])",
            text
        ):
            return term

    # Standalone C.
    if re.search(
        r"\bc\b",
        text
    ):
        return "c"

    return None


# ============================================================
# TECHNICAL TITLE MISMATCH
# ============================================================

def technical_title_mismatch(
    title_a: Any,
    title_b: Any
) -> bool:

    a = normalize_text(title_a)
    b = normalize_text(title_b)

    language_a = detect_programming_language(a)
    language_b = detect_programming_language(b)

    if (
        language_a
        and language_b
        and language_a != language_b
    ):
        return True

    # C++ protection.
    if (
        ("c++" in a)
        != ("c++" in b)
    ):

        if (
            "c++" in a
            or "c++" in b
        ):
            return True

    # C# protection.
    if (
        ("c#" in a)
        != ("c#" in b)
    ):

        if (
            "c#" in a
            or "c#" in b
        ):
            return True

    return False


# ============================================================
# CONTIGUOUS TOKEN MATCH
# ============================================================

def is_contiguous_subsequence(
    shorter: list[str],
    longer: list[str]
) -> bool:

    if not shorter or not longer:
        return False

    if len(shorter) > len(longer):
        return False

    size = len(shorter)

    for i in range(
        len(longer) - size + 1
    ):

        if longer[
            i:i + size
        ] == shorter:

            return True

    return False


# ============================================================
# TITLE STRUCTURAL MATCH
# ============================================================

def title_structural_match(
    title_a: Any,
    title_b: Any
) -> float:

    if technical_title_mismatch(
        title_a,
        title_b
    ):
        return 0.0

    core_a = title_core(title_a)
    core_b = title_core(title_b)

    if not core_a or not core_b:
        return 0.0

    # Exact.
    if core_a == core_b:
        return 1.0

    # Primary title.
    primary_a = primary_title(title_a)
    primary_b = primary_title(title_b)

    if primary_a and primary_b:

        if primary_a == primary_b:
            return 0.98

        primary_tokens_a = primary_title_tokens(
            title_a
        )

        primary_tokens_b = primary_title_tokens(
            title_b
        )

        if (
            is_contiguous_subsequence(
                primary_tokens_a,
                primary_tokens_b
            )
            or
            is_contiguous_subsequence(
                primary_tokens_b,
                primary_tokens_a
            )
        ):
            return 0.95

    # Ordered core tokens.
    tokens_a = ordered_title_tokens(
        title_a
    )

    tokens_b = ordered_title_tokens(
        title_b
    )

    if (
        is_contiguous_subsequence(
            tokens_a,
            tokens_b
        )
        or
        is_contiguous_subsequence(
            tokens_b,
            tokens_a
        )
    ):
        return 0.90

    # Stop-word-normalized comparison.
    clean_a = ordered_title_tokens(
        title_a,
        remove_stop_words=True
    )

    clean_b = ordered_title_tokens(
        title_b,
        remove_stop_words=True
    )

    if clean_a and clean_b:

        if clean_a == clean_b:
            return 0.92

        if (
            is_contiguous_subsequence(
                clean_a,
                clean_b
            )
            or
            is_contiguous_subsequence(
                clean_b,
                clean_a
            )
        ):
            return 0.88

    return 0.0


# ============================================================
# TITLE RELATION
# ============================================================

def title_relation(
    title_a: Any,
    title_b: Any
) -> float:

    structural = title_structural_match(
        title_a,
        title_b
    )

    if structural > 0:
        return structural

    tokens_a = title_tokens(title_a)
    tokens_b = title_tokens(title_b)

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = (
        tokens_a
        & tokens_b
    )

    if not intersection:
        return 0.0

    union = (
        tokens_a
        | tokens_b
    )

    if not union:
        return 0.0

    return (
        len(intersection)
        / len(union)
    )


# ============================================================
# MULTILINGUAL SEARCH VARIANTS
# ============================================================

def get_search_variants(
    identified_data: dict[str, Any]
) -> list[str]:
    """
    Collect Gemini-generated multilingual variants.

    Example:

        श्रीरामचरितमानस
        Shri Ramcharitmanas
        Ramcharitmanas Tulsidas
        Tulsidas Ramcharitmanas
    """

    variants = []

    raw_variants = identified_data.get(
        "search_variants",
        []
    )

    if isinstance(
        raw_variants,
        str
    ):
        raw_variants = [
            raw_variants
        ]

    if isinstance(
        raw_variants,
        list
    ):

        for variant in raw_variants:

            if variant:

                variant = str(
                    variant
                ).strip()

                if variant:
                    variants.append(
                        variant
                    )

    # Always include identified title.
    title = identified_data.get(
        "title",
        ""
    )

    if title:
        variants.insert(
            0,
            str(title)
        )

    # Remove duplicates while preserving order.
    result = []

    seen = set()

    for variant in variants:

        key = normalize_text(
            variant
        )

        # For non-Latin scripts normalize_text()
        # can become empty. Preserve the original variant
        # in that case.
        if not key:
            key = variant.lower().strip()

        if (
            key
            and key not in seen
        ):

            seen.add(key)

            result.append(
                variant
            )

    return result


# ============================================================
# MULTILINGUAL VARIANT TITLE MATCH
# ============================================================

def variant_title_match(
    candidate_title: Any,
    identified_data: dict[str, Any]
) -> float:
    """
    Compare candidate title against Gemini multilingual variants.

    Supports:
        सुंदरकांड
        Sundarkand
        Sundar Kand
        Sunderkand
        Sundar-Kand
        Sundar Kanda
    """

    variants = get_search_variants(
        identified_data
    )

    if not variants:
        return 0.0

    candidate_raw = str(
        candidate_title or ""
    ).strip()

    if not candidate_raw:
        return 0.0

    # --------------------------------------------------------
    # Normal ASCII representation
    # --------------------------------------------------------

    candidate_text = normalize_text(
        candidate_raw
    )

    # --------------------------------------------------------
    # Transliteration representation
    # --------------------------------------------------------

    candidate_translit = unidecode(
        candidate_raw
    ).lower().strip()

    candidate_translit = re.sub(
        r"[^a-z0-9+#\s]",
        " ",
        candidate_translit
    )

    candidate_translit = re.sub(
        r"\s+",
        " ",
        candidate_translit
    ).strip()

    # Compact transliteration:
    #
    # Sundar Kand -> sundarkand
    # Sundar-Kand -> sundarkand
    # Sundarkand -> sundarkand
    #
    candidate_compact = "".join(
        ch
        for ch in candidate_translit
        if ch.isalnum()
    )

    best_score = 0.0

    for variant in variants:

        if not variant:
            continue

        variant_raw = str(
            variant
        ).strip()

        # ----------------------------------------------------
        # Standard structural comparison
        # ----------------------------------------------------

        score = title_structural_match(
            variant_raw,
            candidate_raw
        )

        best_score = max(
            best_score,
            score
        )

        # ----------------------------------------------------
        # Normalized exact comparison
        # ----------------------------------------------------

        variant_text = normalize_text(
            variant_raw
        )

        if (
            variant_text
            and candidate_text
            and variant_text == candidate_text
        ):
            best_score = max(
                best_score,
                1.0
            )

        # ----------------------------------------------------
        # Transliteration
        # ----------------------------------------------------

        variant_translit = unidecode(
            variant_raw
        ).lower().strip()

        variant_translit = re.sub(
            r"[^a-z0-9+#\s]",
            " ",
            variant_translit
        )

        variant_translit = re.sub(
            r"\s+",
            " ",
            variant_translit
        ).strip()

        # ----------------------------------------------------
        # Compact transliteration
        # ----------------------------------------------------

        variant_compact = "".join(
            ch
            for ch in variant_translit
            if ch.isalnum()
        )

        if (
            variant_compact
            and candidate_compact
        ):

            if (
                variant_compact
                == candidate_compact
            ):
                best_score = max(
                    best_score,
                    1.0
                )

            else:

                compact_similarity = (
                    SequenceMatcher(
                        None,
                        variant_compact,
                        candidate_compact,
                    ).ratio()
                )

                best_score = max(
                    best_score,
                    compact_similarity
                )

    return best_score

# ============================================================
# MULTILINGUAL TOKEN MATCH
# ============================================================

def variant_token_match(
    candidate_title: Any,
    identified_data: dict[str, Any]
) -> float:
    """
    Multilingual/transliteration-aware token comparison.

    Supports both normal English tokens and compact
    transliterated forms.
    """

    candidate_raw = str(
        candidate_title or ""
    ).strip()

    if not candidate_raw:
        return 0.0

    variants = get_search_variants(
        identified_data
    )

    if not variants:
        return 0.0

    best = 0.0

    # --------------------------------------------------------
    # Normal candidate tokens
    # --------------------------------------------------------

    candidate_tokens = title_tokens(
        candidate_raw
    )

    # --------------------------------------------------------
    # Transliteration tokens
    # --------------------------------------------------------

    candidate_translit = unidecode(
        candidate_raw
    ).lower()

    candidate_translit = re.sub(
        r"[^a-z0-9+#\s]",
        " ",
        candidate_translit
    )

    candidate_translit = re.sub(
        r"\s+",
        " ",
        candidate_translit
    ).strip()

    candidate_translit_tokens = set(
        candidate_translit.split()
    )

    for variant in variants:

        if not variant:
            continue

        # ----------------------------------------------------
        # Standard token comparison
        # ----------------------------------------------------

        variant_tokens = title_tokens(
            variant
        )

        if (
            candidate_tokens
            and variant_tokens
        ):

            overlap = (
                candidate_tokens
                & variant_tokens
            )

            if overlap:

                union = (
                    candidate_tokens
                    | variant_tokens
                )

                if union:

                    score = (
                        len(overlap)
                        / len(union)
                    )

                    if len(overlap) >= 1:

                        best = max(
                            best,
                            score
                        )

        # ----------------------------------------------------
        # Transliteration token comparison
        # ----------------------------------------------------

        variant_translit = unidecode(
            str(variant)
        ).lower()

        variant_translit = re.sub(
            r"[^a-z0-9+#\s]",
            " ",
            variant_translit
        )

        variant_translit = re.sub(
            r"\s+",
            " ",
            variant_translit
        ).strip()

        variant_translit_tokens = set(
            variant_translit.split()
        )

        if (
            candidate_translit_tokens
            and variant_translit_tokens
        ):

            overlap = (
                candidate_translit_tokens
                & variant_translit_tokens
            )

            if overlap:

                union = (
                    candidate_translit_tokens
                    | variant_translit_tokens
                )

                if union:

                    score = (
                        len(overlap)
                        / len(union)
                    )

                    best = max(
                        best,
                        score
                    )

    return best

# ============================================================
# WORK KEY
# ============================================================

def candidate_key(
    book: dict[str, Any]
) -> str:

    title = title_core(
        book.get("title")
    )

    author = normalize_author(
        book.get("author")
    )

    title_key = " ".join(
        sorted(
            title.split()
        )
    )

    author_key = " ".join(
        sorted(
            author.split()
        )
    )

    return (
        f"work:{title_key}|"
        f"author:{author_key}"
    )


# ============================================================
# SAME WORK
# ============================================================

def same_work(
    book_a: dict[str, Any],
    book_b: dict[str, Any]
) -> bool:

    title_a = book_a.get(
        "title",
        ""
    )

    title_b = book_b.get(
        "title",
        ""
    )

    if technical_title_mismatch(
        title_a,
        title_b
    ):
        return False

    relation = title_structural_match(
        title_a,
        title_b
    )

    if relation < 0.88:
        return False

    author_a = author_tokens(
        book_a.get("author")
    )

    author_b = author_tokens(
        book_b.get("author")
    )

    if author_a and author_b:

        overlap = (
            author_a
            & author_b
        )

        if not overlap:
            return False

        return True

    if relation >= 0.95:
        return True

    return False


# ============================================================
# CANDIDATE RELEVANCE FILTER
# ============================================================

def is_candidate_relevant(
    candidate: dict[str, Any],
    identified_data: dict[str, Any]
) -> bool:
    """
    Strict multilingual-aware candidate filtering.

    Priority:

        1. Strong Gemini multilingual variant match
        2. Programming-language mismatch protection
        3. Direct structural title match
        4. Variant token match
        5. Strong title + author support
    """

    raw_identified_title = (
        identified_data.get(
            "title",
            ""
        )
    )

    raw_candidate_title = (
        candidate.get(
            "title",
            ""
        )
    )

    if (
        not raw_identified_title
        or not raw_candidate_title
    ):
        return False

    # ========================================================
    # MULTILINGUAL / TRANSLITERATION MATCH
    # ========================================================
    #
    # IMPORTANT:
    #
    # This happens BEFORE normalize_text().
    #
    # Therefore:
    #
    #     सुंदरकांड
    #
    # is not destroyed by ASCII-only normalization.
    #
    # Gemini variant:
    #
    #     Sundarkand
    #
    # can match an Internet Archive title:
    #
    #     Sundar Kand
    #
    # ========================================================

    variant_score = variant_title_match(
        raw_candidate_title,
        identified_data
    )

    if variant_score >= 0.88:
        return True

    # ========================================================
    # NORMALIZED TITLES
    # ========================================================

    identified_title = normalize_text(
        raw_identified_title
    )

    candidate_title = normalize_text(
        raw_candidate_title
    )

    # ========================================================
    # PROGRAMMING LANGUAGE PROTECTION
    # ========================================================

    identified_language = (
        detect_programming_language(
            identified_title
        )
    )

    candidate_language = (
        detect_programming_language(
            candidate_title
        )
    )

    if (
        identified_language
        and candidate_language
        and identified_language
        != candidate_language
    ):
        return False

    # C++ protection

    if (
        ("c++" in identified_title)
        != ("c++" in candidate_title)
    ):

        if (
            "c++" in identified_title
            or "c++" in candidate_title
        ):
            return False

    # C# protection

    if (
        ("c#" in identified_title)
        != ("c#" in candidate_title)
    ):

        if (
            "c#" in identified_title
            or "c#" in candidate_title
        ):
            return False

    # ========================================================
    # DIRECT STRUCTURAL TITLE MATCH
    # ========================================================

    structural = 0.0

    if (
        identified_title
        and candidate_title
    ):

        structural = (
            title_structural_match(
                identified_title,
                candidate_title
            )
        )

    if structural >= 0.88:
        return True

    # ========================================================
    # MULTILINGUAL TOKEN MATCH
    # ========================================================

    variant_token_score = (
        variant_token_match(
            raw_candidate_title,
            identified_data
        )
    )

    if variant_token_score >= 0.70:
        return True

    # ========================================================
    # AUTHOR MATCH
    # ========================================================

    identified_author = author_tokens(
        identified_data.get(
            "author"
        )
    )

    candidate_author = author_tokens(
        candidate.get(
            "author"
        )
    )

    author_match = bool(
        identified_author
        and candidate_author
        and (
            identified_author
            & candidate_author
        )
    )

    # ========================================================
    # TITLE + AUTHOR
    # ========================================================

    if (
        author_match
        and identified_title
        and candidate_title
    ):

        relation = title_relation(
            identified_title,
            candidate_title
        )

        if relation >= 0.70:

            identified_tokens = (
                ordered_title_tokens(
                    identified_title,
                    remove_stop_words=True
                )
            )

            candidate_tokens = (
                ordered_title_tokens(
                    candidate_title,
                    remove_stop_words=True
                )
            )

            overlap = (
                set(identified_tokens)
                & set(candidate_tokens)
            )

            if len(overlap) >= 2:
                return True

    # ========================================================
    # MULTILINGUAL TITLE + AUTHOR
    # ========================================================

    if (
        author_match
        and variant_score >= 0.65
    ):
        return True

    if (
        author_match
        and variant_token_score >= 0.40
    ):
        return True

    # ========================================================
    # STRONG VARIANT WITHOUT AUTHOR
    # ========================================================

    if (
        variant_score >= 0.95
        and not candidate_author
    ):
        return True

    return False

    # ========================================================
    # DIRECT STRUCTURAL TITLE MATCH
    # ========================================================

    structural = title_structural_match(
        identified_title,
        candidate_title
    )

    if structural >= 0.88:
        return True

    # ========================================================
    # MULTILINGUAL SEARCH VARIANT MATCH
    # ========================================================

    variant_score = variant_title_match(
        candidate_title,
        identified_data
    )

    if variant_score >= 0.88:
        return True

    # ========================================================
    # MULTILINGUAL TOKEN MATCH
    # ========================================================

    variant_token_score = (
        variant_token_match(
            candidate_title,
            identified_data
        )
    )

    # ========================================================
    # AUTHOR SUPPORT
    # ========================================================

    identified_author = author_tokens(
        identified_data.get(
            "author"
        )
    )

    candidate_author = author_tokens(
        candidate.get(
            "author"
        )
    )

    author_match = bool(
        identified_author
        and candidate_author
        and (
            identified_author
            & candidate_author
        )
    )

    # --------------------------------------------------------
    # English / transliterated title:
    #
    # Strong title relation + matching author.
    # --------------------------------------------------------

    if author_match:

        relation = title_relation(
            identified_title,
            candidate_title
        )

        if relation >= 0.70:

            identified_tokens = (
                ordered_title_tokens(
                    identified_title,
                    remove_stop_words=True
                )
            )

            candidate_tokens = (
                ordered_title_tokens(
                    candidate_title,
                    remove_stop_words=True
                )
            )

            overlap = (
                set(identified_tokens)
                & set(candidate_tokens)
            )

            if len(overlap) >= 2:
                return True

        # ----------------------------------------------------
        # Multilingual case:
        #
        # Title itself may have no shared tokens because
        # Hindi/Sanskrit script and English transliteration
        # are different.
        #
        # In that case require:
        #
        #   variant token/title evidence
        #   +
        #   matching author
        # ----------------------------------------------------

        if (
            variant_score >= 0.70
            and author_match
        ):
            return True

        if (
            variant_token_score >= 0.40
            and author_match
        ):
            return True

    # ========================================================
    # SEARCH VARIANT + TITLE-ONLY CASE
    # ========================================================
    #
    # Some catalogues omit authors.
    #
    # Only allow this when the variant provides strong
    # structural evidence.
    # ========================================================

    if (
        variant_score >= 0.95
        and not candidate_author
    ):
        return True

    return False


# ============================================================
# FILTER CANDIDATES
# ============================================================

def filter_candidates(
    candidates: list[dict[str, Any]],
    identified_data: dict[str, Any],
    max_candidates: int = 30
) -> list[dict[str, Any]]:

    filtered = []

    for candidate in candidates:

        if is_candidate_relevant(
            candidate,
            identified_data
        ):

            filtered.append(
                candidate
            )

    return filtered[
        :max_candidates
    ]


# ============================================================
# MERGE FIELD VALUE
# ============================================================

def fill_missing_fields(
    existing: dict[str, Any],
    incoming: dict[str, Any]
) -> None:

    protected_fields = {
        "sources",
        "source_records",
        "editions",
    }

    for field, value in incoming.items():

        if field in protected_fields:
            continue

        if value in (
            None,
            "",
            [],
            {}
        ):
            continue

        existing_value = (
            existing.get(
                field
            )
        )

        if existing_value in (
            None,
            "",
            [],
            {}
        ):

            existing[
                field
            ] = value


# ============================================================
# MERGE CANDIDATES
# ============================================================

def merge_candidates(
    candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:

    merged: list[
        dict[str, Any]
    ] = []

    for book in candidates:

        matching_work = None

        for existing in merged:

            if same_work(
                existing,
                book
            ):

                matching_work = existing
                break

        # ----------------------------------------------------
        # New work.
        # ----------------------------------------------------

        if matching_work is None:

            new_book = dict(
                book
            )

            source = book.get(
                "source"
            )

            new_book[
                "sources"
            ] = (
                [source]
                if source
                else []
            )

            new_book[
                "source_records"
            ] = [
                dict(book)
            ]

            new_book[
                "editions"
            ] = [
                dict(book)
            ]

            merged.append(
                new_book
            )

            continue

        # ----------------------------------------------------
        # Existing work.
        # ----------------------------------------------------

        source = book.get(
            "source"
        )

        if (
            source
            and source not in matching_work[
                "sources"
            ]
        ):

            matching_work[
                "sources"
            ].append(
                source
            )

        # Preserve source record.
        matching_work[
            "source_records"
        ].append(
            dict(book)
        )

        # Preserve edition record.
        matching_work[
            "editions"
        ].append(
            dict(book)
        )

        # Fill missing metadata.
        fill_missing_fields(
            matching_work,
            book
        )

    # ========================================================
    # WORK METADATA
    # ========================================================

    for work in merged:

        work[
            "work_record_count"
        ] = len(
            work.get(
                "source_records",
                []
            )
        )

        work[
            "edition_count"
        ] = len(
            work.get(
                "editions",
                []
            )
        )

    return merged