"""
Example: Using a custom User-Agent

This example demonstrates how to override the default User-Agent
used for HTTP requests to IMDb.
"""

from imdbkit import IMDBKit
import imdbkit.api

# Check the default User-Agent
print(f"Default User-Agent List: {imdbkit.api.USER_AGENTS_LIST}")

# Override with a custom User-Agent
imdbkit.api.USER_AGENTS_LIST = [
    "MyCustomApp/1.0 (Contact: myemail@example.com)",
    "AnotherUserAgent/2.0"
    ]

print(f"Custom User-Agent List: {imdbkit.api.USER_AGENTS_LIST}")

# Now all requests will use the custom User-Agent
kit = IMDBKit()
try:
    movie = kit.get_movie("tt0133093")  # The Matrix
    print(f"\nFetched movie: {movie.title} ({movie.year})")
    print(f"Rating: {movie.rating}")
except Exception as e:
    print(f"Error: {e}")

# Note: If you get an error, the error message will now include
# more details like HTTP status code and response text
