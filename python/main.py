import json
import logging
import re
import unicodedata
from datetime import date

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.exceptions import HTTPException

movies = [
    {
        "id": 1,
        "title": "Inception",
        "director": "Christopher Nolan",
        "year": 2010,
        "genre": "Sci-Fi",
    },
    {
        "id": 2,
        "title": "The Matrix",
        "director": "The Wachowskis",
        "year": 1999,
        "genre": "Sci-Fi",
    },
    {
        "id": 3,
        "title": "Parasite",
        "director": "Bong Joon-ho",
        "year": 2019,
        "genre": "Thriller",
    },
]

app = FastAPI(title="Movie API")
logger = logging.getLogger("uvicorn.error")


# ---------- Helpers for things JavaScript/Express have built in ----------

def to_integer(text):
    """Number(text) + Number.isInteger(): returns an int, or None if not one."""
    text = text.strip()
    if text == "":
        return 0
    if re.fullmatch(r"0[xX][0-9a-fA-F]+|0[bB][01]+|0[oO][0-7]+", text):
        return int(text, 0)
    if not re.fullmatch(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?", text):
        return None
    number = float(text)
    return int(number) if number.is_integer() else None


def parse_number(text):
    """JavaScript has one number type, so 2010.0 in JSON becomes 2010."""
    number = float(text)
    return int(number) if number.is_integer() else number


def reject_constant(text):
    raise ValueError(f"{text} is not valid JSON")


def is_integer(value):
    # bool is a kind of int in Python, so it has to be excluded
    return isinstance(value, int) and not isinstance(value, bool)


def locale_key(text):
    """Approximates localeCompare: ignores case and accents at first."""
    base = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    return base.casefold(), text.swapcase()


def error(status, code, message, **extra):
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, **extra}},
    )


def has(body, field):
    """body.field !== undefined"""
    return isinstance(body, dict) and field in body


# Only for /docs: gives Swagger UI a JSON body box
BODY_DOCS = {
    "requestBody": {
        "content": {
            "application/json": {
                "schema": {"type": "object"},
                "example": {
                    "title": "Interstellar",
                    "director": "Christopher Nolan",
                    "year": 2014,
                    "genre": "Sci-Fi",
                },
            }
        }
    }
}


# express.json()  (morgan's job, request logging, is done by Uvicorn)
@app.middleware("http")
async def parse_json(request: Request, call_next):
    # Express ignores upper/lower case and trailing slashes in routes
    request.scope["path"] = request.scope["path"].lower().rstrip("/") or "/"

    request.state.body = None  # like req.body being undefined
    raw = await request.body()
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    has_body = "content-length" in request.headers or "transfer-encoding" in request.headers
    if has_body and content_type == "application/json":
        # express.json() turns an empty body into {}
        body = json.loads(raw or "{}", parse_float=parse_number, parse_constant=reject_constant)
        if not isinstance(body, (dict, list)):
            raise ValueError("JSON body must be an object or array")
        request.state.body = body
    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
async def root():
    return "Hello from Express"


@app.get("/movies")
async def get_movies(genre: str = "", minYear: str = "", sort: str = ""):
    result = movies.copy()

    if genre:
        result = [m for m in result if m["genre"].lower() == genre.lower()]

    if minYear:
        year = to_integer(minYear)
        if year is None:
            return error(400, "INVALID_QUERY", "minYear must be an integer")
        result = [m for m in result if m["year"] >= year]

    if sort == "year":
        result.sort(key=lambda m: m["year"])
    elif sort == "title":
        result.sort(key=lambda m: locale_key(m["title"]))
    elif sort:
        return error(400, "INVALID_QUERY", "sort must be 'year' or 'title'")

    return result


@app.get("/movies/{id}")
async def get_movie(id: str):
    id = to_integer(id)
    if id is None:
        return error(400, "INVALID_ID", "Id must be an integer")

    movie = next((m for m in movies if m["id"] == id), None)
    if movie is None:
        return error(404, "MOVIE_NOT_FOUND", "Movie not found")
    return movie


@app.post("/movies", status_code=201, openapi_extra=BODY_DOCS)
async def create_movie(request: Request):
    body = request.state.body
    errors = validate_movie(body, False)
    if len(errors) > 0:
        return error(400, "VALIDATION_ERROR", "Movie data is invalid", details=errors)

    new_movie = {
        "id": len(movies) + 1,
        "title": body["title"],
        "director": body["director"],
        "year": body["year"],
        "genre": body["genre"],
    }
    movies.append(new_movie)
    return new_movie


@app.delete("/movies/{id}", status_code=204)
async def delete_movie(id: str):
    id = to_integer(id)
    if id is None:
        return error(400, "INVALID_ID", "Id must be an integer")

    index = next((i for i, m in enumerate(movies) if m["id"] == id), -1)
    if index == -1:
        return error(404, "MOVIE_NOT_FOUND", "Movie not found")

    movies.pop(index)
    return Response(status_code=204)


@app.put("/movies/{id}", openapi_extra=BODY_DOCS)
async def replace_movie(id: str, request: Request):
    id = to_integer(id)
    if id is None:
        return error(400, "INVALID_ID", "Id must be an integer")

    index = next((i for i, m in enumerate(movies) if m["id"] == id), -1)
    if index == -1:
        return error(404, "MOVIE_NOT_FOUND", "Movie not found")

    body = request.state.body
    errors = validate_movie(body, False)
    if len(errors) > 0:
        return error(400, "VALIDATION_ERROR", "Movie data is invalid", details=errors)

    movies[index] = {
        "id": id,
        "title": body["title"],
        "director": body["director"],
        "year": body["year"],
        "genre": body["genre"],
    }
    return movies[index]


@app.patch("/movies/{id}", openapi_extra=BODY_DOCS)
async def update_movie(id: str, request: Request):
    id = to_integer(id)
    if id is None:
        return error(400, "INVALID_ID", "Id must be an integer")

    movie = next((m for m in movies if m["id"] == id), None)
    if movie is None:
        return error(404, "MOVIE_NOT_FOUND", "Movie not found")

    body = request.state.body
    errors = validate_movie(body, True)
    if len(errors) > 0:
        return error(400, "VALIDATION_ERROR", "Movie data is invalid", details=errors)

    if has(body, "title"):
        movie["title"] = body["title"]
    if has(body, "director"):
        movie["director"] = body["director"]
    if has(body, "year"):
        movie["year"] = body["year"]
    if has(body, "genre"):
        movie["genre"] = body["genre"]

    return movie


def validate_movie(body, partial=False):
    if body is None:  # reading undefined.title throws in JavaScript
        raise TypeError("Request body is missing")

    errors = []
    max_year = date.today().year + 5

    if not partial and not has(body, "title"):
        errors.append("title is required")
    if has(body, "title") and (
        not isinstance(body["title"], str) or len(body["title"].strip()) == 0
    ):
        errors.append("title must be a non-empty string")

    if not partial and not has(body, "director"):
        errors.append("director is required")
    if has(body, "director") and (
        not isinstance(body["director"], str) or len(body["director"].strip()) == 0
    ):
        errors.append("director must be a non-empty string")

    if not partial and not has(body, "year"):
        errors.append("year is required")
    if has(body, "year") and (
        not is_integer(body["year"]) or body["year"] < 1888 or body["year"] > max_year
    ):
        errors.append(f"year must be an integer between 1888 and {max_year}")

    if not partial and not has(body, "genre"):
        errors.append("genre is required")
    if has(body, "genre") and (
        not isinstance(body["genre"], str) or len(body["genre"].strip()) == 0
    ):
        errors.append("genre must be a non-empty string")

    return errors


@app.exception_handler(HTTPException)
async def route_not_found(_request: Request, _exc: HTTPException):
    return error(404, "ROUTE_NOT_FOUND", "The requested route does not exist")


@app.exception_handler(Exception)
async def internal_server_error(_request: Request, exc: Exception):
    logger.error("%r", exc)
    return error(500, "INTERNAL_SERVER_ERROR", "An unexpected server error occurred")


if __name__ == "__main__":
    print("http://localhost:3000")
    uvicorn.run(app, port=3000)
