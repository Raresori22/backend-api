import logging
from datetime import date
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import AfterValidator, BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("uvicorn.error")


# ---------- Pydantic models (replace validateMovie) ----------

def check_year(value: int) -> int:
    max_year = date.today().year + 5
    if not 1888 <= value <= max_year:
        raise ValueError(f"year must be an integer between 1888 and {max_year}")
    return value


# Reusable field types. The pattern \S means "contains a non-whitespace character".
NonEmptyStr = Annotated[str, Field(pattern=r"\S")]
# strict=True rejects "2010" (a string), just like Number.isInteger does in JS.
Year = Annotated[int, Field(strict=True), AfterValidator(check_year)]


class MovieCreate(BaseModel):
    """Body of POST and PUT: every field is required."""

    title: NonEmptyStr = Field(examples=["Interstellar"])
    director: NonEmptyStr = Field(examples=["Christopher Nolan"])
    year: Year = Field(examples=[2014])
    genre: NonEmptyStr = Field(examples=["Sci-Fi"])


class MovieUpdate(BaseModel):
    """Body of PATCH: fields may be left out, but may not be null."""

    title: NonEmptyStr = Field(default=None, examples=["Interstellar"])
    director: NonEmptyStr = Field(default=None, examples=["Christopher Nolan"])
    year: Year = Field(default=None, examples=[2014])
    genre: NonEmptyStr = Field(default=None, examples=["Sci-Fi"])


class Movie(MovieCreate):
    """A stored movie: everything in MovieCreate, plus the id."""

    id: int


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: list[str] | None = None


class ErrorResponse(BaseModel):
    error: ErrorInfo


# ---------- App and data ----------

# Documents our error format in Swagger instead of FastAPI's default 422.
app = FastAPI(title="Movie API", responses={"4XX": {"model": ErrorResponse}})

movies: list[Movie] = [
    Movie(id=1, title="Inception", director="Christopher Nolan", year=2010, genre="Sci-Fi"),
    Movie(id=2, title="The Matrix", director="The Wachowskis", year=1999, genre="Sci-Fi"),
    Movie(id=3, title="Parasite", director="Bong Joon-ho", year=2019, genre="Thriller"),
]
next_id = 4  # only ever goes up, so ids are never reused after a delete


def find_index(movie_id: int) -> int:
    for index, movie in enumerate(movies):
        if movie.id == movie_id:
            return index
    raise HTTPException(
        status_code=404,
        detail={"code": "MOVIE_NOT_FOUND", "message": "Movie not found"},
    )


# ---------- Routes ----------

@app.get("/", response_class=PlainTextResponse)
async def root():
    return "Hello from FastAPI"


@app.get("/movies")
async def list_movies(
    genre: str | None = None,
    min_year: Annotated[int | None, Query(alias="minYear")] = None,
    sort: Literal["year", "title"] | None = None,
) -> list[Movie]:
    result = list(movies)
    if genre:
        result = [m for m in result if m.genre.lower() == genre.lower()]
    if min_year is not None:
        result = [m for m in result if m.year >= min_year]
    if sort == "year":
        result.sort(key=lambda m: m.year)
    elif sort == "title":
        result.sort(key=lambda m: m.title.casefold())
    return result


@app.get("/movies/{movie_id}")
async def get_movie(movie_id: int) -> Movie:
    return movies[find_index(movie_id)]


@app.post("/movies", status_code=201)
async def create_movie(body: MovieCreate) -> Movie:
    global next_id
    movie = Movie(id=next_id, **body.model_dump())
    next_id += 1
    movies.append(movie)
    return movie


@app.put("/movies/{movie_id}")
async def replace_movie(movie_id: int, body: MovieCreate) -> Movie:
    index = find_index(movie_id)
    movies[index] = Movie(id=movie_id, **body.model_dump())
    return movies[index]


@app.patch("/movies/{movie_id}")
async def update_movie(movie_id: int, body: MovieUpdate) -> Movie:
    index = find_index(movie_id)
    # exclude_unset keeps only the fields the client actually sent
    changes = body.model_dump(exclude_unset=True)
    movies[index] = movies[index].model_copy(update=changes)
    return movies[index]


@app.delete("/movies/{movie_id}", status_code=204)
async def delete_movie(movie_id: int) -> None:
    movies.pop(find_index(movie_id))


# ---------- Error handlers: same JSON shape as the Express app ----------

def error_response(status: int, code: str, message: str, details: list[str] | None = None):
    error = ErrorInfo(code=code, message=message, details=details)
    return JSONResponse(
        status_code=status,
        content={"error": error.model_dump(exclude_none=True)},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    location = errors[0]["loc"][0]  # "path", "query" or "body"
    if location == "path":
        return error_response(400, "INVALID_ID", "Id must be an integer")

    # loc looks like ("body", "year"); drop the first part to get the field name
    details = [f"{'.'.join(map(str, e['loc'][1:])) or 'body'}: {e['msg']}" for e in errors]
    if location == "query":
        return error_response(400, "INVALID_QUERY", "; ".join(details))
    return error_response(400, "VALIDATION_ERROR", "Movie data is invalid", details)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):  # raised by our own code
        return error_response(exc.status_code, **exc.detail)
    if exc.status_code in (404, 405):  # Express answers 404 for unknown methods too
        return error_response(404, "ROUTE_NOT_FOUND", "The requested route does not exist")
    return error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logger.error("Unhandled error: %s", exc)
    return error_response(500, "INTERNAL_SERVER_ERROR", "An unexpected server error occurred")
