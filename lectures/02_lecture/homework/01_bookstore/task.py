"""
01_bookstore — CRUD API для книжного магазина 📚

Спроектируйте REST API для управления каталогом книг.

Спецификация эндпоинтов (ничего не менять — тесты завязаны на них):

    GET    /books              — список книг (с опциональной фильтрацией)
    GET    /books/{id}         — одна книга по id
    POST   /books              — создать книгу
    PUT    /books/{id}         — полностью обновить книгу
    DELETE /books/{id}         — удалить книгу
    GET    /books/search       — поиск книг по названию или автору

    # Дополнительно — категории
    GET    /categories         — список категорий
    POST   /categories         — создать категорию

Требования к реализации:
    1. Используйте FastAPI + Pydantic
    2. Храните данные в памяти (глобальный список/словарь)
    3. Правильные HTTP-статусы:
        - 200 — успешный GET, PUT
        - 201 — успешный POST
        - 204 — успешный DELETE
        - 404 — ресурс не найден
        - 409 — конфликт (например, дубликат)
        - 422 — невалидные данные (Pydantic сам это делает)
    4. Валидация полей через Pydantic Field:
        - title:  не пустой, до 100 символов
        - author: не пустой, до 100 символов
        - year:   ≥ 0, до 2025
        - isbn:   строка 10 или 13 цифр (978-5-xxx...)
        - price:  > 0
        - category_id: опционально, ссылка на категорию
    5. Кастомная обработка ошибок:
        - BookNotFoundException → 404 c {"detail": "Book not found", "code": "NOT_FOUND"}
        - DuplicateIsbnException → 409 c {"detail": "...", "code": "DUPLICATE_ISBN"}
    6. Поиск /books/search?query=... — ищет по title и author (case-insensitive)
    7. Фильтрация GET /books?category_id=N&year=2024
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional

# ═══════════════════════════════════════════════════════════
# МОДЕЛИ
# ═══════════════════════════════════════════════════════════


class Category(BaseModel):
    """Доменная модель категории. Возвращается в ответах."""

    id: int
    name: str = Field(min_length=1, max_length=50)


class CategoryCreate(BaseModel):
    """Модель для создания категории (без id, лишние поля запрещены)."""

    name: str = Field(min_length=1, max_length=50)

    model_config = {"extra": "forbid"}


class Book(BaseModel):
    """Доменная модель книги. Возвращается в ответах GET/PUT."""

    id: int
    title: str = Field(min_length=1, max_length=100)
    author: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=0, le=2025)
    isbn: str
    price: float = Field(gt=0)
    category_id: Optional[int] = None

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, v: str) -> str:
        digits = v.replace("-", "")
        if not digits.isdigit() or len(digits) not in (10, 13):
            raise ValueError("ISBN must be 10 or 13 digits")
        return v


class BookCreate(BaseModel):
    """Модель для создания/обновления книги (без id — сервер сгенерирует)."""

    title: str = Field(min_length=1, max_length=100)
    author: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=0, le=2025)
    isbn: str
    price: float = Field(gt=0)
    category_id: Optional[int] = None

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, v: str) -> str:
        digits = v.replace("-", "")
        if not digits.isdigit() or len(digits) not in (10, 13):
            raise ValueError("ISBN must be 10 or 13 digits")
        return v


# ═══════════════════════════════════════════════════════════
# ИСКЛЮЧЕНИЯ
# ═══════════════════════════════════════════════════════════


class BookNotFoundException(HTTPException):
    """404 — книга не найдена."""
    def __init__(self):
        super().__init__(status_code=404, detail="Book not found")


class DuplicateIsbnException(HTTPException):
    """409 — ISBN уже существует."""
    def __init__(self):
        super().__init__(status_code=409, detail="ISBN already exists")


# ═══════════════════════════════════════════════════════════
# ПРИЛОЖЕНИЕ
# ═══════════════════════════════════════════════════════════

app = FastAPI(title="Bookstore API")

# Хранилище
BOOKS: list[dict] = []
CATEGORIES: list[dict] = []
BOOK_ID_COUNTER = 1
CATEGORY_ID_COUNTER = 1


@app.exception_handler(BookNotFoundException)
def book_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Book not found", "code": "NOT_FOUND"}
    )


@app.exception_handler(DuplicateIsbnException)
def duplicate_isbn_handler(request, exc):
    return JSONResponse(
        status_code=409,
        content={"detail": "ISBN already exists", "code": "DUPLICATE_ISBN"}
    )


# ═══════════════════════════════════════════════════════════
# КАТЕГОРИИ
# ═══════════════════════════════════════════════════════════


@app.get("/categories")
def list_categories():
    """GET /categories — список всех категорий."""
    return CATEGORIES


@app.post("/categories", status_code=201)
def create_category(category: CategoryCreate):
    """POST /categories — создать категорию."""
    global CATEGORY_ID_COUNTER
    new_cat = {
        "id": CATEGORY_ID_COUNTER,
        "name": category.name
    }
    CATEGORY_ID_COUNTER += 1
    CATEGORIES.append(new_cat)
    return new_cat


# ═══════════════════════════════════════════════════════════
# CRUID КНИГ
# ═══════════════════════════════════════════════════════════


@app.get("/books")
def list_books(category_id: Optional[int] = None, year: Optional[int] = None):
    """GET /books — список книг. Опциональная фильтрация по category_id и year."""
    results = BOOKS
    if category_id is not None:
        results = [b for b in results if b.get("category_id") == category_id]
    if year is not None:
        results = [b for b in results if b.get("year") == year]
    return results


@app.get("/books/search")
def search_books(query: str):
    """GET /books/search?query=... — поиск по title и author (case-insensitive)."""
    query_lower = query.lower()
    return [
        b for b in BOOKS
        if query_lower in b["title"].lower() or query_lower in b["author"].lower()
    ]


@app.get("/books/{book_id}")
def get_book(book_id: int):
    """GET /books/{id} — одна книга."""
    for b in BOOKS:
        if b["id"] == book_id:
            return b
    raise BookNotFoundException()


@app.post("/books", status_code=201)
def create_book(book: BookCreate):
    """POST /books — создать книгу.

    Проверять уникальность ISBN. Если дубликат — DuplicateIsbnException.
    """
    for b in BOOKS:
        if b["isbn"] == book.isbn:
            raise DuplicateIsbnException()

    global BOOK_ID_COUNTER
    new_book = {
        "id": BOOK_ID_COUNTER,
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": book.isbn,
        "price": book.price,
        "category_id": book.category_id
    }
    BOOK_ID_COUNTER += 1
    BOOKS.append(new_book)
    return new_book


@app.put("/books/{book_id}")
def update_book(book_id: int, book: BookCreate):
    """PUT /books/{id} — полностью обновить книгу."""
    book_index = -1
    for i, b in enumerate(BOOKS):
        if b["id"] == book_id:
            book_index = i
            break
    if book_index == -1:
        raise BookNotFoundException()

    for i, b in enumerate(BOOKS):
        if i != book_index and b["isbn"] == book.isbn:
            raise DuplicateIsbnException()

    updated_book = {
        "id": book_id,
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": book.isbn,
        "price": book.price,
        "category_id": book.category_id
    }
    BOOKS[book_index] = updated_book
    return updated_book


@app.delete("/books/{book_id}", status_code=204)
def delete_book(book_id: int):
    """DELETE /books/{id} — удалить книгу."""
    for i, b in enumerate(BOOKS):
        if b["id"] == book_id:
            BOOKS.pop(i)
            return
    raise BookNotFoundException()
