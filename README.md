# IMDBKit

**imdbkit** is a robust Python library for scraping and retrieving detailed information about movies, TV series, and celebrities from IMDb. It provides a simple API to fetch information about movies, series, episodes, and people from IMDb.

## Credits

Credits: [SilentXBotz](https://t.me/SilentXBotz)

## Installation

You can install the package directly from the repository:

```bash
pip3 install git+https://github.com/NBBotz/IMDBKit
```

Or add it to your `requirements.txt`:

```text
git+https://github.com/NBBotz/IMDBKit
```

Or install from source (locally):

```bash
pip install .
```

To install development dependencies:

```bash
pip install .[dev]
```

## Usage

Here are some examples of how to use `imdbkit`.

### Initialization

The recommended way to use `imdbkit` is by creating an instance of `IMDBKit`.

```python
from imdbkit import IMDBKit

kit = IMDBKit()
```

### Search for a Title

```python
from imdbkit import TitleType

results = kit.search_movie("The Matrix", title_type=TitleType.Movies)
for title in results.titles:
    print(f"{title.title} ({title.year}) - {title.imdbId}")
```

### Get Movie Details

```python
movie = kit.get_movie("0133093") # Matrix
print(movie.title)
print(movie.year)
print(movie.rating)
print(movie.plot)
```

### Get Person Details

```python
person = kit.get_name("0000206") # Keanu Reeves
print(person.name)
print(person.bio)
print(person.birth_date)
```

### Get Season Episodes

```python
# Breaking Bad
episodes = kit.get_season_episodes("0903747", season=1)
for episode in episodes.episodes:
    print(f"S{episode.season}E{episode.episode}: {episode.title}")
```

### Get All Episodes

```python
# Fetch all episodes for a series
all_episodes = kit.get_all_episodes("0903747")
print(f"Total episodes found: {len(all_episodes)}")
```

### Get AKAs (Also Known As)

```python
akas = kit.get_akas("0133093")
for aka in akas:
    print(f"{aka.country.name}: {aka.title}")
```

### Get Filmography

```python
filmography = kit.get_filmography("0000206") # Keanu Reeves
print(f"Credits found: {len(filmography)}")
```

### Get Reviews

```python
reviews = kit.get_reviews("0133093")
for review in reviews:
    print(f"{review['author']['nickName']}: {review['summary']['originalText']}")
```

### Get Trivia

```python
trivia = kit.get_trivia("0133093")
for item in trivia:
    print(item['displayableArticle']['body']['plaidHtml'])
```

### Get Interests

```python
interests = kit.get_all_interests("0133093")
print(f"Interests: {', '.join(interests)}")
```

## Testing

To run the tests, you need to have `pytest` installed.

```bash
pip install .[test]
pytest
```

## Credits

This repository is a **modified version** of the original [imdbinfo](https://github.com/tveronesi/imdbinfo) Python package by tveronesi.

## Disclaimer

This library is intended for educational and research purposes only. It scrapes data from IMDb, which may be against their Terms of Service. Use it responsibly and at your own risk. The authors of this library are not responsible for any misuse or consequences resulting from the use of this software.
