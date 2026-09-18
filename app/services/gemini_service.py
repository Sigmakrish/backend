import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from app.schemas.book import BookIdentification

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not configured")

client = genai.Client(api_key=api_key)


def ask_gemini(prompt: str) -> str:
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
    )

    return response.text


def identify_book(image_bytes: bytes, mime_type: str):
    prompt = """
Identify the book shown in this image.

IMPORTANT:

1. Identify the WORK first:
   - title
   - author

2. Do NOT guess the physical edition.
   - Do not guess publisher from binding style.
   - Do not guess publication year unless visible or strongly supported.
   - If publisher is unknown, return an empty string.
   - If year is unknown, return null.

3. The title and author may be written in ANY language or script.

4. Preserve the original/native title and author exactly when possible.

5. Create search_variants containing useful alternative ways
   to search for the same book across international catalogs.

6. Identify the language of the book.

Return:
- language: the full human-readable language name, such as
  Hindi, Bengali, English, Sanskrit, Tamil, Telugu, Marathi,
  Gujarati, Punjabi, Urdu, Arabic, Persian, Russian, Greek,
  Japanese, Chinese, Korean, etc.
- language_code: the ISO 639-1 language code when known,
  such as hi, bn, en, sa, ta, te, mr, gu, pa, ur, ar, fa,
  ru, el, ja, zh, ko.

Do not put the ISO code alone in the language field.

Search variants may include:
- original title
- original title + author
- Romanized/transliterated title
- Romanized/transliterated author
- English title if the work has a commonly known English title
- simplified title
- common catalog spelling

For example:

Hindi:
श्रीरामचरितमानस
गोस्वामी तुलसीदास

Possible variants:
- श्रीरामचरितमानस गोस्वामी तुलसीदास
- Shri Ramcharitmanas Goswami Tulsidas
- Ramcharitmanas Tulsidas
- Shri Ramcharitmanas
- Tulsidas Ramcharitmanas

For Japanese, Chinese, Korean, Arabic, Russian,
Bengali, Tamil, Telugu and other languages, provide
appropriate Romanized or commonly searchable forms
when possible.

DO NOT invent alternative titles.

The confidence value refers primarily to confidence
in the WORK identification, not the physical edition.

Return only the requested structured information.
"""
    
    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type,
    )

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=[prompt, image_part],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BookIdentification,
        ),
    )

    return response.parsed

def identify_book_from_text(text: str):
    prompt = f"""
Identify the book described by the following user text.

USER TEXT:
{text}

IMPORTANT:

1. Identify the WORK first:
   - title
   - author

2. Do NOT guess the physical edition.
   - Do not guess publisher unless explicitly stated.
   - Do not guess publication year unless explicitly stated.
   - If publisher is unknown, return an empty string.
   - If year is unknown, return null.

3. The book may be written in ANY language or script.

4. Preserve the original/native title and author when possible.

5. Identify the language of the book.

6. Create useful search_variants for international book catalogs.

Search variants may include:
- original title
- original title + author
- Romanized/transliterated title
- Romanized/transliterated author
- commonly known English title
- simplified title
- common catalog spelling

DO NOT invent alternative titles.

The confidence value refers primarily to confidence
in the WORK identification, not the physical edition.

Return:
- language: full human-readable language name
- language_code: ISO 639-1 code when known
- title
- author
- publication_year
- publisher
- isbn
- subject
- search_variants
- confidence

Return only the requested structured information.
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BookIdentification,
        ),
    )

    return response.parsed

def generate_book_summary(book: dict) -> str:
    prompt = f"""
Create a useful study-oriented summary for this book.

BOOK INFORMATION:
Title: {book.get("title", "")}
Author: {book.get("author", "")}
Subject: {book.get("subject", "")}
Language: {book.get("language", "")}
Publication Year: {book.get("publication_year", book.get("first_publish_year", ""))}

IMPORTANT:
- Use only the information provided above.
- Do not invent chapters, quotations, page numbers, or historical facts.
- If information is insufficient, clearly say so.
- Keep the summary concise but useful for studying.
- Explain the book's likely central theme or subject when supported.
- Do not reproduce copyrighted text.

Return a structured study summary containing:
1. Overview
2. Main themes
3. Key ideas
4. Historical/contextual significance if supported
5. Who may find the book useful

Return only the study summary.
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
    )

    return response.text

def ask_about_book(book: dict, question: str) -> str:
    book_text = str(
        book.get("fulltext", "") or ""
    ).strip()

    if not book_text:
        return (
            "I could not find readable content from the "
            "available pages of this book."
        )

    # --------------------------------------------------------
    # Limit context sent to Gemini
    # --------------------------------------------------------
    # OCR may contain many pages of text. Sending everything
    # back to Gemini wastes input-token quota.
    MAX_CONTEXT_CHARS = 18000

    if len(book_text) > MAX_CONTEXT_CHARS:
        book_text = book_text[:MAX_CONTEXT_CHARS]

        context_note = (
            "\n\n[Only the first portion of the extracted "
            "book content is provided to the AI.]"
        )
    else:
        context_note = ""

    prompt = f"""
You are the study assistant for RareBook AI.

Answer the user's question using the extracted content
from the identified book.

BOOK INFORMATION:
Title: {book.get("title", "")}
Author: {book.get("author", "")}
Subject: {book.get("subject", "")}
Language: {book.get("language", "")}
Publication Year:
{book.get("publication_year", book.get("first_publish_year", ""))}

EXTRACTED BOOK CONTENT:
{book_text}
{context_note}

USER QUESTION:
{question}

RULES:
- Use the extracted book content as the primary source.
- Do not invent facts that are not supported by the content.
- If the available content is insufficient, say so clearly.
- Answer directly and concisely.
- Preserve the book's original language when appropriate.
- Do not reproduce long passages from the book.
- A short quotation may be used when necessary.
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
    )

    return response.text