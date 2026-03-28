# MIT License
# Copyright (c) 2026 NBBotz (https://github.com/NBBotz)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

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
from .protection import WafHandler
from curl_cffi import requests as cffi_requests
import niquests

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.graphql.imdb.com/"

# Users can override: imdbkit.api.USER_AGENTS_LIST = ["your-agent"]
USER_AGENTS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

# Cached WAF token — shared across all HTML page requests
_waf_token: Optional[str] = None


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

    # ── HTML page fetcher with WAF solver ─────────────────────────────────────

    def _request_json_url(self, url: str) -> Any:
        """
        Fetch an IMDb HTML page and extract __NEXT_DATA__ JSON.
        Handles AWS WAF 202 challenges automatically using curl_cffi + WafHandler.
        Caches the WAF token globally so subsequent requests skip re-solving.
        """
        global _waf_token
        user_agent = random.choice(USER_AGENTS_LIST)

        # First attempt — use cached token if we have one
        cookies = {"aws-waf-token": _waf_token} if _waf_token else {}
        resp = cffi_requests.get(url, cookies=cookies, impersonate="chrome")

        # WAF challenge received — solve it
        if resp.status_code == 202:
            logger.warning("HTTP 202 WAF challenge received for %s, solving...", url)
            try:
                session = cffi_requests.Session(impersonate="chrome")
                tk, host = WafHandler.parse_challenge(resp.text)
                token = WafHandler(tk, host, "www.imdb.com", session)()
                _waf_token = token
                logger.debug("WAF challenge solved, retrying with token")
                resp = cffi_requests.get(
                    url, cookies={"aws-waf-token": token}, impersonate="chrome"
                )
            except Exception as e:
                logger.warning(
                    "WAF challenge solve failed: %s — retrying without token", e
                )
                _waf_token = None
                resp = cffi_requests.get(url, cookies={}, impersonate="chrome")

        if resp.status_code != 200:
            logger.error("Error fetching %s: %s", url, resp.status_code)
            error_msg = f"Error fetching {url}: HTTP {resp.status_code}"
            if resp.text:
                error_msg += f" - {resp.text[:200]}"
            if resp.status_code == 202:
                error_msg += " — AWS WAF enforcement in place. Try again later."
            raise Exception(error_msg)

        tree = html.fromstring(resp.content or b"")
        script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
        if not script or type(script) is not list:
            logger.error("No __NEXT_DATA__ script found at %s", url)
            raise Exception("No script found with id '__NEXT_DATA__'")
        return json.loads(str(script[0]))

    # ── GraphQL request (no WAF — uses plain niquests) ─────────────────────────

    def _make_graphql_request(self, headers, search_term, payload, url) -> Any:
        resp = cffi_requests.post(url, headers=headers, json=payload, impersonate="chrome")
        # resp = niquests.post(url, headers=headers, json=payload)
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

    # ── Public API ─────────────────────────────────────────────────────────────

    @lru_cache(maxsize=128)
    def get_movie(self, imdb_id: str, locale: Optional[str] = None) -> Optional[MovieDetail]:
        """Fetch full movie details. Uses HTML page + WAF solver."""
        imdb_id, lang = self._normalize_imdb_id(imdb_id, locale)
        url = f"https://www.imdb.com/{lang}/title/tt{imdb_id}/reference"
        t0 = time()
        logger.info("Fetching movie %s", imdb_id)
        raw_json = self._request_json_url(url)
        logger.debug("Fetched movie %s in %.2f seconds", imdb_id, time() - t0)
        return parse_json_movie(raw_json)

    @lru_cache(maxsize=128)
    def search_movie(
        self,
        title: str,
        locale: Optional[str] = None,
        title_type: Optional[TitleFilter] = None,
    ) -> Optional[SearchResult]:
        """
        Search for a title using IMDb's GraphQL API — completely WAF-free.

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

        type_log = "All"
        if title_type:
            if isinstance(title_type, tuple):
                type_log = ", ".join(tt.name for tt in title_type)
            else:
                type_log = title_type.name

        query = """query {
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
              professionCategory { traits text { text id } }
            }
            knownForV2 {
              credits {
                title { id titleText { text } releaseYear { year } }
              }
            }
            canonicalUrl
          }
        }
      }
    }
  }
}""".replace("__SEARCH_TERM__", title).replace("__TYPES__", search_options_types)

        payload = {"query": query}
        headers = {
            "Content-Type": "application/json",
            "x-imdb-user-country": country_code,
            "User-Agent": random.choice(USER_AGENTS_LIST),
            "Referer": "https://www.imdb.com/",
            "Origin": "https://www.imdb.com",
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
        """Fetch person details. Uses HTML page + WAF solver."""
        person_id, lang = self._normalize_imdb_id(person_id, locale)
        url = f"https://www.imdb.com/{lang}/name/nm{person_id}/"
        t0 = time()
        logger.info("Fetching person %s", person_id)
        raw_json = self._request_json_url(url)
        logger.debug("Fetched person %s in %.2f seconds", person_id, time() - t0)
        return parse_json_person_detail(raw_json)

    @lru_cache(maxsize=128)
    def get_season_episodes(
        self, imdb_id: str, season=1, locale: Optional[str] = None
    ) -> SeasonEpisodesList:
        """Fetch season episodes. Uses HTML page + WAF solver."""
        imdb_id, lang = self._normalize_imdb_id(imdb_id, locale)
        url = f"https://www.imdb.com/{lang}/title/tt{imdb_id}/episodes/?season={season}"
        logger.info("Fetching episodes for series %s season %s", imdb_id, season)
        raw_json = self._request_json_url(url)
        episodes = parse_json_season_episodes(raw_json)
        logger.debug("Fetched %d episodes", len(episodes.episodes))
        return episodes

    @lru_cache(maxsize=128)
    def get_all_episodes(self, imdb_id: str, locale: Optional[str] = None):
        """Fetch all episodes via search URL. Uses HTML page + WAF solver."""
        series_id, lang = self._normalize_imdb_id(imdb_id, locale)
        url = f"https://www.imdb.com/{lang}/search/title/?count=250&series=tt{series_id}&sort=release_date,asc"
        logger.info("Fetching all episodes for series %s", imdb_id)
        raw_json = self._request_json_url(url)
        episodes = parse_json_bulked_episodes(raw_json)
        logger.debug("Fetched %d episodes", len(episodes))
        return episodes

    @lru_cache(maxsize=128)
    def get_episodes(
        self, imdb_id: str, season=1, locale: Optional[str] = None
    ) -> SeasonEpisodesList:
        """Deprecated — use get_season_episodes or get_all_episodes."""
        logger.warning(
            "get_episodes is deprecating, use get_season_episodes or get_all_episodes instead."
        )
        return self.get_season_episodes(imdb_id, season, locale)

    def get_akas(self, imdb_id: str) -> Union[AkasData, list]:
        """Fetch AKAs via GraphQL — WAF-free."""
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_title_info(imdb_id)
        if not raw_json:
            return []
        return parse_json_akas(raw_json)

    def get_all_interests(self, imdb_id: str):
        """Fetch interests/tags via GraphQL — WAF-free."""
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_title_info(imdb_id)
        if not raw_json:
            return []
        interests = []
        for edge in raw_json.get("interests", {}).get("edges", []):
            text = edge.get("node", {}).get("primaryText", {}).get("text", "")
            if text:
                interests.append(text)
        return interests

    def get_trivia(self, imdb_id: str) -> List[Dict]:
        """Fetch trivia via GraphQL — WAF-free."""
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_title_info(imdb_id)
        if not raw_json:
            return []
        return parse_json_trivia(raw_json)

    def get_reviews(self, imdb_id: str) -> List[Dict]:
        """Fetch reviews via GraphQL — WAF-free."""
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_title_info(imdb_id)
        if not raw_json:
            return []
        return parse_json_reviews(raw_json)

    def get_parental_guide(self, imdb_id: str):
        """Fetch parental guide via GraphQL — WAF-free."""
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_title_info(imdb_id)
        if not raw_json:
            return {}
        return parse_json_parental_guide(raw_json)

    def get_filmography(self, imdb_id) -> dict:
        """Fetch filmography via GraphQL — WAF-free."""
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_name_info(imdb_id)
        if not raw_json:
            return {}
        return parse_json_filmography(raw_json)

    @lru_cache(maxsize=128)
    def _get_extended_title_info(self, imdb_id) -> dict:
        """GraphQL: AKAs, trivia, reviews, interests, parental guide."""
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
                      id spoiler
                      author { nickName }
                      summary { originalText }
                      text { originalText { plaidHtml } }
                      authorRating submissionDate
                      helpfulness { upVotes downVotes }
                      __typename
                    }
                  }
                }
                parentsGuide {
                  categories {
                    category { id text }
                    guideItems(first: 10) {
                      edges { node { isSpoiler text { plaidHtml } } }
                    }
                    severity { id votedFor }
                    severityBreakdown { votedFor voteType }
                  }
                }
              }
            }
            """ % imdbId
        )
        payload = {"query": query}
        logger.info("Fetching extended title info for %s via GraphQL", imdb_id)
        data = self._make_graphql_request(headers, imdbId, payload, GRAPHQL_URL)
        return data.get("data", {}).get("title", {})

    def _get_extended_name_info(self, person_id) -> dict:
        """GraphQL: full filmography for a person."""
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
            """ % person_id_full
        )
        headers = {
            "Content-Type": "application/json",
            "x-imdb-user-country": country,
        }
        payload = {"query": query}
        logger.info("Fetching person %s from GraphQL", person_id_full)
        data = self._make_graphql_request(headers, person_id_full, payload, GRAPHQL_URL)
        return data.get("data", {}).get("name", {})


# ── Module-level singleton + convenience functions ────────────────────────────

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
