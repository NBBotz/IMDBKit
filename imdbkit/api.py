import random
import re
from typing import Optional, Dict, Union, List, Tuple, Any
from functools import lru_cache
from time import time
import logging
import json
from lxml import html
from enum import Enum

from .structs import (
    SearchResult,
    MovieDetail,
    SeasonEpisodesList,
    PersonDetail,
    AkasData,
)
from .data_parsing import (
    parse_json_movie,
    parse_json_search,
    parse_json_person_detail,
    parse_json_season_episodes,
    parse_json_bulked_episodes,
    parse_json_akas,
    parse_json_trivia,
    parse_json_reviews,
    parse_json_filmography,
    parse_json_parental_guide,
)
from .i18n import _retrieve_url_lang, _get_country_code_from_lang_locale
import niquests

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.graphql.imdb.com/"

# Users can override this by setting: imdbkit.api.USER_AGENTS_LIST = ["your-agent"]
USER_AGENTS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]


class TitleType(Enum):
    """
    Defines the valid 'ttype' filters for title searches on IMDb.
    The values correspond to the URL parameter used in search queries.
    """
    Movies   = "ft"
    Series   = "tv"
    Episodes = "ep"
    Shorts   = "sh"
    TvMovie  = "tvm"
    Video    = "v"


title_type_search_type = {
    TitleType.Movies:   "MOVIE",
    TitleType.Series:   "TV",
    TitleType.Episodes: "TV_EPISODE",
    TitleType.Shorts:   "MOVIE",
    TitleType.TvMovie:  "TV",
    TitleType.Video:    "",
}

TitleFilter = Union[TitleType, Tuple[TitleType, ...]]


class IMDBKit:
    def __init__(self, locale: Optional[str] = None):
        self.locale = locale

    def _normalize_imdb_id(self, imdb_id: str, locale: Optional[str] = None):
        imdb_id = str(imdb_id)
        num = int(re.sub(r"\D", "", imdb_id))
        effective_locale = locale if locale is not None else self.locale
        lang = _retrieve_url_lang(effective_locale)
        imdb_id = f"{num:07d}"
        return imdb_id, lang

    def _request_json_url(self, url: str) -> Any:
        user_agent = random.choice(USER_AGENTS_LIST)
        logger.debug("Using User-Agent: %s", user_agent)
        headers = {"User-Agent": user_agent}
        resp = niquests.get(url, headers=headers)

        if resp.status_code != 200:
            logger.error("Error fetching %s: %s", url, resp.status_code)
            error_msg = f"Error fetching {url}: HTTP {resp.status_code}"
            if resp.text:
                error_msg += f" - {resp.text[:200]}"
            raise Exception(error_msg)

        tree = html.fromstring(resp.content or b"")
        script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
        if not script or type(script) is not list:
            logger.error("No script found with id '__NEXT_DATA__'")
            raise Exception("No script found with id '__NEXT_DATA__'")
        return json.loads(str(script[0]))

    def _make_graphql_request(self, headers, search_term, payload, url) -> Any:
        resp = niquests.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.error("GraphQL request failed: %s", resp.status_code)
            error_msg = f"GraphQL request failed for {search_term}: HTTP {resp.status_code}"
            if resp.text:
                error_msg += f" - {resp.text[:200]}"
            raise Exception(error_msg)
        data = resp.json()
        if "errors" in data:
            logger.error("GraphQL error: %s", data["errors"])
            raise Exception(f"GraphQL error for {search_term}: {data['errors']}")
        return data

    @lru_cache(maxsize=128)
    def get_movie(self, imdb_id: str, locale: Optional[str] = None) -> Optional[MovieDetail]:
        """Fetch movie details from IMDb using the provided IMDb ID."""
        imdb_id, lang = self._normalize_imdb_id(imdb_id, locale)
        url = f"https://www.imdb.com/{lang}/title/tt{imdb_id}/reference"
        t0 = time()
        logger.info("Fetching movie %s", imdb_id)
        raw_json = self._request_json_url(url)
        t1 = time()
        logger.debug("Fetched movie %s in %.2f seconds", imdb_id, t1 - t0)
        movie = parse_json_movie(raw_json)
        return movie

    @lru_cache(maxsize=128)
    def search_movie(
        self,
        title: str,
        locale: Optional[str] = None,
        title_type: Optional[TitleFilter] = None,
    ) -> Optional[SearchResult]:
        """
        Search for a title using IMDb's GraphQL API (WAF-free).

        :param title: Title to search for.
        :param locale: Optional locale string (e.g., 'en', 'es').
        :param title_type: Optional filter(s) for media type.
        """
        effective_locale = locale if locale is not None else self.locale
        country_code = _get_country_code_from_lang_locale(effective_locale)

        search_options_types = ""
        if title_type:
            tt_iter = title_type if isinstance(title_type, tuple) else (title_type,)
            types = [
                title_type_search_type.get(tt)
                for tt in tt_iter
                if tt is not TitleType.Video
            ]
            search_options_types = ",".join(filter(None, types))

        if not title_type:
            type_log = "All"
        else:
            if isinstance(title_type, tuple):
                type_log = ", ".join(tt.name for tt in title_type)
            else:
                type_log = title_type.name

        query_template = """query {
  mainSearch(
    first: 50
    options: {
      searchTerm: "__SEARCH_TERM__"
      isExactMatch: false
      type: [TITLE, NAME]
      titleSearchOptions: { type: [__TYPES__] }
    }
  ) {
    edges {
      node {
        entity {
          ... on Title {
            __typename
            id
            titleText { text }
            canonicalUrl
            originalTitleText { text }
            releaseDate { year month day }
            primaryImage { url }
            titleType { id text categories { id text value } }
            ratingsSummary { aggregateRating }
            runtime { seconds }
          }
          ... on Name {
            __typename
            id
            nameText { text }
            professions {
              profession { text }
              professionCategory {
                traits
                text { text id }
              }
            }
            knownForV2 {
              credits {
                title {
                  id
                  titleText { text }
                  releaseYear { year }
                }
              }
            }
            canonicalUrl
          }
        }
      }
    }
  }
}"""

        query = (
            query_template
            .replace("__SEARCH_TERM__", title)
            .replace("__TYPES__", search_options_types)
        )
        payload = {"query": query}
        headers = {
            "Content-Type": "application/json",
            "x-imdb-user-country": country_code,
        }

        logger.info("Searching for title '%s' [Type: %s] via GraphQL", title, type_log)
        try:
            data = self._make_graphql_request(
                headers=headers, search_term=title, payload=payload, url=GRAPHQL_URL
            )
        except Exception as e:
            logger.warning("Search request failed: %s", e)
            return None

        result = parse_json_search(data)
        logger.debug("Search for '%s' returned %s titles", title, len(result.titles))
        return result

    @lru_cache(maxsize=128)
    def get_name(self, person_id: str, locale: Optional[str] = None) -> Optional[PersonDetail]:
        """Fetch person details from IMDb using the provided IMDb ID."""
        person_id, lang = self._normalize_imdb_id(person_id, locale)
        url = f"https://www.imdb.com/{lang}/name/nm{person_id}/"
        t0 = time()
        logger.info("Fetching person %s", person_id)
        raw_json = self._request_json_url(url)
        t1 = time()
        logger.debug("Fetched person %s in %.2f seconds", person_id, t1 - t0)
        t0 = time()
        person = parse_json_person_detail(raw_json)
        t1 = time()
        logger.debug("Parsed person %s in %.2f seconds", person_id, t1 - t0)
        return person

    @lru_cache(maxsize=128)
    def get_season_episodes(
        self, imdb_id: str, season=1, locale: Optional[str] = None
    ) -> SeasonEpisodesList:
        """Fetch episodes for a series using the provided IMDb ID."""
        imdb_id, lang = self._normalize_imdb_id(imdb_id, locale)
        url = f"https://www.imdb.com/{lang}/title/tt{imdb_id}/episodes/?season={season}"
        logger.info("Fetching episodes for movie %s", imdb_id)
        raw_json = self._request_json_url(url)
        episodes = parse_json_season_episodes(raw_json)
        logger.debug("Fetched %d episodes for movie %s", len(episodes.episodes), imdb_id)
        return episodes

    @lru_cache(maxsize=128)
    def get_all_episodes(self, imdb_id: str, locale: Optional[str] = None):
        series_id, lang = self._normalize_imdb_id(imdb_id, locale)
        url = f"https://www.imdb.com/{lang}/search/title/?count=250&series=tt{series_id}&sort=release_date,asc"
        logger.info("Fetching bulk episodes for series %s", imdb_id)
        raw_json = self._request_json_url(url)
        episodes = parse_json_bulked_episodes(raw_json)
        logger.debug("Fetched %d episodes for series %s", len(episodes), imdb_id)
        return episodes

    @lru_cache(maxsize=128)
    def get_episodes(
        self, imdb_id: str, season=1, locale: Optional[str] = None
    ) -> SeasonEpisodesList:
        """Deprecated: use get_season_episodes or get_all_episodes instead."""
        logger.warning(
            "get_episodes is deprecating, use get_season_episodes or get_all_episodes instead."
        )
        return self.get_season_episodes(imdb_id, season, locale)

    def get_akas(self, imdb_id: str) -> Union[AkasData, list]:
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_title_info(imdb_id)
        if not raw_json:
            logger.warning("No AKAs found for title %s", imdb_id)
            return []
        akas = parse_json_akas(raw_json)
        logger.debug("Fetched %d AKAs for title %s", len(akas), imdb_id)
        return akas

    def get_all_interests(self, imdb_id: str):
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_title_info(imdb_id)
        if not raw_json:
            logger.warning("No interests found for title %s", imdb_id)
            return []
        interests = []
        interests_edges = raw_json.get("interests", {}).get("edges", [])
        for edge in interests_edges:
            node = edge.get("node", {})
            primary_text = node.get("primaryText", {}).get("text", "")
            if primary_text:
                interests.append(primary_text)
        logger.debug("Fetched %d interests for title %s", len(interests), imdb_id)
        return interests

    def get_trivia(self, imdb_id: str) -> List[Dict]:
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_title_info(imdb_id)
        if not raw_json:
            logger.warning("No trivia found for title %s", imdb_id)
            return []
        trivia_list = parse_json_trivia(raw_json)
        logger.debug("Fetched %d trivia items for title %s", len(trivia_list), imdb_id)
        return trivia_list

    def get_reviews(self, imdb_id: str) -> List[Dict]:
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_title_info(imdb_id)
        if not raw_json:
            logger.warning("No reviews found for title %s", imdb_id)
            return []
        reviews_list = parse_json_reviews(raw_json)
        logger.debug("Fetched %d reviews for title %s", len(reviews_list), imdb_id)
        return reviews_list

    def get_parental_guide(self, imdb_id: str):
        """Fetch parental guide for a title using the provided IMDb ID."""
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_title_info(imdb_id)
        if not raw_json:
            logger.warning("No parental guide found for title %s", imdb_id)
            return {}
        parental_guide = parse_json_parental_guide(raw_json)
        logger.debug("Fetched parental guide for title %s", imdb_id)
        return parental_guide

    def get_filmography(self, imdb_id) -> dict:
        """Fetch full filmography for a person using the provided IMDb ID."""
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_name_info(imdb_id)
        if not raw_json:
            logger.warning("No full_credit found for name %s", imdb_id)
            return {}
        full_credits_list = parse_json_filmography(raw_json)
        logger.debug("Fetched full_credits for name %s", imdb_id)
        return full_credits_list

    @lru_cache(maxsize=128)
    def _get_extended_title_info(self, imdb_id) -> dict:
        """
        Fetch extended info (AKAs, trivia, reviews, interests, parental guide)
        using IMDb's GraphQL API.
        """
        imdbId = "tt" + imdb_id
        country = _get_country_code_from_lang_locale()
        headers = {
            "Content-Type": "application/json",
            "x-imdb-user-country": country,
        }
        query = (
            """
            query {
              title(id: "%s") {
                id
                titleText { text }
                originalTitle: originalTitleText { text }
                interests(first: 20) {
                  edges { node { primaryText { text } } }
                }
                akas(first: 200) {
                  edges {
                    node {
                      country { name: text code: id }
                      language { name: text code: id }
                      title: text
                    }
                  }
                }
                trivia(first: 50) {
                  edges {
                    node {
                      id
                      displayableArticle { body { plaidHtml } }
                      interestScore { usersVoted usersInterested }
                    }
                  }
                }
                reviews(first: 50) {
                  edges {
                    node {
                      id
                      spoiler
                      author { nickName }
                      summary { originalText }
                      text { originalText { plaidHtml } }
                      authorRating
                      submissionDate
                      helpfulness { upVotes downVotes }
                      __typename
                    }
                  }
                }
                parentsGuide {
                  categories {
                    category { id text }
                    guideItems(first: 10) {
                      edges {
                        node {
                          isSpoiler
                          text { plaidHtml }
                        }
                      }
                    }
                    severity { id votedFor }
                    severityBreakdown { votedFor voteType }
                  }
                }
              }
            }
            """
            % imdbId
        )
        payload = {"query": query}
        logger.info("Fetching title %s from GraphQL API", imdb_id)
        data = self._make_graphql_request(headers, imdbId, payload, GRAPHQL_URL)
        return data.get("data", {}).get("title", {})

    def _get_extended_name_info(self, person_id) -> dict:
        """Fetch extended person info using IMDb's GraphQL API."""
        person_id_full = "nm" + person_id
        country = _get_country_code_from_lang_locale()
        query = (
            """
            query {
              name(id: "%s") {
                nameText { text }
                credits(first: 250
                  filter: {
                    categories: [
                      "production_designer" "casting_department" "director" "composer"
                      "casting_director" "executive" "art_director" "actress"
                      "costume_designer" "writer" "camera_department" "art_department"
                      "publicist" "cinematographer" "location_management" "soundtrack"
                      "sound_department" "talent_agent" "set_decorator"
                      "animation_department" "make_up_department" "costume_department"
                      "script_department" "producer" "stunts" "editor"
                      "stunt_coordinator" "special_effects" "assistant_director"
                      "editorial_department" "music_department" "transportation_department"
                      "actor" "visual_effects" "production_manager" "archive_sound"
                    ]
                  }
                ) {
                  edges {
                    node {
                      category { id }
                      title {
                        id
                        ratingsSummary { aggregateRating }
                        primaryImage { url }
                        originalTitleText { text }
                        titleText { text }
                        titleType { id }
                        releaseYear { year }
                      }
                    }
                  }
                  pageInfo { endCursor hasNextPage }
                }
              }
            }
            """
            % person_id_full
        )
        headers = {
            "Content-Type": "application/json",
            "x-imdb-user-country": country,
        }
        payload = {"query": query}
        logger.info("Fetching person %s from GraphQL API", person_id_full)
        data = self._make_graphql_request(headers, person_id_full, payload, GRAPHQL_URL)
        return data.get("data", {}).get("name", {})


# ── Module-level singleton and convenience functions ──────────────────────────

_default_kit = IMDBKit()


def normalize_imdb_id(imdb_id: str, locale: Optional[str] = None):
    return _default_kit._normalize_imdb_id(imdb_id, locale)

def request_json_url(url: str) -> Any:
    return _default_kit._request_json_url(url)

def make_graphql_request(headers, search_term, payload, url) -> Any:
    return _default_kit._make_graphql_request(headers, search_term, payload, url)

def get_movie(imdb_id: str, locale: Optional[str] = None) -> Optional[MovieDetail]:
    return _default_kit.get_movie(imdb_id, locale)

def search_movie(
    title: str, locale: Optional[str] = None, title_type: Optional[TitleFilter] = None
) -> Optional[SearchResult]:
    return _default_kit.search_movie(title, locale, title_type)

def get_name(person_id: str, locale: Optional[str] = None) -> Optional[PersonDetail]:
    return _default_kit.get_name(person_id, locale)

def get_season_episodes(
    imdb_id: str, season=1, locale: Optional[str] = None
) -> SeasonEpisodesList:
    return _default_kit.get_season_episodes(imdb_id, season, locale)

def get_all_episodes(imdb_id: str, locale: Optional[str] = None):
    return _default_kit.get_all_episodes(imdb_id, locale)

def get_episodes(
    imdb_id: str, season=1, locale: Optional[str] = None
) -> SeasonEpisodesList:
    return _default_kit.get_episodes(imdb_id, season, locale)

def get_akas(imdb_id: str) -> Union[AkasData, list]:
    return _default_kit.get_akas(imdb_id)

def get_all_interests(imdb_id: str):
    return _default_kit.get_all_interests(imdb_id)

def get_trivia(imdb_id: str) -> List[Dict]:
    return _default_kit.get_trivia(imdb_id)

def get_reviews(imdb_id: str) -> List[Dict]:
    return _default_kit.get_reviews(imdb_id)

def get_parental_guide(imdb_id: str):
    return _default_kit.get_parental_guide(imdb_id)

def get_filmography(imdb_id) -> dict:
    return _default_kit.get_filmography(imdb_id)
