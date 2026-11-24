require("dotenv").config();

const express = require("express");
const morgan = require("morgan");
const pool = require("./db");

const app = express();

app.use(express.json());
app.use(morgan("dev"));

// Allow-lists: only these server-defined column names may become SQL text
const sortColumns = {
    id: "id",
    title: "title",
    year: "release_year"
};

const allowedFields = {
    title: "title",
    director: "director",
    year: "release_year"
};

const MAX_INTEGER = 2147483647; // largest PostgreSQL INTEGER

// Returns a positive integer, or null if the text isn't a valid one
function parsePositiveInt(text) {
    if (typeof text !== "string" || !/^\d+$/.test(text)) return null;
    const number = Number(text);
    return number >= 1 && number <= MAX_INTEGER ? number : null;
}

function sendError(res, status, code, message, details) {
    res.status(status).json({ error: { code, message, details } });
}

app.get('/', (req, res) => {
    res.send('Hello from Express');
});

app.get('/movies', async (req, res, next) => {
    try {
        const { director, year, sortBy = "id" } = req.query;
        const conditions = [];
        const values = [];

        if (director !== undefined) {
            if (typeof director !== "string" || director.trim() === "") {
                return sendError(res, 400, "INVALID_QUERY", "director must be a non-empty string");
            }
            values.push(director);
            conditions.push(`LOWER(director) = LOWER($${values.length})`);
        }

        if (year !== undefined) {
            const yearNumber = parsePositiveInt(year);
            if (yearNumber === null) {
                return sendError(res, 400, "INVALID_QUERY", "year must be a positive integer");
            }
            values.push(yearNumber);
            conditions.push(`release_year = $${values.length}`);
        }

        if (typeof sortBy !== "string" || !Object.hasOwn(sortColumns, sortBy)) {
            return sendError(res, 400, "INVALID_QUERY", "sortBy must be 'id', 'year' or 'title'");
        }

        const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

        const result = await pool.query(`
            SELECT
                id,
                title,
                director,
                release_year AS year
            FROM movies
            ${where}
            ORDER BY ${sortColumns[sortBy]}, id
        `, values);

        res.json(result.rows);
    } catch (error) {
        next(error);
    }
});

app.get('/movies/:id', async (req, res, next) => {
    try {
        const id = parsePositiveInt(req.params.id);
        if (id === null) {
            return sendError(res, 400, "INVALID_ID", "Id must be a positive integer");
        }

        const result = await pool.query(`
            SELECT
                id,
                title,
                director,
                release_year AS year
            FROM movies
            WHERE id = $1
        `, [id]);

        if (result.rows.length === 0) {
            return sendError(res, 404, "MOVIE_NOT_FOUND", "Movie not found");
        }
        res.json(result.rows[0]);
    } catch (error) {
        next(error);
    }
});

app.post('/movies', async (req, res, next) => {
    try {
        const body = req.body ?? {}; // req.body is undefined when no JSON was sent
        const errors = validateMovie(body, false);
        if (errors.length > 0) {
            return sendError(res, 400, "VALIDATION_ERROR", "Movie data is invalid", errors);
        }

        const { title, director, year } = body;
        const result = await pool.query(`
            INSERT INTO movies (
                title,
                director,
                release_year
            )
            VALUES ($1, $2, $3)
            RETURNING
                id,
                title,
                director,
                release_year AS year
        `, [title, director, year]);

        res.status(201).json(result.rows[0]);
    } catch (error) {
        next(error);
    }
});

// replaces all data of a movie
app.put('/movies/:id', async (req, res, next) => {
    try {
        const id = parsePositiveInt(req.params.id);
        if (id === null) {
            return sendError(res, 400, "INVALID_ID", "Id must be a positive integer");
        }

        const body = req.body ?? {};
        const errors = validateMovie(body, false);
        if (errors.length > 0) {
            return sendError(res, 400, "VALIDATION_ERROR", "Movie data is invalid", errors);
        }

        const { title, director, year } = body;
        const result = await pool.query(`
            UPDATE movies
            SET
                title = $1,
                director = $2,
                release_year = $3
            WHERE id = $4
            RETURNING
                id,
                title,
                director,
                release_year AS year
        `, [title, director, year, id]);

        if (result.rows.length === 0) {
            return sendError(res, 404, "MOVIE_NOT_FOUND", "Movie not found");
        }
        res.json(result.rows[0]);
    } catch (error) {
        next(error);
    }
});

// replaces only the fields that were sent
app.patch('/movies/:id', async (req, res, next) => {
    try {
        const id = parsePositiveInt(req.params.id);
        if (id === null) {
            return sendError(res, 400, "INVALID_ID", "Id must be a positive integer");
        }

        const body = req.body ?? {};
        const errors = validateMovie(body, true);
        if (errors.length > 0) {
            return sendError(res, 400, "VALIDATION_ERROR", "Movie data is invalid", errors);
        }

        // Loop over the allow-list, never over the client's keys
        const setClauses = [];
        const values = [];
        for (const [field, column] of Object.entries(allowedFields)) {
            if (body[field] !== undefined) {
                values.push(body[field]);
                setClauses.push(`${column} = $${values.length}`);
            }
        }

        if (setClauses.length === 0) {
            return sendError(res, 400, "VALIDATION_ERROR", "Movie data is invalid",
                ["provide at least one of: title, director, year"]);
        }

        values.push(id);
        const result = await pool.query(`
            UPDATE movies
            SET ${setClauses.join(", ")}
            WHERE id = $${values.length}
            RETURNING
                id,
                title,
                director,
                release_year AS year
        `, values);

        if (result.rows.length === 0) {
            return sendError(res, 404, "MOVIE_NOT_FOUND", "Movie not found");
        }
        res.json(result.rows[0]);
    } catch (error) {
        next(error);
    }
});

app.delete('/movies/:id', async (req, res, next) => {
    try {
        const id = parsePositiveInt(req.params.id);
        if (id === null) {
            return sendError(res, 400, "INVALID_ID", "Id must be a positive integer");
        }

        const result = await pool.query(`
            DELETE FROM movies
            WHERE id = $1
            RETURNING id
        `, [id]);

        if (result.rows.length === 0) {
            return sendError(res, 404, "MOVIE_NOT_FOUND", "Movie not found");
        }
        res.status(204).send();
    } catch (error) {
        next(error);
    }
});

app.get("/health/database", async (req, res, next) => {
    try {
        const result = await pool.query(
            "SELECT NOW() AS database_time"
        );

        res.json({
            status: "ok",
            databaseTime: result.rows[0].database_time
        });
    } catch (error) {
        next(error);
    }
});

function validateMovie(body, partial = false) {
  const errors = [];
  const maxYear = new Date().getFullYear() + 5;

  if (!partial && body.title === undefined)
    errors.push("title is required");
  if (body.title !== undefined &&
      (typeof body.title !== "string" || body.title.trim().length === 0))
    errors.push("title must be a non-empty string");

  if (!partial && body.director === undefined)
    errors.push("director is required");
  if (body.director !== undefined &&
      (typeof body.director !== "string" || body.director.trim().length === 0))
    errors.push("director must be a non-empty string");

  if (!partial && body.year === undefined)
    errors.push("year is required");
  if (body.year !== undefined &&
      (!Number.isInteger(body.year) || body.year < 1888 || body.year > maxYear))
    errors.push(`year must be an integer between 1888 and ${maxYear}`);

  return errors;
}

// Unknown routes
app.use((req, res) => {
    sendError(res, 404, "ROUTE_NOT_FOUND", "The requested route does not exist");
});

// Centralized error handler: must stay after all routes
app.use((err, req, res, next) => {
    if (res.headersSent) return next(err);

    if (err.type === "entity.parse.failed") {
        return sendError(res, 400, "INVALID_JSON", "Request body is not valid JSON");
    }
    if (err.code === "22001") { // PostgreSQL: value too long for VARCHAR(200)
        return sendError(res, 400, "VALIDATION_ERROR", "title and director can be at most 200 characters");
    }

    console.error(err);
    sendError(res, 500, "INTERNAL_SERVER_ERROR", "An unexpected server error occurred");
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`http://localhost:${PORT}`);
});
