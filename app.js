let movies = [
  {
    id: 1,
    title: "Inception",
    director: "Christopher Nolan",
    year: 2010,
    genre: "Sci-Fi"
  },
  {
    id: 2,
    title: "The Matrix",
    director: "The Wachowskis",
    year: 1999,
    genre: "Sci-Fi"
  },
  {
    id: 3,
    title: "Parasite",
    director: "Bong Joon-ho",
    year: 2019,
    genre: "Thriller"
  }
];


const express = require("express");
const morgan = require("morgan");

const app = express();

app.use(express.json());
app.use(morgan("dev"));


app.get('/', (req, res) => {
res.send('Hello from Express');
});

app.get('/movies', (req, res) => {
    const { genre, minYear, sort } = req.query;
    let result = [...movies];

    if(genre) {
        result = result.filter(m => m.genre.toLowerCase() === genre.toLowerCase());
    }

    if(minYear) {
        const year = Number(minYear);
        if (!Number.isInteger(year)) {
            return res.status(400).json({ error: { code: "INVALID_QUERY", message: "minYear must be an integer" } });
        }
        result = result.filter(m => m.year >= year);
    }
    if (sort === 'year') result.sort((a, b) => a.year - b.year);
    else if (sort === 'title') result.sort((a, b) =>    a.title.localeCompare(b.title));
    else if (sort) return res.status(400).json({ error: { code: "INVALID_QUERY", message: "sort must be 'year' or 'title'" } });

    res.json(result);
});

app.get('/movies/:id', (req, res) => {
    const id = Number(req.params.id);
    if (!Number.isInteger(id)) {
        return res.status(400).json({ error: { code: "INVALID_ID", message: "Id must be an integer" } });
    }

    const movie = movies.find(m => m.id === id);
    if(!movie) return res.status(404).json({ error: { code: "MOVIE_NOT_FOUND", message: "Movie not found" } });
    res.json(movie);
});

app.post('/movies', (req, res) => {
    const errors = validateMovie( req.body, false );
    if( errors.length > 0 ){
        return res.status(400).json({ error: { code: "VALIDATION_ERROR", message: "Movie data is invalid", details: errors } });
    }

    const { title, director, year, genre } = req.body;
    const newMovie = { id: movies.length + 1, title, director, year, genre };
    movies.push(newMovie);
    res.status(201).json(newMovie);
})

app.delete('/movies/:id', (req, res) => {
    const id = Number(req.params.id);
    if(!Number.isInteger(id)) {
        return res.status(400).json({ error: { code: "INVALID_ID", message: "Id must be an integer" } });
    }

    const index = movies.findIndex(movie => movie.id === id);
    if(index === -1) {
        return res.status(404).json({ error: { code: "MOVIE_NOT_FOUND", message: "Movie not found" } });
    }

    movies.splice(index, 1);
    res.status(204).send();
})

app.put('/movies/:id', (req, res) => {
    const id = Number(req.params.id);
    if(!Number.isInteger(id)) {
        return res.status(400).json({ error: { code: "INVALID_ID", message: "Id must be an integer" } });
    }

    const index = movies.findIndex( m => m.id === id );
    if( index === -1 ) {
        return res.status(404).json({ error: { code: "MOVIE_NOT_FOUND", message: "Movie not found" } });
    }

    const errors = validateMovie( req.body, false );
    if( errors.length > 0 ){
        return res.status(400).json({ error: { code: "VALIDATION_ERROR", message: "Movie data is invalid", details: errors } });
    }

    const { title, director, year, genre } = req.body;
    movies[index] = { id, title, director, year, genre };
    res.json(movies[index]);
})

app.patch('/movies/:id', (req, res) => {
    const id = Number(req.params.id);
    if(!Number.isInteger(id)) {
        return res.status(400).json({ error: { code: "INVALID_ID", message: "Id must be an integer" } });
    }

    const movie = movies.find(m => m.id === id);
    if (!movie) {
      return res.status(404).json({ error: { code: "MOVIE_NOT_FOUND", message: "Movie not found" } });
    }

    const errors = validateMovie( req.body, true );
    if( errors.length > 0 ){
        return res.status(400).json({ error: { code: "VALIDATION_ERROR", message: "Movie data is invalid", details: errors } });
    }

    const { title, director, year, genre } = req.body;
    if (title !== undefined) movie.title = title;
    if (director !== undefined) movie.director = director;
    if (year !== undefined) movie.year = year;
    if (genre !== undefined) movie.genre = genre;

    res.status(200).json(movie);
})



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
 
  if (!partial && body.genre === undefined)
    errors.push("genre is required");
  if (body.genre !== undefined &&
      (typeof body.genre !== "string" || body.genre.trim().length === 0))
    errors.push("genre must be a non-empty string");

  return errors;
}

app.use((req, res) => {
  res.status(404).json({
    error: {
      code: "ROUTE_NOT_FOUND",
      message: "The requested route does not exist"
    }
  });
});

app.use((err, req, res, next) => {
  console.error(err);

  res.status(500).json({
    error: {
      code: "INTERNAL_SERVER_ERROR",
      message: "An unexpected server error occurred"
    }
  });
});

app.listen(3000, () => {
console.log('http://localhost:3000');
});



