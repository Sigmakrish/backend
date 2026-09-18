import asyncio
import httpx
from typing import Any


GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"


async def search_google_books(
    title: str,
    author: str = "",
    limit: int = 20
) -> list[dict[str, Any]]:

    # Build search query
    if title and author:
        query = f'intitle:"{title}" inauthor:"{author}"'
    elif title:
        query = f'intitle:"{title}"'
    elif author:
        query = f'inauthor:"{author}"'
    else:
        return []

    params = {
        "q": query,
        "maxResults": min(limit, 40),
        "printType": "books",
    }

    for attempt in range(3):

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    GOOGLE_BOOKS_URL,
                    params=params
                )

            # Rate limited
            if response.status_code == 429:

                if attempt < 2:
                    wait_time = 2 ** attempt
                    print(
                        f"Google Books rate limited. "
                        f"Retrying in {wait_time} seconds..."
                    )

                    await asyncio.sleep(wait_time)
                    continue

                print(
                    "Google Books rate limit reached. "
                    "Continuing without Google Books results."
                )

                return []

            response.raise_for_status()

            data = response.json()

            candidates = []

            for item in data.get("items", []):

                volume = item.get("volumeInfo", {})

                identifiers = volume.get(
                    "industryIdentifiers",
                    []
                )
                
                isbn13 = ""
                isbn10 = ""

                for identifier in identifiers:

                    identifier_type = identifier.get("type")
                    identifier_value = identifier.get(
                        "identifier",
                        ""
                    )

                    if identifier_type == "ISBN_13":
                        isbn13 = identifier_value

                    elif identifier_type == "ISBN_10":
                        isbn10 = identifier_value

                published_date = volume.get(
                    "publishedDate",
                    ""
                )

                year = None

                if (
                    published_date
                    and len(published_date) >= 4
                    and published_date[:4].isdigit()
                ):
                    year = int(published_date[:4])

                candidates.append({
                    "source": "Google Books",
                    "key": item.get("id"),
                    "title": volume.get("title", ""),
                    "author": (
                        volume.get("authors", [""])[0]
                        if volume.get("authors")
                        else ""
                    ),
                    "first_publish_year": year,
                    "publisher": volume.get(
                        "publisher",
                        ""
                    ),
                    "subject": (
                        volume.get("categories", [""])[0]
                        if volume.get("categories")
                        else ""
                    ),
                    "cover_i": None,
                    "cover_url": (
                        volume.get("imageLinks", {})
                        .get("large")
                        or volume.get("imageLinks", {})
                        .get("medium")
                        or volume.get("imageLinks", {})
                        .get("thumbnail")
                    ),
                    "isbn": isbn13 or isbn10,
                    "isbn_list": [
                        isbn
                        for isbn in [isbn10, isbn13]
                        if isbn
                    ],
                    "isbn10": isbn10,
                    "isbn13": isbn13,
                    "description": volume.get(
                        "description",
                        ""
                    ),
                })

            return candidates

        except httpx.HTTPError as error:

            if attempt < 2:
                wait_time = 2 ** attempt

                print(
                    f"Google Books request failed. "
                    f"Retrying in {wait_time} seconds..."
                )

                await asyncio.sleep(wait_time)

            else:
                print(
                    f"Google Books search failed: {error}"
                )

    return []