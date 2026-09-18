import httpx
from typing import Any
from urllib.parse import quote


INTERNET_ARCHIVE_SEARCH_URL = (
    "https://archive.org/advancedsearch.php"
)

INTERNET_ARCHIVE_METADATA_URL = (
    "https://archive.org/metadata"
)


# ============================================================
# COMMON ACCESS RECORD
# ============================================================

def create_access_record(
    source: str,
    title: str,
    url: str = "",
    access_type: str = "Unknown",
    status: str = "Unknown",
    description: str = "",
    archive_url: str = "",
    read_online_url: str = "",
    pdf_url: str = "",
    download_url: str = "",
):
    return {
        "source": source,
        "title": title,
        "url": url,
        "access_type": access_type,
        "status": status,
        "description": description,

        # Actual usable links
        "archive_url": archive_url,
        "read_online_url": read_online_url,
        "pdf_url": pdf_url,
        "download_url": download_url,
    }


# ============================================================
# SAFE VALUE HELPERS
# ============================================================

def _first_value(value: Any) -> str:

    if isinstance(value, list):

        if not value:
            return ""

        return str(value[0]).strip()

    if value is None:
        return ""

    return str(value).strip()


def _list_value(value: Any) -> list[str]:

    if value is None:
        return []

    if isinstance(value, list):

        return [
            str(x).strip()
            for x in value
            if str(x).strip()
        ]

    value = str(value).strip()

    return [value] if value else []


# ============================================================
# INTERNET ARCHIVE URL HELPERS
# ============================================================

def _archive_details_url(identifier: str) -> str:

    return (
        "https://archive.org/details/"
        f"{quote(identifier, safe='')}"
    )


def _archive_download_url(
    identifier: str,
    filename: str,
) -> str:

    return (
        "https://archive.org/download/"
        f"{quote(identifier, safe='')}/"
        f"{quote(filename, safe='')}"
    )


# ============================================================
# FILE ACCESS HELPERS
# ============================================================

def _is_restricted_file(file_info: dict[str, Any]) -> bool:

    """
    Conservative check.

    We do NOT expose a direct download URL if IA marks
    the file as private/restricted.
    """

    if not isinstance(file_info, dict):
        return True

    private_value = str(
        file_info.get("private", "")
        or ""
    ).lower()

    if private_value in {
        "1",
        "true",
        "yes",
    }:
        return True

    # Some restricted files contain access-related metadata.
    name = str(
        file_info.get("name", "")
        or ""
    ).lower()

    if name.endswith(".zip") and (
        "lending" in name
        or "restricted" in name
    ):
        return True

    return False


def _is_pdf_file(file_info: dict[str, Any]) -> bool:

    if not isinstance(file_info, dict):
        return False

    name = str(
        file_info.get("name", "")
        or ""
    ).lower()

    format_value = str(
        file_info.get("format", "")
        or ""
    ).lower()

    # Actual PDF filename
    if name.endswith(".pdf"):
        return True

    # IA metadata formats
    pdf_formats = {
        "pdf",
        "text pdf",
        "item image pdf",
        "image pdf",
        "pdf with text",
    }

    return format_value in pdf_formats


def _find_pdf_file(
    files: list[dict[str, Any]]
) -> dict[str, Any] | None:

    """
    Find the best actual PDF file exposed by IA.

    Restricted/private files are ignored.
    """

    candidates = []

    for file_info in files:

        if not isinstance(file_info, dict):
            continue

        if _is_restricted_file(file_info):
            continue

        if not _is_pdf_file(file_info):
            continue

        candidates.append(file_info)

    if not candidates:
        return None

    # Prefer files whose format explicitly says Text PDF.
    for file_info in candidates:

        format_value = str(
            file_info.get("format", "")
            or ""
        ).lower()

        if format_value == "text pdf":
            return file_info

    # Then prefer normal PDF.
    for file_info in candidates:

        format_value = str(
            file_info.get("format", "")
            or ""
        ).lower()

        if format_value == "pdf":
            return file_info

    return candidates[0]


def _find_downloadable_file(
    files: list[dict[str, Any]]
) -> dict[str, Any] | None:

    """
    Find a useful non-restricted downloadable file.

    PDF is preferred.
    """

    pdf_file = _find_pdf_file(files)

    if pdf_file:
        return pdf_file

    preferred_formats = {
        "djvu",
        "djvu txt",
        "text",
        "epub",
        "plain text",
    }

    for file_info in files:

        if not isinstance(file_info, dict):
            continue

        if _is_restricted_file(file_info):
            continue

        name = str(
            file_info.get("name", "")
            or ""
        ).lower()

        format_value = str(
            file_info.get("format", "")
            or ""
        ).lower()

        if (
            format_value in preferred_formats
            or name.endswith(".epub")
            or name.endswith(".txt")
            or name.endswith(".djvu")
        ):
            return file_info

    return None


# ============================================================
# ACCESS STATUS
# ============================================================

def determine_access_status(
    doc: dict[str, Any]
):
    """
    Determine conservative access status.

    An Internet Archive record does NOT automatically mean
    that the book is freely downloadable.
    """

    collection = _list_value(
        doc.get("collection", [])
    )

    mediatype = str(
        doc.get("mediatype", "")
        or ""
    ).lower()

    collection_text = " ".join(
        collection
    ).lower()

    # --------------------------------------------------------
    # Lending / controlled access
    # --------------------------------------------------------

    if (
        "lending" in collection_text
        or "inlibrary" in collection_text
        or "printdisabled" in collection_text
        or "borrow" in collection_text
    ):

        return (
            "Borrow",
            "Available",
            (
                "Internet Archive has a lending or "
                "controlled-access record. Availability "
                "depends on the item's access controls."
            )
        )

    # --------------------------------------------------------
    # Text item
    # --------------------------------------------------------

    if mediatype == "texts":

        return (
            "Read Online",
            "Available",
            (
                "Internet Archive text record found. "
                "Reading or downloading availability "
                "depends on the item's rights and "
                "access controls."
            )
        )

    # --------------------------------------------------------
    # Other media
    # --------------------------------------------------------

    if mediatype:

        return (
            "Record Only",
            "Available",
            (
                "Internet Archive record found, but it "
                "is not identified as a text item."
            )
        )

    # --------------------------------------------------------
    # Unknown
    # --------------------------------------------------------

    return (
        "Record Only",
        "Available",
        (
            "Internet Archive record found. "
            "Actual reading or borrowing availability "
            "depends on the item."
        )
    )


# ============================================================
# BUILD IA CANDIDATE
# ============================================================

def _build_candidate(
    doc: dict[str, Any],
    fallback_title: str = "",
):

    identifier = doc.get(
        "identifier"
    )

    if not identifier:
        return None

    title = (
        doc.get("title")
        or fallback_title
        or ""
    )

    creator = _first_value(
        doc.get("creator", "")
    )

    subject = _first_value(
        doc.get("subject", "")
    )

    isbn_values = _list_value(
        doc.get("isbn", [])
    )

    isbn = (
        isbn_values[0]
        if isbn_values
        else ""
    )

    archive_url = _archive_details_url(
        identifier
    )

    return {

        "source": "Internet Archive",

        "key": identifier,

        "identifier": identifier,

        "title": title,

        "author": creator,

        "first_publish_year": (
            doc.get("date")
        ),

        "publisher": "",

        "subject": subject,

        "language": _first_value(
            doc.get("language", "")
        ),

        "description": (
            doc.get("description", "")
        ),

        "isbn": isbn,

        "isbn_list": isbn_values,

        "cover_url": None,

        "archive_url": archive_url,

        # Keep the original IA metadata.
        "archive_metadata": doc,

        "access_type": "Archive Record",

        "access_status": "Discovered",

        "access_description": (
            "Internet Archive record discovered "
            "during book identification."
        ),
    }


# ============================================================
# IA QUERY BUILDER
# ============================================================

def _generate_archive_queries(
    title: str,
    author: str = "",
    search_variants: list[str] | None = None,
):

    queries = []
    seen = set()

    def add(query: str):

        query = str(
            query or ""
        ).strip()

        if not query:
            return

        if query in seen:
            return

        seen.add(query)

        queries.append(query)

    # --------------------------------------------------------
    # Main title
    # --------------------------------------------------------

    if title:

        add(
            f'title:("{title}")'
        )

        add(
            f'title:({title})'
        )

    # --------------------------------------------------------
    # Gemini variants
    # --------------------------------------------------------

    for variant in (
        search_variants or []
    ):

        variant = str(
            variant or ""
        ).strip()

        if not variant:
            continue

        add(
            f'title:("{variant}")'
        )

        add(
            f'title:({variant})'
        )

    # --------------------------------------------------------
    # Title + author
    # --------------------------------------------------------

    if title and author:

        add(
            f'title:("{title}") '
            f'AND creator:("{author}")'
        )

    # --------------------------------------------------------
    # Important title phrase fallback
    # --------------------------------------------------------

    title_words = [
        x.strip()
        for x in str(
            title or ""
        ).replace(
            "-",
            " "
        ).split()
        if len(x.strip()) >= 4
    ]

    if len(title_words) >= 2:

        phrase = " ".join(
            title_words[:2]
        )

        add(
            f'title:("{phrase}")'
        )

    # --------------------------------------------------------
    # Special transliteration handling
    # --------------------------------------------------------

    title_lower = str(
        title or ""
    ).lower()

    variant_text = " ".join(
        str(x).lower()
        for x in (
            search_variants or []
        )
    )

    combined = (
        title_lower
        + " "
        + variant_text
    )

    if (
        "sundarkand" in combined
        or "sundar kand" in combined
        or "sunderkand" in combined
        or "sunder kand" in combined
        or "sundara kanda" in combined
    ):

        for term in [
            "Sundarkand",
            "Sunderkand",
            "Sundar Kand",
            "Sunder Kand",
            "Sundar Kanda",
        ]:

            add(
                f'title:("{term}")'
            )

            add(
                f'title:({term})'
            )

    return queries[:30]


# ============================================================
# INTERNET ARCHIVE CANDIDATE DISCOVERY
# ============================================================

async def search_internet_archive_candidates(
    title: str,
    author: str = "",
    search_variants: list[str] | None = None,
    limit: int = 20,
):

    if (
        not title
        and not search_variants
    ):
        return []

    queries = _generate_archive_queries(
        title=title,
        author=author,
        search_variants=search_variants,
    )

    all_candidates = []

    seen_identifiers = set()

    params_fields = [
        "identifier",
        "title",
        "creator",
        "date",
        "description",
        "collection",
        "mediatype",
        "language",
        "subject",
        "isbn",
    ]

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:

        for query in queries:

            params = {
                "q": query,
                "fl[]": params_fields,
                "rows": limit,
                "page": 1,
                "output": "json",
            }

            try:

                response = await client.get(
                    INTERNET_ARCHIVE_SEARCH_URL,
                    params=params,
                )

                response.raise_for_status()

                data = response.json()

            except Exception as exc:

                print(
                    "Internet Archive candidate "
                    f"search failed for '{query}': "
                    f"{exc}"
                )

                continue

            response_data = data.get(
                "response",
                {}
            )

            docs = response_data.get(
                "docs",
                []
            )

            total = response_data.get(
                "numFound",
                0
            )

            print(
                "Internet Archive query "
                f"'{query}': "
                f"{len(docs)} returned / "
                f"{total} total"
            )

            for doc in docs:

                identifier = doc.get(
                    "identifier"
                )

                if not identifier:
                    continue

                if identifier in seen_identifiers:
                    continue

                seen_identifiers.add(
                    identifier
                )

                candidate = _build_candidate(
                    doc,
                    fallback_title=title,
                )

                if candidate:

                    all_candidates.append(
                        candidate
                    )

    print(
        "Internet Archive candidate "
        "discovery total: "
        f"{len(all_candidates)}"
    )

    return all_candidates


# ============================================================
# DIRECT IA RECORD METADATA
# ============================================================

async def get_internet_archive_record(
    identifier: str,
):

    if not identifier:
        return None

    url = (
        f"{INTERNET_ARCHIVE_METADATA_URL}/"
        f"{identifier}"
    )

    try:

        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:

            response = await client.get(
                url
            )

            response.raise_for_status()

            data = response.json()

            return data

    except Exception as exc:

        print(
            "Internet Archive metadata lookup "
            f"failed for '{identifier}': "
            f"{exc}"
        )

        return None


# ============================================================
# BUILD ACTUAL FILE LINKS
# ============================================================

def _build_file_links(
    identifier: str,
    metadata: dict[str, Any],
):
    """
    Inspect the exact IA metadata and generate only
    links that correspond to actual exposed files.

    No PDF URL is invented.
    """

    archive_url = _archive_details_url(
        identifier
    )

    # IA BookReader / item page.
    read_online_url = archive_url

    pdf_url = ""

    download_url = ""

    files = metadata.get(
        "files",
        []
    )

    if not isinstance(files, list):
        files = []

    # --------------------------------------------------------
    # Actual PDF
    # --------------------------------------------------------

    pdf_file = _find_pdf_file(
        files
    )

    if pdf_file:

        filename = str(
            pdf_file.get("name", "")
            or ""
        ).strip()

        if filename:

            pdf_url = _archive_download_url(
                identifier,
                filename,
            )

    # --------------------------------------------------------
    # Actual downloadable file
    # --------------------------------------------------------

    downloadable_file = _find_downloadable_file(
        files
    )

    if downloadable_file:

        filename = str(
            downloadable_file.get("name", "")
            or ""
        ).strip()

        if filename:

            download_url = _archive_download_url(
                identifier,
                filename,
            )

    return {
        "archive_url": archive_url,
        "read_online_url": read_online_url,
        "pdf_url": pdf_url,
        "download_url": download_url,
    }


# ============================================================
# BUILD ACCESS FROM EXISTING IA CANDIDATE
# ============================================================

async def build_access_records(
    candidate
):

    if not candidate:
        return []

    # --------------------------------------------------------
    # Only IA candidates should be processed here.
    # --------------------------------------------------------

    source = str(
        candidate.get(
            "source",
            ""
        )
        or ""
    ).lower()

    if (
        source != "internet archive"
        and not candidate.get(
            "identifier"
        )
    ):
        return []

    identifier = candidate.get(
        "identifier"
    )

    # Some merged records may store it as "key".
    if not identifier:

        identifier = candidate.get(
            "key"
        )

    # Some merged records may retain archive_url only.
    if not identifier:

        archive_url = candidate.get(
            "archive_url",
            ""
        )

        if (
            archive_url
            and "/details/" in archive_url
        ):

            identifier = (
                archive_url
                .split(
                    "/details/",
                    1
                )[1]
                .split(
                    "?",
                    1
                )[0]
                .strip("/")
            )

    if not identifier:
        return []

    # --------------------------------------------------------
    # Direct metadata lookup.
    # --------------------------------------------------------

    metadata_response = (
        await get_internet_archive_record(
            identifier
        )
    )

    # --------------------------------------------------------
    # Metadata unavailable.
    # --------------------------------------------------------

    if metadata_response is None:

        title = candidate.get(
            "title",
            ""
        )

        archive_url = _archive_details_url(
            identifier
        )

        return [
            create_access_record(

                source="Internet Archive",

                title=title,

                url=archive_url,

                access_type="Archive Record",

                status="Record Found",

                description=(
                    "Internet Archive record was "
                    "discovered. Detailed file metadata "
                    "could not be retrieved."
                ),

                archive_url=archive_url,

                read_online_url=archive_url,

            )
        ]

    # --------------------------------------------------------
    # IA metadata response.
    # --------------------------------------------------------

    ia_metadata = metadata_response.get(
        "metadata",
        {}
    )

    if not isinstance(
        ia_metadata,
        dict
    ):
        ia_metadata = {}

    # --------------------------------------------------------
    # Combine metadata for access detection.
    # --------------------------------------------------------

    combined_doc = dict(
        ia_metadata
    )

    for key in [
        "collection",
        "mediatype",
    ]:

        if not combined_doc.get(key):

            combined_doc[key] = metadata_response.get(
                key,
                ""
            )

    (
        access_type,
        status,
        description
    ) = determine_access_status(
        combined_doc
    )

    title = (
        ia_metadata.get(
            "title"
        )
        or candidate.get(
            "title",
            ""
        )
    )

    archive_url = _archive_details_url(
        identifier
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Inspect actual files exposed by IA.
    # --------------------------------------------------------

    file_links = _build_file_links(
        identifier=identifier,
        metadata=metadata_response,
    )

    read_online_url = file_links[
        "read_online_url"
    ]

    pdf_url = file_links[
        "pdf_url"
    ]

    download_url = file_links[
        "download_url"
    ]

    # --------------------------------------------------------
    # Improve description.
    # --------------------------------------------------------

    if pdf_url:

        description += (
            " A PDF file is exposed by the "
            "Internet Archive metadata."
        )

    elif download_url:

        description += (
            " A downloadable file is exposed "
            "by the Internet Archive metadata."
        )

    else:

        description += (
            " No unrestricted PDF/download file "
            "was exposed by the retrieved metadata."
        )

    # --------------------------------------------------------
    # If lending/controlled access, do not advertise
    # direct PDF/download links.
    # --------------------------------------------------------

    if access_type == "Borrow":

        pdf_url = ""
        download_url = ""

        description += (
            " The item appears to use controlled "
            "or lending access, so direct file "
            "downloads are not exposed."
        )

    return [
        create_access_record(

            source="Internet Archive",

            title=title,

            url=archive_url,

            access_type=access_type,

            status=status,

            description=description,

            archive_url=archive_url,

            read_online_url=read_online_url,

            pdf_url=pdf_url,

            download_url=download_url,
        )
    ]


# ============================================================
# LEGACY SEARCH FUNCTION
# ============================================================

async def search_internet_archive(
    title: str,
    author: str = "",
):

    if not title:
        return []

    query = (
        f'title:("{title}")'
    )

    params = {

        "q": query,

        "fl[]": [
            "identifier",
            "title",
            "creator",
            "date",
            "description",
            "collection",
            "mediatype",
            "language",
            "subject",
            "isbn",
        ],

        "rows": 20,

        "page": 1,

        "output": "json",
    }

    try:

        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:

            response = await client.get(
                INTERNET_ARCHIVE_SEARCH_URL,
                params=params,
            )

            response.raise_for_status()

            data = response.json()

    except Exception as exc:

        print(
            "Internet Archive search failed: "
            f"{exc}"
        )

        return []

    docs = (
        data
        .get("response", {})
        .get("docs", [])
    )

    records = []

    seen = set()

    for doc in docs:

        identifier = doc.get(
            "identifier"
        )

        if not identifier:
            continue

        if identifier in seen:
            continue

        seen.add(
            identifier
        )

        (
            access_type,
            status,
            description
        ) = determine_access_status(
            doc
        )

        title_value = (
            doc.get("title")
            or title
        )

        records.append(
            create_access_record(

                source="Internet Archive",

                title=title_value,

                url=_archive_details_url(
                    identifier
                ),

                access_type=access_type,

                status=status,

                description=description,

                archive_url=_archive_details_url(
                    identifier
                ),

                read_online_url=_archive_details_url(
                    identifier
                ),
            )
        )

    return records