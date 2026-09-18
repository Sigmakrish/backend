from pydantic import BaseModel


class BookIdentification(BaseModel):
    title: str
    author: str
    publication_year: int | None = None
    publisher: str = ""
    language: str = ""
    language_code: str = ""
    subject: str = ""
    edition_clues: str = ""
    confidence: int
    reasoning: str
    search_variants: list[str] = []