from io import BytesIO

from app.routes.auth import router as auth_router

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException
)

from fastapi.middleware.cors import CORSMiddleware

from PIL import Image

from app.services.fulltext_service import (
    fetch_book_fulltext_from_access
)

from app.services.gemini_service import (
    ask_gemini,
    identify_book,
    identify_book_from_text,
    generate_book_summary,
    ask_about_book,
)

from app.services.ranking_service import (
    rank_candidates
)

from app.services.book_search_service import (
    search_books
)

from app.services.google_books_service import (
    search_google_books
)

from app.services.candidate_service import (
    merge_candidates,
    filter_candidates
)

from app.services.metadata_verification_service import (
    verify_candidate_sources
)

from app.services.access_service import (
    build_access_records,
    search_internet_archive_candidates
)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="RareBook AI API",
    description="Backend API for RareBook AI",
    version="1.0.0"
)
app.include_router(auth_router)

# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "RareBook AI API is running"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# ============================================================
# GEMINI TEST
# ============================================================

@app.get("/gemini-test")
def gemini_test():

    answer = ask_gemini(
        "In one sentence, explain what a rare book is."
    )

    return {
        "answer": answer
    }


# ============================================================
# BOOK IDENTIFICATION ONLY
# ============================================================

@app.post("/api/books/identify")
async def identify_book_endpoint(
    image: UploadFile = File(...)
):

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/jpg"
    }

    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG and PNG images "
                "are supported."
            )
        )

    image_bytes = await image.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded image is empty."
        )

    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="Image size must be below 10 MB."
        )

    try:

        result = identify_book(
            image_bytes,
            image.content_type
        )

    except Exception as e:

        print(
            f"Gemini identification error: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Book identification failed."
        )

    return {
        "success": True,
        "identification": result.model_dump()
    }


# ============================================================
# RANKING TEST
# ============================================================

@app.post("/api/books/rank-test")
async def rank_test():

    identified = {

        "title": "The Origin of Species",

        "author": "Charles Darwin",

        "publication_year": 1859,

        "publisher": "John Murray",

        "language": "English",

        "subject": "Evolution"
    }

    candidates = [

        {
            "title": "On the Origin of Species",
            "author": "Charles Darwin",
            "publication_year": 1859,
            "publisher": "John Murray",
            "language": "English",
            "subject": "Evolution"
        },

        {
            "title": "The Descent of Man",
            "author": "Charles Darwin",
            "publication_year": 1871,
            "publisher": "John Murray",
            "language": "English",
            "subject": "Evolution"
        },

        {
            "title": "Principles of Biology",
            "author": "Herbert Spencer",
            "publication_year": 1864,
            "publisher": "Williams and Norgate",
            "language": "English",
            "subject": "Biology"
        }

    ]

    ranked = rank_candidates(
        identified,
        candidates
    )

    return {
        "candidates": ranked
    }


# ============================================================
# BOOK SEARCH
# ============================================================

@app.get("/api/books/search")
async def search_books_endpoint(
    title: str = "",
    author: str = "",
    year: int | None = None
):

    books = await search_books(
        title=title,
        author=author,
        year=year
    )

    return {
        "success": True,
        "count": len(books),
        "books": books
    }


# ============================================================
# IDENTIFY + SEARCH + MERGE + FILTER
# + VERIFY + RANK + ACCESS
# ============================================================

@app.post("/api/books/identify-and-rank")
async def identify_and_rank(
    image: UploadFile = File(...)
):

    # ========================================================
    # 1. VALIDATE IMAGE
    # ========================================================

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/jpg"
    }

    if image.content_type not in allowed_types:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG and PNG images "
                "are supported."
            )
        )

    # ========================================================
    # 2. READ IMAGE
    # ========================================================

    image_bytes = await image.read()

    if not image_bytes:

        raise HTTPException(
            status_code=400,
            detail="The uploaded image is empty."
        )

    # ========================================================
    # 3. SIZE LIMIT
    # ========================================================

    if len(image_bytes) > 10 * 1024 * 1024:

        raise HTTPException(
            status_code=400,
            detail=(
                "Image size must be below 10 MB."
            )
        )

    # ========================================================
    # 4. OPEN IMAGE
    # ========================================================

    try:

        uploaded_image = Image.open(
            BytesIO(image_bytes)
        ).convert("RGB")

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid image file."
        )

    # ========================================================
    # 5. GEMINI IDENTIFICATION
    # ========================================================

    try:

        identified = identify_book(
            image_bytes,
            image.content_type
        )

    except Exception as e:

        print(
            f"Gemini identification error: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Book identification failed."
        )

    identified_data = (
        identified.model_dump()
    )

    # ========================================================
    # 6. EXTRACT IDENTIFICATION DATA
    # ========================================================

    title = identified_data.get(
        "title",
        ""
    )

    author = identified_data.get(
        "author",
        ""
    )

    search_variants = (
        identified_data.get(
            "search_variants",
            []
        )
    )

    # ========================================================
    # 7. DEBUG IDENTIFICATION
    # ========================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "RAREBOOK AI SEARCH DEBUG"
    )

    print(
        "=" * 60
    )

    print(
        f"Gemini Title  : {title}"
    )

    print(
        f"Gemini Author : {author}"
    )

    print(
        "Gemini Language : "
        f"{identified_data.get('language', '')}"
    )

    print(
        "Language Code : "
        f"{identified_data.get('language_code', '')}"
    )

    print(
        "Search Variants : "
        f"{search_variants}"
    )

    # ========================================================
    # 8. OPEN LIBRARY SEARCH
    # ========================================================

    try:

        open_library_candidates = (
            await search_books(
                title=title,
                author=author,
                search_variants=search_variants
            )
        )

    except Exception as e:

        print(
            f"Open Library search error: {e}"
        )

        open_library_candidates = []

    print(
        "Open Library results: "
        f"{len(open_library_candidates)}"
    )

    # ========================================================
    # 9. GOOGLE BOOKS SEARCH
    # ========================================================

    try:

        google_books_candidates = (
            await search_google_books(
                title=title,
                author=author
            )
        )

    except Exception as e:

        print(
            f"Google Books search error: {e}"
        )

        google_books_candidates = []

    print(
        "Google Books results: "
        f"{len(google_books_candidates)}"
    )

    # ========================================================
    # 10. INTERNET ARCHIVE CANDIDATE DISCOVERY
    # ========================================================

    try:

        internet_archive_candidates = (
            await search_internet_archive_candidates(
                title=title,
                author=author,
                search_variants=search_variants
            )
        )

    except Exception as e:

        print(
            "Internet Archive candidate "
            f"search error: {e}"
        )

        internet_archive_candidates = []

    print(
        "Internet Archive candidates: "
        f"{len(internet_archive_candidates)}"
    )

    # ========================================================
    # 11. COMBINE ALL SOURCES
    # ========================================================

    all_candidates = (
        open_library_candidates
        + google_books_candidates
        + internet_archive_candidates
    )

    print(
        "Total candidates before merging: "
        f"{len(all_candidates)}"
    )

    # ========================================================
    # 12. MERGE DUPLICATES
    # ========================================================

    candidates = merge_candidates(
        all_candidates
    )

    print(
        "Total candidates after merging: "
        f"{len(candidates)}"
    )

    # ========================================================
    # 13. INTELLIGENT CANDIDATE FILTERING
    # ========================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "CANDIDATE FILTERING"
    )

    print(
        "=" * 60
    )

    before_filter = len(
        candidates
    )

    candidates = filter_candidates(
        candidates,
        identified_data,
        max_candidates=30
    )

    after_filter = len(
        candidates
    )

    print(
        "Candidates before filtering: "
        f"{before_filter}"
    )

    print(
        "Candidates after filtering: "
        f"{after_filter}"
    )

    print(
        "=" * 60
    )

    # ========================================================
    # 14. METADATA VERIFICATION
    # ========================================================

    for book in candidates:

        try:

            verification = (
                verify_candidate_sources(
                    book
                )
            )

        except Exception as e:

            print(
                "Metadata verification error: "
                f"{e}"
            )

            verification = {
                "verification_score": None,
                "verification_status": (
                    "Verification unavailable"
                ),
                "field_matches": {}
            }

        book[
            "verification_score"
        ] = verification.get(
            "verification_score"
        )

        book[
            "verification_status"
        ] = verification.get(
            "verification_status"
        )

        book[
            "field_matches"
        ] = verification.get(
            "field_matches",
            {}
        )

        book[
            "source_count"
        ] = len(
            book.get(
                "sources",
                []
            )
        )

    # ========================================================
    # 15. DEBUG VERIFICATION
    # ========================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "METADATA VERIFICATION"
    )

    print(
        "=" * 60
    )

    for index, book in enumerate(
        candidates[:10],
        start=1
    ):

        print(
            f"{index}. "
            f"{book.get('title', 'Unknown')} | "
            f"Sources: "
            f"{book.get('source_count', 0)} | "
            f"Verification: "
            f"{book.get('verification_score')} | "
            f"Status: "
            f"{book.get('verification_status')}"
        )

    print(
        "=" * 60
    )

    # ========================================================
    # 16. DEBUG CANDIDATES
    # ========================================================

    print(
        "\nCANDIDATES BEFORE RANKING"
    )

    print(
        "=" * 60
    )

    for index, book in enumerate(
        candidates[:10],
        start=1
    ):

        print(
            f"{index}. "
            f"{book.get('title', 'Unknown')} | "
            f"{book.get('author', 'Unknown')} | "
            f"{book.get('publisher', 'Unknown')} | "
            f"{book.get('source', 'Unknown')}"
        )

    print(
        "=" * 60
    )

    # ========================================================
    # 17. RANK CANDIDATES
    # ========================================================

    try:

        ranked_candidates = rank_candidates(
            identified_data,
            candidates,
            uploaded_image
        )

    except Exception as e:

        print(
            f"Ranking error: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Candidate ranking failed."
        )

    # ========================================================
    # 18. LEGAL ACCESS DISCOVERY
    # ========================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "LEGAL ACCESS DISCOVERY"
    )

    print(
        "=" * 60
    )

    ACCESS_MAX_CANDIDATES = 15

    # Clear access data
    for book in ranked_candidates:

        book["access"] = []

    # IA candidates first
    ia_candidates = [

        book

        for book in ranked_candidates

        if (
            str(
                book.get(
                    "source",
                    ""
                ) or ""
            ).lower() == "internet archive"

            or book.get("identifier")

            or book.get("archive_url")
        )
    ]

    # Other candidates
    other_candidates = [

        book

        for book in ranked_candidates

        if book not in ia_candidates
    ]

    # IA candidates first
    eligible_candidates = (
        ia_candidates
        + other_candidates
    )

    eligible_candidates = (
        eligible_candidates[
            :ACCESS_MAX_CANDIDATES
        ]
    )

    print(
        "Candidates eligible for access discovery: "
        f"{len(eligible_candidates)}"
    )

    # ========================================================
    # BUILD ACCESS RECORDS
    # ========================================================

    for book in eligible_candidates:

        try:

            access_records = (
                await build_access_records(
                    book
                )
            )

            book["access"] = (
                access_records
            )

        except Exception as e:

            print(
                "Access discovery failed for "
                f"{book.get('title', 'Unknown')}: "
                f"{e}"
            )

            book["access"] = []

        # Debug access
        print(
            f"{book.get('title', 'Unknown')} | "
            f"Access records: "
            f"{len(book.get('access', []))}"
        )

        for access in book.get(
            "access",
            []
        ):

            print(
                f"  Source    : "
                f"{access.get('source', '')}"
            )

            print(
                f"  Type      : "
                f"{access.get('access_type', '')}"
            )

            print(
                f"  Status    : "
                f"{access.get('status', '')}"
            )

            print(
                f"  Archive   : "
                f"{access.get('archive_url', '')}"
            )

            print(
                f"  Read      : "
                f"{access.get('read_online_url', '')}"
            )

            print(
                f"  PDF       : "
                f"{access.get('pdf_url', '')}"
            )

            print(
                f"  Download  : "
                f"{access.get('download_url', '')}"
            )

    print(
        "=" * 60
    )

    # ========================================================
    # 19. DEBUG FINAL RANKING
    # ========================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "FINAL RANKING RESULTS"
    )

    print(
        "=" * 60
    )

    for index, book in enumerate(
        ranked_candidates[:10],
        start=1
    ):

        print(
            f"{index}. "
            f"{book.get('title', 'Unknown')} | "
            f"Work: "
            f"{book.get('work_score')} | "
            f"Edition: "
            f"{book.get('edition_score')} | "
            f"Cover: "
            f"{book.get('cover_similarity_score')} | "
            f"Verification: "
            f"{book.get('verification_score')} | "
            f"Access: "
            f"{len(book.get('access', []))} | "
            f"Final: "
            f"{book.get('relevance_score')} | "
            f"Status: "
            f"{book.get('verification_status')}"
        )

    print(
        "=" * 60
    )

    # ========================================================
    # 20. FINAL RESPONSE
    # ========================================================

    return {
        "success": True,

        "identification": (
            identified_data
        ),

        "candidates": (
            ranked_candidates
        )
    }


# ============================================================
# TEXT IDENTIFICATION
# ============================================================

@app.post("/api/books/text-identify")
async def text_identify_book(payload: dict):

    text = str(
        payload.get(
            "text",
            ""
        )
    ).strip()

    if not text:

        raise HTTPException(
            status_code=400,
            detail="Text is required."
        )

    if len(text) > 2000:

        raise HTTPException(
            status_code=400,
            detail="Text must be 2000 characters or less."
        )

    try:

        identified = identify_book_from_text(
            text
        )

        identified_data = (
            identified.model_dump()
            if hasattr(
                identified,
                "model_dump"
            )
            else identified.dict()
        )

        title = identified_data.get(
            "title",
            ""
        )

        author = identified_data.get(
            "author",
            ""
        )

        search_variants = (
            identified_data.get(
                "search_variants",
                []
            )
        )

        if not title and not author:

            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not identify a book "
                    "from the provided text."
                )
            )

        # ----------------------------------------------------
        # OPEN LIBRARY
        # ----------------------------------------------------

        try:

            open_library_results = (
                await search_books(
                    title=title,
                    author=author,
                    search_variants=search_variants,
                )
            )

        except Exception as e:

            print(
                f"Open Library text search error: {e}"
            )

            open_library_results = []

        # ----------------------------------------------------
        # GOOGLE BOOKS
        # ----------------------------------------------------

        try:

            google_books_results = (
                await search_google_books(
                    title=title,
                    author=author,
                )
            )

        except Exception as e:

            print(
                f"Google Books text search error: {e}"
            )

            google_books_results = []

        # ----------------------------------------------------
        # INTERNET ARCHIVE
        # ----------------------------------------------------

        try:

            internet_archive_results = (
                await search_internet_archive_candidates(
                    title=title,
                    author=author,
                    search_variants=search_variants,
                )
            )

        except Exception as e:

            print(
                f"Internet Archive text search error: {e}"
            )

            internet_archive_results = []

        # ----------------------------------------------------
        # MERGE
        # ----------------------------------------------------

        all_candidates = merge_candidates(
            open_library_results
            + google_books_results
            + internet_archive_results
        )

        # ----------------------------------------------------
        # FILTER
        # ----------------------------------------------------

        filtered_candidates = filter_candidates(
            all_candidates,
            identified_data,
        )

        filtered_candidates = (
            filtered_candidates[:30]
        )

        # ----------------------------------------------------
        # VERIFICATION
        # ----------------------------------------------------

        verified_candidates = []

        for candidate in filtered_candidates:

            try:

                verification = (
                    verify_candidate_sources(
                        candidate
                    )
                )

            except Exception as e:

                print(
                    f"Text metadata verification error: {e}"
                )

                verification = {
                    "verification_score": None,
                    "verification_status": (
                        "Verification unavailable"
                    ),
                    "field_matches": {}
                }

            candidate["verification"] = (
                verification
            )

            verified_candidates.append(
                candidate
            )

        # ----------------------------------------------------
        # RANKING
        # ----------------------------------------------------

        ranked_candidates = rank_candidates(
            identified_data,
            verified_candidates,
        )

        # ----------------------------------------------------
        # ACCESS
        # ----------------------------------------------------

        ACCESS_MAX_CANDIDATES = 15

        for book in ranked_candidates:

            book["access"] = []

        ia_candidates = [

            book

            for book in ranked_candidates

            if (
                str(
                    book.get(
                        "source",
                        ""
                    ) or ""
                ).lower()
                == "internet archive"

                or book.get("identifier")

                or book.get("archive_url")
            )
        ]

        other_candidates = [

            book

            for book in ranked_candidates

            if book not in ia_candidates
        ]

        eligible_candidates = (
            ia_candidates
            + other_candidates
        )[:ACCESS_MAX_CANDIDATES]

        for book in eligible_candidates:

            try:

                access_records = (
                    await build_access_records(
                        book
                    )
                )

                book["access"] = (
                    access_records
                )

            except Exception as access_error:

                print(
                    f"Access discovery failed for "
                    f"{book.get('title', '')}: "
                    f"{access_error}"
                )

                book["access"] = []

        return {

            "success": True,

            "identification": (
                identified_data
            ),

            "candidates": (
                ranked_candidates
            )
        }

    except HTTPException:

        raise

    except Exception as e:

        print(
            f"Text identification error: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Text identification failed."
        )


# ============================================================
# BOOK SUMMARY
# ============================================================

@app.post("/api/books/{book_id}/summary")
async def book_summary(
    book_id: str,
    payload: dict
):

    book = payload.get(
        "book"
    )

    if not book or not isinstance(
        book,
        dict
    ):

        raise HTTPException(
            status_code=400,
            detail="Book information is required."
        )

    try:

        summary = generate_book_summary(
            book
        )

        return {

            "success": True,

            "book_id": book_id,

            "summary": summary,
        }

    except Exception as e:

        print(
            f"Summary generation error: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not generate book summary."
        )


# ============================================================
# NORMAL BOOK QUESTION
# ============================================================

@app.post("/api/books/{book_id}/ask")
async def ask_book_question(
    book_id: str,
    payload: dict
):

    book = payload.get(
        "book"
    )

    question = str(
        payload.get(
            "question",
            ""
        )
    ).strip()

    if not book or not isinstance(
        book,
        dict
    ):

        raise HTTPException(
            status_code=400,
            detail="Book information is required."
        )

    if not question:

        raise HTTPException(
            status_code=400,
            detail="Question is required."
        )

    if len(question) > 2000:

        raise HTTPException(
            status_code=400,
            detail="Question must be 2000 characters or less."
        )

    try:

        answer = ask_about_book(
            book,
            question
        )

        return {

            "success": True,

            "book_id": book_id,

            "answer": answer,
        }

    except Exception as e:

        error_text = str(e)

        print(
            f"Book question error: {error_text}"
        )

        if (
            "429" in error_text
            or "RESOURCE_EXHAUSTED" in error_text
            or "quota" in error_text.lower()
        ):

            raise HTTPException(
                status_code=429,
                detail=(
                    "Gemini quota is temporarily "
                    "exceeded. Please wait and try again."
                )
            )

        raise HTTPException(
            status_code=500,
            detail="Could not answer the question."
        )


# ============================================================
# FULL-TEXT EXTRACTION
# ============================================================

@app.post("/api/books/fulltext")
async def get_book_fulltext(
    payload: dict
):

    access_record = payload.get(
        "access",
        {}
    )

    if not isinstance(
        access_record,
        dict
    ):

        return {

            "success": False,

            "error": (
                "Access information is required."
            )
        }

    # --------------------------------------------------------
    # Find a usable URL.
    # Prefer actual PDF/download URL.
    # --------------------------------------------------------

    possible_urls = [

        access_record.get(
            "pdf_url"
        ),

        access_record.get(
            "download_url"
        ),

        access_record.get(
            "read_online_url"
        ),

        access_record.get(
            "archive_url"
        ),
    ]

    usable_url = next(

        (
            url

            for url in possible_urls

            if (
                isinstance(
                    url,
                    str
                )

                and url.strip()
            )
        ),

        None
    )

    if not usable_url:

        return {

            "success": False,

            "error": (
                "The matching book does not have "
                "a usable full-text access URL."
            )
        }

    resolved_access = dict(
        access_record
    )

    # If PDF URL exists, keep it.
    # Otherwise use the first available URL.
    if not resolved_access.get(
        "pdf_url"
    ):

        resolved_access[
            "pdf_url"
        ] = usable_url

    try:

        result = (
            await fetch_book_fulltext_from_access(
                resolved_access
            )
        )

        return result

    except Exception as exc:

        error_text = str(
            exc
        )

        print(
            f"FULLTEXT ERROR: {error_text}"
        )

        # Gemini quota error
        if (
            "429" in error_text
            or "RESOURCE_EXHAUSTED" in error_text
            or "quota" in error_text.lower()
        ):

            return {

                "success": False,

                "error_code": "GEMINI_QUOTA",

                "error": (
                    "Gemini quota is temporarily "
                    "exceeded. Please wait and try again."
                )
            }

        return {

            "success": False,

            "error_code": "FULLTEXT_ERROR",

            "error": (
                "Could not extract book content."
            )
        }


# ============================================================
# FULL-TEXT AI QUESTION
# ============================================================

@app.post("/api/books/fulltext-ask")
async def fulltext_ask(
    payload: dict
):

    question = str(
        payload.get(
            "question",
            ""
        )
    ).strip()

    book = payload.get(
        "book",
        {}
    )

    if not question:

        return {

            "success": False,

            "error_code": "INVALID_REQUEST",

            "error": "Question is required."
        }

    if not isinstance(
        book,
        dict
    ):

        return {

            "success": False,

            "error_code": "INVALID_REQUEST",

            "error": (
                "Book information is required."
            )
        }

    try:

        answer = ask_about_book(
            book=book,
            question=question
        )

        return {

            "success": True,

            "answer": answer
        }

    except Exception as exc:

        error_text = str(
            exc
        )

        # ----------------------------------------------------
        # Gemini quota / rate limit
        # ----------------------------------------------------

        if (
            "429" in error_text
            or "RESOURCE_EXHAUSTED" in error_text
            or "quota" in error_text.lower()
        ):

            return {

                "success": False,

                "error_code": "GEMINI_QUOTA",

                "error": (
                    "Gemini quota is temporarily "
                    "exceeded. Please wait and try again."
                )
            }

        # ----------------------------------------------------
        # Other error
        # ----------------------------------------------------

        print(
            f"FULLTEXT ASK ERROR: {error_text}"
        )

        return {

            "success": False,

            "error_code": "FULLTEXT_ERROR",

            "error": (
                "Unable to answer the question "
                "from the available book content."
            )
        }
