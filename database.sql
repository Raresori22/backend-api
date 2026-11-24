DROP TABLE IF EXISTS movies;

CREATE TABLE movies (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    director VARCHAR(200) NOT NULL,
    release_year INTEGER NOT NULL
);

INSERT INTO movies (
    title,
    director,
    release_year
)
VALUES
    ('Inception', 'Christopher Nolan', 2010),
    ('The Matrix', 'The Wachowskis', 1999),
    ('Parasite', 'Bong Joon-ho', 2019);

SELECT *
FROM movies
ORDER BY id;