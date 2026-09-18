from difflib import SequenceMatcher
from typing import Any
import re

from PIL import Image

from app.services.cover_similarity_service import (
    calculate_cover_similarity
)


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize(value: Any) -> str:
    """
    Normalize text for comparison.

    Important:
    - Keeps + and # for C++ and C#
    - Normalizes Mathematics -> Maths
    - Normalizes Roman school classes
    """

    if value is None:
        return ""

    text = str(value).lower().strip()

    replacements = {
        "mathematics": "maths",
        "mathematical": "maths",

        "class ix": "class 9",
        "class x": "class 10",
        "class xi": "class 11",
        "class xii": "class 12",

        "grade ix": "grade 9",
        "grade x": "grade 10",
        "grade xi": "grade 11",
        "grade xii": "grade 12",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Preserve + and #.
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
# BASIC STRING SIMILARITY
# ============================================================

def similarity(a: Any, b: Any) -> float:
    """
    Return similarity from 0.0 to 1.0.
    """

    a = normalize(a)
    b = normalize(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


# ============================================================
# TOKENIZATION
# ============================================================

def tokenize(value: Any) -> set[str]:
    """
    Convert text into meaningful comparison tokens.
    """

    text = normalize(value)

    if not text:
        return set()

    words = text.split()

    stop_words = {
        "the",
        "a",
        "an",
        "of",
        "for",
        "and",
        "in",
        "to",

        "book",
        "books",
        "textbook",
        "textbooks",

        "edition",
        "volume",
        "vol",
        "part",

        "class",
        "grade",
        "school",

        "study",
        "student",
        "students",
    }

    return {
        word
        for word in words
        if word not in stop_words
    }


# ============================================================
# TOKEN SIMILARITY
# ============================================================

def token_similarity(a: Any, b: Any) -> float:
    """
    Compare meaningful title words.

    Uses Jaccard similarity.
    """

    tokens_a = tokenize(a)
    tokens_b = tokenize(b)

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a.intersection(
        tokens_b
    )

    union = tokens_a.union(
        tokens_b
    )

    if not union:
        return 0.0

    return len(intersection) / len(union)


# ============================================================
# PROGRAMMING LANGUAGE DETECTION
# ============================================================

PROGRAMMING_TERMS = [
    "javascript",
    "c++",
    "c#",
    "python",
    "kotlin",
    "swift",
    "rust",
    "perl",
    "ruby",
    "php",
    "sql",
    "java",
]


def detect_programming_language(
    value: Any
) -> str | None:
    """
    Detect programming language.

    C is detected separately using a word boundary so that:

        C
        C Programming

    does not get confused with C++ or C#.
    """

    text = normalize(value)

    if not text:
        return None

    # More specific languages first.
    for term in PROGRAMMING_TERMS:
        if term in text:
            return term

    # Standalone C.
    if re.search(
        r"\bc\b",
        text
    ):
        return "c"

    return None


# ============================================================
# TITLE CORE
# ============================================================

def title_core(value: Any) -> str:
    """
    Remove edition-specific wording while keeping
    meaningful title information.
    """

    text = normalize(value)

    if not text:
        return ""

    removable_patterns = [
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

    for pattern in removable_patterns:
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
# TITLE SIMILARITY
# ============================================================

def title_similarity(
    a: Any,
    b: Any
) -> float:
    """
    Compare book titles from 0 to 100.

    Combines:
        40% sequence similarity
        60% token similarity

    Also protects technical titles such as:

        C vs C++
        C vs C#
        Java vs JavaScript
        Python vs Java
    """

    a_norm = normalize(a)
    b_norm = normalize(b)

    if not a_norm or not b_norm:
        return 0.0

    if a_norm == b_norm:
        return 100.0

    a_language = detect_programming_language(
        a_norm
    )

    b_language = detect_programming_language(
        b_norm
    )

    # Explicit technical mismatch.
    if (
        a_language
        and b_language
        and a_language != b_language
    ):
        return 0.0

    # Explicit C++ protection.
    if (
        ("c++" in a_norm)
        != ("c++" in b_norm)
    ):
        if (
            "c++" in a_norm
            or "c++" in b_norm
        ):
            return 0.0

    # Explicit C# protection.
    if (
        ("c#" in a_norm)
        != ("c#" in b_norm)
    ):
        if (
            "c#" in a_norm
            or "c#" in b_norm
        ):
            return 0.0

    sequence_score = (
        SequenceMatcher(
            None,
            a_norm,
            b_norm
        ).ratio()
        * 100
    )

    tokens_a = tokenize(a_norm)
    tokens_b = tokenize(b_norm)

    if not tokens_a or not tokens_b:
        token_score = 0.0

    else:
        intersection = len(
            tokens_a & tokens_b
        )

        union = len(
            tokens_a | tokens_b
        )

        token_score = (
            intersection / union * 100
            if union > 0
            else 0.0
        )

    score = (
        sequence_score * 0.40
        + token_score * 0.60
    )

    # ========================================================
    # SHORT TITLE / SUBTITLE PROTECTION
    # ========================================================

    core_a = title_core(a_norm)
    core_b = title_core(b_norm)

    core_tokens_a = tokenize(core_a)
    core_tokens_b = tokenize(core_b)

    if (
        core_tokens_a
        and core_tokens_b
    ):

        intersection = (
            core_tokens_a
            & core_tokens_b
        )

        # If every token from the shorter title exists
        # in the longer title, this is likely the same work.
        shorter = min(
            len(core_tokens_a),
            len(core_tokens_b)
        )

        if (
            shorter > 0
            and len(intersection) == shorter
        ):
            score = max(
                score,
                85.0
            )

    return min(
        100.0,
        max(
            0.0,
            score
        )
    )


# ============================================================
# CLASS / GRADE EXTRACTION
# ============================================================

def extract_class(
    value: Any
) -> int | None:
    """
    Extract school class / grade.
    """

    if not value:
        return None

    text = str(value).lower()

    roman_classes = {
        "xii": 12,
        "xi": 11,
        "x": 10,
        "ix": 9,
        "viii": 8,
        "vii": 7,
        "vi": 6,
        "v": 5,
        "iv": 4,
        "iii": 3,
        "ii": 2,
        "i": 1,
    }

    # Numeric class.
    match = re.search(
        r"(?:class|grade)\s*(\d{1,2})",
        text
    )

    if match:
        return int(
            match.group(1)
        )

    # Roman class.
    match = re.search(
        r"(?:class|grade)\s*"
        r"(xii|xi|x|ix|viii|vii|vi|v|iv|iii|ii|i)\b",
        text
    )

    if match:
        return roman_classes.get(
            match.group(1)
        )

    return None


# ============================================================
# SUBJECT GROUPS
# ============================================================

SUBJECT_GROUPS = {

    "maths": {
        "math",
        "maths",
        "algebra",
        "geometry",
        "trigonometry",
        "arithmetic",
        "calculus",
        "statistics",
    },

    "science": {
        "science",
        "physics",
        "chemistry",
        "biology",
        "scientific",
    },

    "english": {
        "english",
        "grammar",
        "literature",
        "poetry",
        "language",
    },

    "history": {
        "history",
        "historical",
        "ancient",
        "medieval",
        "modern",
    },

    "geography": {
        "geography",
        "geographical",
        "maps",
        "earth",
    },

    "computer": {
        "computer",
        "computers",
        "programming",
        "coding",
        "informatics",
        "software",
        "algorithm",
        "algorithms",
    },

    "economics": {
        "economics",
        "economic",
        "finance",
        "financial",
    },

    "politics": {
        "politics",
        "political",
        "civics",
        "government",
    },

    "religion": {
        "religion",
        "religious",
        "bible",
        "quran",
        "gita",
        "ramayana",
        "mahabharata",
    },
}


# ============================================================
# SUBJECT DETECTION
# ============================================================

def detect_subject(
    value: Any
) -> str | None:
    """
    Detect broad subject category.
    """

    if not value:
        return None

    text = normalize(value)

    words = set(
        text.split()
    )

    for subject, keywords in SUBJECT_GROUPS.items():

        if words.intersection(
            keywords
        ):
            return subject

    return None


# ============================================================
# SUBJECT MATCH
# ============================================================

def subject_match(
    identified_title: Any,
    identified_subject: Any,
    candidate_title: Any,
    candidate_subject: Any
) -> tuple[float, bool]:
    """
    Returns:

        (subject_score, clear_mismatch)
    """

    identified_detected = (
        detect_subject(
            identified_title
        )
        or detect_subject(
            identified_subject
        )
    )

    candidate_detected = (
        detect_subject(
            candidate_title
        )
        or detect_subject(
            candidate_subject
        )
    )

    if not identified_detected:
        return 0.0, False

    if not candidate_detected:
        return 0.0, False

    if (
        identified_detected
        == candidate_detected
    ):
        return 1.0, False

    return 0.0, True


# ============================================================
# ISBN NORMALIZATION
# ============================================================

def normalize_isbn(
    isbn: Any
) -> str:
    """
    Normalize ISBN-10 / ISBN-13.
    """

    if not isbn:
        return ""

    return re.sub(
        r"[^0-9Xx]",
        "",
        str(isbn)
    ).upper()


# ============================================================
# AUTHOR NORMALIZATION
# ============================================================

def normalize_author(
    value: Any
) -> str:
    """
    Normalize author names.

    Example:

        Yashavant Kanetkar
        Yashavant P. Kanetkar

    become comparable.
    """

    text = normalize(value)

    if not text:
        return ""

    tokens = []

    for token in text.split():

        # Remove single-letter initials.
        if len(token) == 1:
            continue

        tokens.append(
            token
        )

    return " ".join(
        tokens
    )


# ============================================================
# AUTHOR SIMILARITY
# ============================================================

def author_similarity(
    a: Any,
    b: Any
) -> float:
    """
    Compare author names from 0 to 1.
    """

    a_norm = normalize_author(a)
    b_norm = normalize_author(b)

    if not a_norm or not b_norm:
        return 0.0

    if a_norm == b_norm:
        return 1.0

    tokens_a = set(
        a_norm.split()
    )

    tokens_b = set(
        b_norm.split()
    )

    if not tokens_a or not tokens_b:
        return 0.0

    overlap = len(
        tokens_a & tokens_b
    )

    denominator = max(
        len(tokens_a),
        len(tokens_b)
    )

    token_score = (
        overlap / denominator
    )

    sequence_score = SequenceMatcher(
        None,
        a_norm,
        b_norm
    ).ratio()

    return (
        token_score * 0.70
        + sequence_score * 0.30
    )


# ============================================================
# YEAR SIMILARITY
# ============================================================

def calculate_year_score(
    identified_year: Any,
    candidate_year: Any
) -> float:
    """
    Exact year = 1.0
    Within 2 years = 0.5
    Otherwise = 0.0
    """

    if (
        not identified_year
        or not candidate_year
    ):
        return 0.0

    try:

        identified = int(
            identified_year
        )

        candidate = int(
            candidate_year
        )

    except (
        ValueError,
        TypeError
    ):
        return 0.0

    if identified == candidate:
        return 1.0

    if abs(
        identified - candidate
    ) <= 2:
        return 0.5

    return 0.0


# ============================================================
# EDITION SCORE
# ============================================================

def calculate_edition_score(
    identified_data: dict[str, Any],
    candidate: dict[str, Any]
) -> float | None:
    """
    Calculate edition confidence.

    IMPORTANT:
    Unknown information is neutral.

    If Gemini does not know ISBN/publisher/year,
    we do NOT punish the candidate.
    """

    identified_year = (
        identified_data.get(
            "publication_year"
        )
    )

    identified_publisher = normalize(
        identified_data.get(
            "publisher"
        )
    )

    identified_isbn = normalize_isbn(
        identified_data.get(
            "isbn"
        )
    )

    candidate_year = candidate.get(
        "first_publish_year"
    )

    if candidate_year is None:
        candidate_year = candidate.get(
            "publication_year"
        )

    candidate_publisher = normalize(
        candidate.get(
            "publisher"
        )
    )

    # --------------------------------------------------------
    # Candidate ISBNs
    # --------------------------------------------------------

    candidate_isbns = set()

    candidate_isbn = normalize_isbn(
        candidate.get(
            "isbn"
        )
    )

    if candidate_isbn:
        candidate_isbns.add(
            candidate_isbn
        )

    for isbn in candidate.get(
        "isbn_list",
        []
    ):

        normalized = normalize_isbn(
            isbn
        )

        if normalized:
            candidate_isbns.add(
                normalized
            )

    # --------------------------------------------------------
    # Signals
    # --------------------------------------------------------

    edition_signals = 0
    edition_matches = 0

    # Year.
    if (
        identified_year
        and candidate_year
    ):

        edition_signals += 1

        if (
            calculate_year_score(
                identified_year,
                candidate_year
            )
            == 1.0
        ):
            edition_matches += 1

    # Publisher.
    if (
        identified_publisher
        and candidate_publisher
    ):

        edition_signals += 1

        publisher_score = similarity(
            identified_publisher,
            candidate_publisher
        )

        if publisher_score >= 0.85:
            edition_matches += 1

    # ISBN.
    if identified_isbn:

        edition_signals += 1

        if identified_isbn in candidate_isbns:
            edition_matches += 1

    # --------------------------------------------------------
    # Unknown edition information = neutral
    # --------------------------------------------------------

    if edition_signals == 0:
        return None

    return (
        edition_matches
        / edition_signals
    ) * 100.0


# ============================================================
# RANK CANDIDATES
# ============================================================

def rank_candidates(
    identified_data: dict[str, Any],
    candidates: list[dict[str, Any]],
    uploaded_image: Image.Image | None = None
) -> list[dict[str, Any]]:

    # ========================================================
    # IDENTIFIED BOOK
    # ========================================================

    identified_title = normalize(
        identified_data.get(
            "title"
        )
    )

    identified_author = normalize(
        identified_data.get(
            "author"
        )
    )

    identified_year = (
        identified_data.get(
            "publication_year"
        )
    )

    identified_publisher = normalize(
        identified_data.get(
            "publisher"
        )
    )

    identified_subject = normalize(
        identified_data.get(
            "subject"
        )
    )

    identified_class = extract_class(
        identified_title
    )

    identified_language = (
        detect_programming_language(
            identified_title
        )
    )

    ranked = []

    # ========================================================
    # PROCESS EACH CANDIDATE
    # ========================================================

    for book in candidates:

        candidate_title = normalize(
            book.get(
                "title"
            )
        )

        candidate_author = normalize(
            book.get(
                "author"
            )
        )

        candidate_year = (
            book.get(
                "first_publish_year"
            )
        )

        if candidate_year is None:

            candidate_year = (
                book.get(
                    "publication_year"
                )
            )

        candidate_publisher = normalize(
            book.get(
                "publisher"
            )
        )

        candidate_subject = normalize(
            book.get(
                "subject"
            )
        )

        candidate_class = extract_class(
            candidate_title
        )

        candidate_language = (
            detect_programming_language(
                candidate_title
            )
        )

        # ====================================================
        # TITLE SCORE
        # ====================================================

        title_score = (
            title_similarity(
                identified_title,
                candidate_title
            )
            / 100.0
        )

        # ====================================================
        # AUTHOR SCORE
        # ========================================================

        author_score = author_similarity(
            identified_author,
            candidate_author
        )

        # ====================================================
        # YEAR SCORE
        # ========================================================

        year_score = calculate_year_score(
            identified_year,
            candidate_year
        )

        # ====================================================
        # PUBLISHER SCORE
        # ========================================================

        publisher_score = similarity(
            identified_publisher,
            candidate_publisher
        )

        # ====================================================
        # SUBJECT SCORE
        # ========================================================

        subject_score = similarity(
            identified_subject,
            candidate_subject
        )

        detected_subject_score, subject_mismatch = (
            subject_match(
                identified_title,
                identified_subject,
                candidate_title,
                candidate_subject
            )
        )

        # If broad subject detection gives a stronger signal,
        # use it.
        if detected_subject_score > 0:
            subject_score = max(
                subject_score,
                detected_subject_score
            )

        # ====================================================
        # CLASS MATCH
        # ====================================================

        class_match = True

        if (
            identified_class is not None
            and candidate_class is not None
        ):

            if (
                identified_class
                != candidate_class
            ):
                class_match = False

        # ====================================================
        # WORK SCORE
        # ====================================================

        # Work identity is much more important than exact
        # edition metadata.
        weights = {
            "title": 60,
            "author": 25,
            "subject": 10,
            "year": 3,
            "publisher": 2,
        }

        weighted_score = 0.0
        total_weight = 0

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        if (
            identified_title
            and candidate_title
        ):

            weighted_score += (
                title_score
                * weights["title"]
            )

            total_weight += (
                weights["title"]
            )

        # ----------------------------------------------------
        # Author
        # ----------------------------------------------------

        if (
            identified_author
            and candidate_author
        ):

            weighted_score += (
                author_score
                * weights["author"]
            )

            total_weight += (
                weights["author"]
            )

        # ----------------------------------------------------
        # Subject
        # ----------------------------------------------------

        if (
            identified_subject
            or detect_subject(
                identified_title
            )
        ):

            if (
                candidate_subject
                or detect_subject(
                    candidate_title
                )
            ):

                weighted_score += (
                    subject_score
                    * weights["subject"]
                )

                total_weight += (
                    weights["subject"]
                )

        # ----------------------------------------------------
        # Year
        # ----------------------------------------------------

        if (
            identified_year
            and candidate_year
        ):

            weighted_score += (
                year_score
                * weights["year"]
            )

            total_weight += (
                weights["year"]
            )

        # ----------------------------------------------------
        # Publisher
        # ----------------------------------------------------

        if (
            identified_publisher
            and candidate_publisher
        ):

            weighted_score += (
                publisher_score
                * weights["publisher"]
            )

            total_weight += (
                weights["publisher"]
            )

        # ----------------------------------------------------
        # Base score
        # ----------------------------------------------------

        if total_weight > 0:

            work_score = (
                weighted_score
                / total_weight
            ) * 100.0

        else:

            work_score = 0.0

        # ====================================================
        # HARD MISMATCH: CLASS
        # ====================================================

        if not class_match:

            work_score *= 0.45

        # ====================================================
        # HARD MISMATCH: SUBJECT
        # ====================================================

        if subject_mismatch:

            work_score *= 0.45

        # ====================================================
        # PROGRAMMING LANGUAGE PROTECTION
        # ====================================================

        technical_mismatch = False

        if (
            identified_language
            and candidate_language
            and identified_language
            != candidate_language
        ):

            technical_mismatch = True
            work_score *= 0.10

        # ----------------------------------------------------
        # C vs C++
        # ----------------------------------------------------

        if (
            ("c++" in identified_title)
            != ("c++" in candidate_title)
        ):

            if (
                "c++" in identified_title
                or "c++" in candidate_title
            ):

                technical_mismatch = True
                work_score *= 0.10

        # ----------------------------------------------------
        # C vs C#
        # ----------------------------------------------------

        if (
            ("c#" in identified_title)
            != ("c#" in candidate_title)
        ):

            if (
                "c#" in identified_title
                or "c#" in candidate_title
            ):

                technical_mismatch = True
                work_score *= 0.10

        # ====================================================
        # TITLE QUALITY PENALTIES
        # ====================================================

        if title_score < 0.20:

            work_score *= 0.25

        elif title_score < 0.40:

            work_score *= 0.50

        # Both title and author poor.
        if (
            title_score < 0.45
            and author_score < 0.45
        ):

            work_score *= 0.50

        work_score = min(
            100.0,
            max(
                0.0,
                work_score
            )
        )

        # ====================================================
        # EDITION SCORE
        # ====================================================

        edition_score = calculate_edition_score(
            identified_data,
            book
        )

        # ====================================================
        # COVER SIMILARITY
        # ====================================================

        cover_similarity = None

        if uploaded_image is not None:

            try:

                cover_similarity = (
                    calculate_cover_similarity(
                        uploaded_image,
                        book.get(
                            "cover_url"
                        )
                    )
                )

            except Exception as exc:

                print(
                    "Cover similarity failed "
                    f"for '{candidate_title}': "
                    f"{exc}"
                )

                cover_similarity = None

        # ====================================================
        # FINAL SCORE
        # ====================================================

        if cover_similarity is not None:

            relevance_score = (
                work_score * 0.80
                + cover_similarity * 0.20
            )

        else:

            relevance_score = work_score

        # ====================================================
        # STRONG WORK MATCH PROTECTION
        # ========================================================

        # If the textual identification is extremely strong,
        # do not allow a mediocre cover match to drag the
        # candidate too far down.
        if (
            work_score >= 85.0
            and not technical_mismatch
            and class_match
            and not subject_mismatch
        ):

            relevance_score = max(
                relevance_score,
                work_score * 0.90
            )

        # ====================================================
        # TECHNICAL MISMATCH CANNOT BE RESCUED BY COVER
        # ====================================================

        if technical_mismatch:

            relevance_score *= 0.25

        # ====================================================
        # CLASS / SUBJECT MISMATCH
        # ====================================================

        if (
            not class_match
            or subject_mismatch
        ):

            relevance_score *= 0.60

        # ====================================================
        # FINAL TITLE PENALTY
        # ====================================================

        if title_score < 0.20:

            relevance_score *= 0.25

        elif title_score < 0.50:

            relevance_score *= 0.60

        relevance_score = min(
            100.0,
            max(
                0.0,
                relevance_score
            )
        )

        # ====================================================
        # MATCH TYPE
        # ====================================================

        if (
            work_score >= 85.0
            and title_score >= 0.80
            and class_match
            and not subject_mismatch
            and not technical_mismatch
        ):

            match_type = (
                "Strong work match"
            )

        elif (
            work_score >= 70.0
            and title_score >= 0.60
            and class_match
            and not subject_mismatch
            and not technical_mismatch
        ):

            match_type = (
                "Likely work match"
            )

        elif work_score >= 50.0:

            match_type = (
                "Possible work match"
            )

        else:

            match_type = (
                "Weak match"
            )

        # ====================================================
        # COPY RESULT
        # ====================================================

        book_copy = dict(
            book
        )

        # ----------------------------------------------------
        # Scores
        # ----------------------------------------------------

        book_copy[
            "work_score"
        ] = round(
            work_score,
            2
        )

        book_copy[
            "edition_score"
        ] = (
            round(
                edition_score,
                2
            )
            if edition_score is not None
            else None
        )

        book_copy[
            "cover_similarity_score"
        ] = (
            round(
                cover_similarity,
                2
            )
            if cover_similarity is not None
            else None
        )

        book_copy[
            "relevance_score"
        ] = round(
            relevance_score,
            2
        )

        # ----------------------------------------------------
        # Match information
        # ----------------------------------------------------

        book_copy[
            "match_type"
        ] = match_type

        # ----------------------------------------------------
        # Debug information
        # ----------------------------------------------------

        book_copy[
            "title_match_score"
        ] = round(
            title_score * 100.0,
            2
        )

        book_copy[
            "author_match_score"
        ] = round(
            author_score * 100.0,
            2
        )

        book_copy[
            "year_match_score"
        ] = round(
            year_score * 100.0,
            2
        )

        book_copy[
            "publisher_match_score"
        ] = round(
            publisher_score * 100.0,
            2
        )

        book_copy[
            "subject_match_score"
        ] = round(
            subject_score * 100.0,
            2
        )

        book_copy[
            "class_match"
        ] = class_match

        book_copy[
            "subject_mismatch"
        ] = subject_mismatch

        book_copy[
            "technical_mismatch"
        ] = technical_mismatch

        book_copy[
            "identified_programming_language"
        ] = identified_language

        book_copy[
            "candidate_programming_language"
        ] = candidate_language

        # ----------------------------------------------------
        # Append
        # ----------------------------------------------------

        ranked.append(
            book_copy
        )

    # ========================================================
    # SORT
    # ========================================================

    ranked.sort(
        key=lambda item: (
            item.get(
                "relevance_score",
                0
            ),
            item.get(
                "work_score",
                0
            )
        ),
        reverse=True
    )

    return ranked