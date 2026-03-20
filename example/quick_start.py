from imdbkit import IMDBKit
import logging

logging.basicConfig(level=logging.WARNING)

kit = IMDBKit()

# Example 1: Search title/name and print the results
title_query = "little house on the prairie"
results = kit.search_movie(title_query)
print(f"Search Results for {title_query} in titles:")
for movie in results.titles:
    print(f"Found a movie: {movie.title} ({movie.title_localized}) - {movie.imdbId} of kind {movie.kind}")

# Example 2: Get movie details
imdb_id = "tt0133093"
movie = kit.get_movie(imdb_id)
print(f"Movie Title: {movie.title} ({movie.year}) - {movie.imdbId}")
