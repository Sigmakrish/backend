import re
import httpx
from typing import Any
from unidecode import unidecode


OPEN_LIBRARY_URL = (
    "https://openlibrary.org/search.json"
)


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(
    text: str
) -> str:

    if not text:
        return ""

    text = str(
        text
    ).lower().strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


# ============================================================
# TRANSLITERATION
# ============================================================

def transliterate(
    text: str
) -> str:
    """
    Convert non-Latin scripts into Latin text.
    """

    if not text:
        return ""

    result = unidecode(
        text
    )

    result = re.sub(
        r"\s+",
        " ",
        result
    )

    return result.strip()


# ============================================================
# SEARCH VARIANT GENERATION
# ============================================================

def generate_search_queries(
    title: str,
    author: str = "",
    search_variants: list[str] | None = None
) -> list[str]:

    queries = []

    def add_query(
        value: str
    ):

        if not value:
            return

        value = re.sub(
            r"\s+",
            " ",
            str(value).strip()
        )

        if (
            value
            and value not in queries
        ):

            queries.append(
                value
            )

    # --------------------------------------------------------
    # Original/native title
    # --------------------------------------------------------

    add_query(title)

    # --------------------------------------------------------
    # Native title + author
    # --------------------------------------------------------

    if title and author:

        add_query(
            f"{title} {author}"
        )

    # --------------------------------------------------------
    # Romanized title
    # --------------------------------------------------------

    roman_title = transliterate(
        title
    )

    roman_author = transliterate(
        author
    )

    if roman_title:
        add_query(
            roman_title
        )

    # Romanized title + author.
    if (
        roman_title
        and roman_author
    ):

        add_query(
            f"{roman_title} {roman_author}"
        )

    # Romanized author.
    if roman_author:

        add_query(
            roman_author
        )

    # --------------------------------------------------------
    # Gemini search variants
    # --------------------------------------------------------

    if search_variants:

        for variant in search_variants:

            if not variant:
                continue

            variant = str(
                variant
            ).strip()

            add_query(
                variant
            )

            # Also add transliterated version.
            roman_variant = transliterate(
                variant
            )

            if (
                roman_variant
                and roman_variant != variant
            ):

                add_query(
                    roman_variant
                )

    # --------------------------------------------------------
    # Better manual transliteration variants
    # --------------------------------------------------------
    #
    # Unidecode sometimes produces awkward forms such as:
    #
    #     suNdrkaaNdd
    #
    # We create simpler human-searchable variants.
    # --------------------------------------------------------

    if roman_title:

        roman_clean = clean_text(
            roman_title
        )

        # Remove repeated transliteration artifacts.
        roman_clean = re.sub(
            r"[^a-z0-9+#\s]",
            " ",
            roman_clean
        )

        roman_clean = re.sub(
            r"\s+",
            " ",
            roman_clean
        ).strip()

        if roman_clean:
            add_query(
                roman_clean
            )

        # ----------------------------------------------------
        # Remove common transliteration artifacts.
        # ----------------------------------------------------

        simplified = roman_clean

        replacements = [
            ("aa", "a"),
            ("ii", "i"),
            ("uu", "u"),
            ("ee", "i"),
            ("oo", "u"),
            ("N", "n"),
            ("M", "m"),
        ]

        for old, new in replacements:

            simplified = simplified.replace(
                old,
                new
            )

        simplified = re.sub(
            r"\s+",
            " ",
            simplified
        ).strip()

        if simplified:
            add_query(
                simplified
            )

    # --------------------------------------------------------
    # Special spacing variants
    #
    # Example:
    #
    #     Sundarkand
    #
    # can also appear as:
    #
    #     Sundar Kand
    #     Sundar Kanda
    #     Sunder Kand
    # --------------------------------------------------------

    if roman_title:

        compact = re.sub(
            r"[^a-zA-Z0-9]+",
            "",
            roman_title
        ).lower()

        if compact:

            # Generate a spaced version when the title
            # appears to contain common Indian-language
            # compound names.
            indian_suffixes = [
                "kand",
                "kanda",
                "charitmanas",
                "ramayan",
                "ramayana",
                "purana",
                "gita",
                "geeta",
            ]

            for suffix in indian_suffixes:

                if compact.endswith(
                    suffix
                ) and len(compact) > len(
                    suffix
                ):

                    prefix = compact[
                        :-len(suffix)
                    ]

                    if prefix:

                        add_query(
                            f"{prefix} {suffix}"
                        )

            # Explicit Sundarkand variants.
            if compact in {
                "sundarkand",
                "sunderkand",
                "sundarkanda",
            }:

                add_query(
                    "Sundarkand"
                )

                add_query(
                    "Sunderkand"
                )

                add_query(
                    "Sundar Kand"
                )

                add_query(
                    "Sunder Kand"
                )

                add_query(
                    "Sundar Kanda"
                )

    # --------------------------------------------------------
    # Short native title
    # --------------------------------------------------------

    title_words = clean_text(
        title
    ).split()

    if len(title_words) >= 3:

        add_query(
            " ".join(
                title_words[:3]
            )
        )

    if len(title_words) >= 2:

        add_query(
            " ".join(
                title_words[:5]
            )
        )

    # --------------------------------------------------------
    # Short romanized title
    # --------------------------------------------------------

    roman_title_words = clean_text(
        roman_title
    ).split()

    if len(roman_title_words) >= 2:

        add_query(
            " ".join(
                roman_title_words[:5]
            )
        )

    # --------------------------------------------------------
    # Final deduplication
    # --------------------------------------------------------

    final_queries = []

    seen = set()

    for query in queries:

        normalized = (
            query.lower().strip()
        )

        if normalized not in seen:

            seen.add(
                normalized
            )

            final_queries.append(
                query
            )

    return final_queries


# ============================================================
# OPEN LIBRARY SEARCH
# ============================================================

async def search_open_library(
    query: str,
    limit: int = 20
) -> list[dict[str, Any]]:

    params = {

        "q": query,

        "fields": (
            "key,title,author_name,"
            "first_publish_year,"
            "publisher,subject,"
            "cover_i,isbn"
        ),

        "limit": limit,
    }

    async with httpx.AsyncClient(
        timeout=15.0
    ) as client:

        response = await client.get(
            OPEN_LIBRARY_URL,
            params=params
        )

        response.raise_for_status()

        data = response.json()

    candidates = []

    for book in data.get(
        "docs",
        []
    ):

        candidates.append({

            "source": "Open Library",

            "key": book.get(
                "key"
            ),

            "title": book.get(
                "title",
                ""
            ),

            "author": (
                book.get(
                    "author_name",
                    [""]
                )[0]
                if book.get(
                    "author_name"
                )
                else ""
            ),

            "first_publish_year": (
                book.get(
                    "first_publish_year"
                )
            ),

            "publisher": (
                book.get(
                    "publisher",
                    [""]
                )[0]
                if book.get(
                    "publisher"
                )
                else ""
            ),

            "subject": (
                book.get(
                    "subject",
                    [""]
                )[0]
                if book.get(
                    "subject"
                )
                else ""
            ),

            "cover_i": book.get(
                "cover_i"
            ),

            "cover_url": (
                f"https://covers.openlibrary.org/b/id/"
                f"{book.get('cover_i')}-L.jpg"
                if book.get(
                    "cover_i"
                )
                else None
            ),

            "isbn": (
                book.get(
                    "isbn",
                    [""]
                )[0]
                if book.get(
                    "isbn"
                )
                else ""
            ),

            "isbn_list": book.get(
                "isbn",
                []
            ),
        })

    return candidates


# ============================================================
# MAIN OPEN LIBRARY BOOK SEARCH
# ============================================================

async def search_books(
    title: str,
    author: str = "",
    search_variants: list[str] | None = None,
    year: int | None = None,
) -> list[dict[str, Any]]:

    queries = generate_search_queries(
        title=title,
        author=author,
        search_variants=search_variants
    )

    print(
        "\nOpen Library search queries:"
    )

    for query in queries:

        print(
            f"  - {query}"
        )

    all_candidates = []

    seen_keys = set()

    for query in queries:

        try:

            results = await search_open_library(
                query
            )

            print(
                f"Open Library '{query}': "
                f"{len(results)} results"
            )

            for book in results:

                key = book.get(
                    "key"
                )

                if key:

                    if key in seen_keys:
                        continue

                    seen_keys.add(
                        key
                    )

                all_candidates.append(
                    book
                )

        except httpx.HTTPError as error:

            print(
                "Open Library search failed "
                f"for '{query}': {error}"
            )

        except Exception as error:

            print(
                "Open Library unexpected error "
                f"for '{query}': {error}"
            )

    return all_candidates