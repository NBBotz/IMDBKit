from imdbkit import IMDBKit

import logging

logging.basicConfig(level=logging.WARNING)

kit = IMDBKit()

n = "nm0000206"

filmography_results = kit.get_filmography(n)
if filmography_results:
    for role, films in filmography_results.items():
        print(f"\nRole: {role}")
        for film in films:
            print(f" - {film.title} ({film.year}) [{film.imdbId}]")
            # cover
            print(f"   Cover URL: {film.cover_url}")
