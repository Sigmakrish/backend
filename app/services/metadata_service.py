from typing import Any


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(value: Any) -> str:
    """Convert a value to clean text."""

    if value is None:
        return ""

    return str(value).strip()


def first_non_empty(*values: Any) -> Any:
    """
    Return the first value that is not empty.
    """

    for value in values:

        if value is None:
            continue

        if isinstance(value, str) and not value.strip():
            continue

        if isinstance(value, list) and not value:
            continue

        return value

    return ""


def normalize_isbn(isbn: Any) -> str:
    """Normalize an ISBN."""

    if not isbn:
        return ""

    isbn = str(isbn).strip()

    return "".join(
        character
        for character in isbn
        if character.isdigit()
        or character.upper() == "X"
    ).upper()


def normalize_isbn_list(
    values: Any
) -> list[str]:
    """
    Normalize and deduplicate a list of ISBNs.
    """

    if not values:
        return []

    if isinstance(values, str):
        values = [values]

    result = []

    for value in values:

        isbn = normalize_isbn(
            value
        )

        if (
            isbn
            and isbn not in result
        ):
            result.append(
                isbn
            )

    return result


def normalize_authors(
    value: Any
) -> list[str]:
    """
    Normalize author information into a list.
    """

    if not value:
        return []

    if isinstance(value, str):
        return [value.strip()]

    if isinstance(value, list):

        result = []

        for author in value:

            if isinstance(
                author,
                dict
            ):
                name = author.get(
                    "name",
                    ""
                )
            else:
                name = author

            name = clean_text(
                name
            )

            if name:
                result.append(
                    name
                )

        return result

    return []


def normalize_subjects(
    value: Any
) -> list[str]:
    """
    Normalize subjects into a list.
    """

    if not value:
        return []

    if isinstance(value, str):
        return [value.strip()]

    if isinstance(value, list):

        result = []

        for subject in value:

            if isinstance(
                subject,
                dict
            ):
                subject = subject.get(
                    "name",
                    ""
                )

            subject = clean_text(
                subject
            )

            if subject:
                result.append(
                    subject
                )

        return result

    return []


def normalize_year(
    value: Any
) -> int | None:
    """
    Convert publication year to integer.
    """

    if value is None:
        return None

    try:

        year = int(
            str(value)[:4]
        )

        if 1000 <= year <= 2100:
            return year

    except (
        ValueError,
        TypeError
    ):
        pass

    return None


# ============================================================
# NORMALIZE ONE BOOK
# ============================================================

def normalize_book_metadata(
    book: dict[str, Any]
) -> dict[str, Any]:
    """
    Convert an Open Library or Google Books
    candidate into a common RareBook AI format.
    """

    source = clean_text(
        book.get("source")
    )

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title = clean_text(
        book.get("title")
    )

    # --------------------------------------------------------
    # AUTHORS
    # --------------------------------------------------------

    authors = normalize_authors(
        first_non_empty(
            book.get("authors"),
            book.get("author")
        )
    )

    author = ""

    if authors:
        author = authors[0]

    # --------------------------------------------------------
    # YEAR
    # --------------------------------------------------------

    publication_year = normalize_year(
        first_non_empty(
            book.get(
                "publication_year"
            ),
            book.get(
                "first_publish_year"
            ),
            book.get(
                "published_date"
            )
        )
    )

    # --------------------------------------------------------
    # PUBLISHER
    # --------------------------------------------------------

    publisher = clean_text(
        book.get("publisher")
    )

    # Google Books can sometimes provide
    # publisher as a list in custom data.
    if isinstance(
        book.get("publisher"),
        list
    ):

        publishers = (
            book.get("publisher")
        )

        publisher = (
            clean_text(
                publishers[0]
            )
            if publishers
            else ""
        )

    # --------------------------------------------------------
    # ISBN
    # --------------------------------------------------------

    isbn_list = []

    isbn_list.extend(
        normalize_isbn_list(
            book.get(
                "isbn_list"
            )
        )
    )

    isbn_list.extend(
        normalize_isbn_list(
            book.get(
                "isbns"
            )
        )
    )

    single_isbn = normalize_isbn(
        book.get("isbn")
    )

    if (
        single_isbn
        and single_isbn not in isbn_list
    ):
        isbn_list.append(
            single_isbn
        )

    isbn10 = normalize_isbn(
        book.get("isbn10")
    )

    isbn13 = normalize_isbn(
        book.get("isbn13")
    )

    if (
        isbn10
        and isbn10 not in isbn_list
    ):
        isbn_list.append(
            isbn10
        )

    if (
        isbn13
        and isbn13 not in isbn_list
    ):
        isbn_list.append(
            isbn13
        )

    # --------------------------------------------------------
    # PRIMARY ISBN
    # --------------------------------------------------------

    primary_isbn = first_non_empty(
        isbn13,
        isbn10,
        isbn_list[0]
        if isbn_list
        else ""
    )

    # --------------------------------------------------------
    # SUBJECTS
    # --------------------------------------------------------

    subjects = normalize_subjects(
        first_non_empty(
            book.get("subjects"),
            book.get("subject")
        )
    )

    subject = ""

    if subjects:
        subject = subjects[0]

    # --------------------------------------------------------
    # LANGUAGE
    # --------------------------------------------------------

    language = clean_text(
        book.get("language")
    )

    language_code = clean_text(
        book.get("language_code")
    )

    # --------------------------------------------------------
    # COVER
    # --------------------------------------------------------

    cover_url = clean_text(
        book.get("cover_url")
    )

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    description = clean_text(
        book.get("description")
    )

    # --------------------------------------------------------
    # BOOK KEY
    # --------------------------------------------------------

    key = clean_text(
        book.get("key")
    )

    # --------------------------------------------------------
    # WORK / EDITION
    # --------------------------------------------------------

    work_key = clean_text(
        book.get("work_key")
    )

    edition_key = clean_text(
        book.get("edition_key")
    )

    # --------------------------------------------------------
    # NORMALIZED RESULT
    # --------------------------------------------------------

    normalized = {

        "source": source,

        "key": key,

        "title": title,

        "authors": authors,

        "author": author,

        "publication_year": (
            publication_year
        ),

        "publisher": publisher,

        "language": language,

        "language_code": language_code,

        "subjects": subjects,

        "subject": subject,

        "isbn": primary_isbn,

        "isbn10": isbn10,

        "isbn13": isbn13,

        "isbn_list": isbn_list,

        "cover_url": cover_url,

        "description": description,

        "work_key": work_key,

        "edition_key": edition_key,
    }

    return normalized


# ============================================================
# NORMALIZE MULTIPLE BOOKS
# ============================================================

def normalize_book_list(
    books: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Normalize multiple book candidates.
    """

    normalized_books = []

    for book in books:

        if not isinstance(
            book,
            dict
        ):
            continue

        normalized_books.append(
            normalize_book_metadata(
                book
            )
        )

    return normalized_books