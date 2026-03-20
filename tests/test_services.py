import os
import json
from types import SimpleNamespace

from imdbkit import api as services

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_json_source")


def load_sample_text(filename: str) -> str:
    with open(os.path.join(SAMPLE_DIR, filename), encoding="utf-8") as f:
        return f.read()


def mock_get_factory(filename: str):
    json_text = load_sample_text(filename)
    html = f'<html><script id="__NEXT_DATA__">{json_text}</script></html>'.encode(
        "utf-8"
    )

    def mock_get(*args, **kwargs):
        return SimpleNamespace(status_code=200, content=html)

    return mock_get


def mock_post_factory(filename: str):
    json_text = load_sample_text(filename)

    def mock_post(*args, **kwargs):
        # Provide a .json() method so callers can get parsed JSON (as real requests.Response.json would)
        return SimpleNamespace(
            status_code=200, content=json_text, json=lambda: json.loads(json_text)
        )

    return mock_post


def test_get_movie(monkeypatch):
    monkeypatch.setattr(
        services.niquests, "get", mock_get_factory("sample_resource.json")
    )
    movie = services.get_movie("tt0133093")
    assert movie.title == "The Matrix"
    assert movie.duration == 136


def test_search_movie(monkeypatch):
    # Use POST mock for GraphQL-style search responses
    # allow setting 'post' even if the niquests stub doesn't define it by default
    monkeypatch.setattr(
        services.niquests,
        "post",
        mock_post_factory("sample_search.json"),
        raising=False,
    )
    result = services.search_movie("matrix")
    assert result.titles[0].title == "The Matrix"
    assert result.names


def test_search_movie_includes_rating(monkeypatch):
    monkeypatch.setattr(
        services.niquests,
        "post",
        mock_post_factory("sample_search.json"),
        raising=False,
    )
    result = services.search_movie("matrix")
    assert result.titles[0].rating == 8.7
    assert result.titles[1].rating == 7.2
    assert result.titles[2].rating == 5.6


def test_get_name(monkeypatch):
    monkeypatch.setattr(
        services.niquests, "get", mock_get_factory("sample_person.json")
    )
    person = services.get_name("nm0000126")
    assert person.name == "Kevin Costner"
    assert "Balla coi lupi" in person.knownfor
