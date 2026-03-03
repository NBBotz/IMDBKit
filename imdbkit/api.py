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
)
from .i18n import _retrieve_url_lang
from .protection import WafHandler
from curl_cffi import requests as cffi_requests  # imdbinfo jaisa — same import


class TitleType(Enum):
    """
    Defines the valid 'ttype' filters for title searches on IMDb.
    The values correspond to the URL parameter used in search queries.
    """

    Movies  = "ft"
    Series  = "tv"
    Episodes = "ep"
    Shorts  = "sh"
    TvMovie = "tvm"
    Video   = "v"


TitleFilter = Union[TitleType, Tuple[TitleType, ...]]

logger = logging.getLogger(__name__)

USER_AGENTS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

WAF_DETECTED = True


class IMDBKit:
    def __init__(self, locale: Optional[str] = None):
        self.locale = locale
        self.session = cffi_requests.Session(impersonate="chrome")
        self.session.headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.5",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "sec-gpc": "1",
            "upgrade-insecure-requests": "1",
        }

    def _normalize_imdb_id(self, imdb_id: str, locale: Optional[str] = None):
        imdb_id = str(imdb_id)
        num = int(re.sub(r"\D", "", imdb_id))
        effective_locale = locale if locale is not None else self.locale
        lang = _retrieve_url_lang(effective_locale)
        imdb_id = f"{num:07d}"
        return imdb_id, lang

    def _get_waf_token(self, html_text: str) -> dict:
        try:
            tk, host = WafHandler.parse_challenge(html_text)
            session = cffi_requests.Session(impersonate="chrome")
            token = WafHandler(tk, host, "www.imdb.com", session)()
            logger.debug("WAF token obtained: %s...", str(token)[:20])
            return {"aws-waf-token": token}
        except Exception as e:
            logger.warning("WAF solve failed: %s", e)
            return {}

    def _request_json_url(self, url: str) -> Any:
        global WAF_DETECTED
        user_agent = random.choice(USER_AGENTS_LIST)
        self.session.headers["user-agent"] = user_agent
        logger.debug("Using User-Agent: %s", user_agent)

        if WAF_DETECTED:
            logger.debug("WAF_DETECTED=True")
            resp = cffi_requests.get(url, cookies={}, impersonate="chrome")
        else:
            resp = self.session.get(url)

        if resp.status_code == 202:
            logger.warning("HTTP 202 received (WAF enforcement detected), solving WAF challenge...")
            try:
                session = cffi_requests.Session(impersonate="chrome")
                tk, host = WafHandler.parse_challenge(resp.text)
                token = WafHandler(tk, host, "www.imdb.com", session)()
                WAF_DETECTED = True
                logger.debug("WAF challenge solved, retrying with token")
                resp = cffi_requests.get(url, cookies={"aws-waf-token": token}, impersonate="chrome")
            except Exception as e:
                logger.warning(
                    "Failed to solve WAF challenge from 202 response: %s, "
                    "falling back to Chrome impersonation without token (may not succeed)...", e
                )
                resp = cffi_requests.get(url, cookies={}, impersonate="chrome")

        if resp.status_code != 200:
            logger.error("Error fetching %s: %s", url, resp.status_code)
            error_msg = f"Error fetching {url}: HTTP {resp.status_code}"
            if resp.text:
                error_msg += f" - {resp.text[:200]}"
            if resp.status_code == 202:
                error_msg += " AWS WAF Enforcement In Place. Try Again Later. ******"
            raise Exception(error_msg)

        tree = html.fromstring(resp.content or b"")
        script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
        if not script or type(script) is not list:
            logger.error("No script found with id '__NEXT_DATA__'")
            raise Exception("No script found with id '__NEXT_DATA__'")
        return json.loads(str(script[0]))

    def _make_graphql_request(self, headers, imdbId, payload, url) -> Any:
        resp = self.session.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.error("GraphQL request failed: %s", resp.status_code)
            error_msg = f"GraphQL request failed for {imdbId}: HTTP {resp.status_code}"
            if resp.text:
                error_msg += f" - {resp.text[:200]}"
            raise Exception(error_msg)
        data = resp.json()
        if "errors" in data:
            logger.error("GraphQL error: %s", data["errors"])
            raise Exception(f"GraphQL error for {imdbId}: {data['errors']}")
        return data

    @lru_cache(maxsize=128)
    def _get_extended_title_info(self, imdb_id) -> dict:
        """
        Fetch extended info (like AKAs) using IMDb's GraphQL API.
        """
        imdbId = "tt" + imdb_id
        url = "https://api.graphql.imdb.com/"
        headers = {
            "Content-Type": "application/json",
        }
        query = (
            """
            query {
              title(id: "%s") {
                id
                titleText {
                  text
                }
                originalTitle: originalTitleText {
                  text
                }
                  interests(first:20){
                    edges{node{primaryText{text}}}
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
                  displayableArticle {
                    body {
                      plaidHtml
                    }
                  }
                  interestScore {
                    usersVoted
                    usersInterested
                  }
                }
              }
            }
            reviews(first: 50) {
              edges {
                node {
                  id
                  spoiler
                  author {
                    nickName
                  }
                  summary {
                    originalText
                  }
                  text {
                    originalText {
                      plaidHtml
                    }
                  }
                  authorRating
                  submissionDate
                  helpfulness {
                    upVotes
                    downVotes
                  }
                  __typename
                }
              }
            }
              }
            }
            """
            % imdbId
        )
        payload = {"query": query}
        logger.info("Fetching title %s from GraphQL API", imdb_id)
        data = self._make_graphql_request(headers, imdbId, payload, url)
        raw_json = data.get("data", {}).get("title", {})
        return raw_json

    def _get_extended_name_info(self, person_id) -> dict:
        """
        Fetch extended person info using IMDb's GraphQL API.
        """
        person_id = "nm" + person_id

        query = (
            """
                query {
                  name(id: "%s") {
                    nameText {
                      text
                    }

                    credits(first: 250
                    filter: {
                categories: [
                  "production_designer"
                  "casting_department"
                  "director"
                  "composer"
                  "casting_director"
                  "executive"
                  "art_director"
                  "actress"
                  "costume_designer"
                  "writer"
                  "camera_department"
                  "art_department"
                  "publicist"
                  "cinematographer"
                  "location_management"
                  "soundtrack"
                  "sound_department"
                  "talent_agent"
                  "set_decorator"
                  "animation_department"
                  "make_up_department"
                  "costume_department"
                  "script_department"
                  "producer"
                  "stunts"
                  "editor"
                  "stunt_coordinator"
                  "special_effects"
                  "assistant_director"
                  "editorial_department"
                  "music_department"
                  "transportation_department"
                  "actor"
                  "visual_effects"
                  "production_manager"
                  "production_designer"
                  "casting_department"
                  "director"
                  "composer"
                  "archive_sound"
                  "casting_director"
                  "art_director"
                ]
              }
                    )

                    {
                      edges {
                        node {
                          category {
                            id
                          }

                          title {
                            id
                            ratingsSummary{aggregateRating}
                            primaryImage {
                              url
                            }
                            #certificate {rating}
                            originalTitleText {
                              text
                            }
                            titleText {
                              text
                            }
                            titleType {
                              #text
                              id
                            }
                            releaseYear {
                              year
                            }
                          }
                        }
                      }

                      pageInfo {
                        endCursor
                        hasNextPage
                      }
                    }
                  }
                }

            """
            % person_id
        )
        url = "https://api.graphql.imdb.com/"
        headers = {
            "Content-Type": "application/json",
        }
        payload = {"query": query}
        logger.info("Fetching person %s from GraphQL API", person_id)
        data = self._make_graphql_request(headers, person_id, payload, url)
        raw_json = data.get("data", {}).get("name", {})
        return raw_json

    @lru_cache(maxsize=128)
    def get_movie(self, imdb_id: str, locale: Optional[str] = None) -> Optional[MovieDetail]:
        """Fetch movie details from IMDb using the provided IMDb ID as string,
        preserve the 'tt' prefix or not, it will be stripped in the function.
        """
        imdb_id, lang = self._normalize_imdb_id(imdb_id, locale)
        url = f"https://www.imdb.com/{lang}/title/tt{imdb_id}/reference"
        logger.info("Fetching movie %s", imdb_id)
        raw_json = self._request_json_url(url)
        movie = parse_json_movie(raw_json)
        logger.debug("Fetched url %s", url)
        return movie

    @lru_cache(maxsize=128)
    def search_movie(
        self,
        title: str,
        locale: Optional[str] = None,
        title_type: Optional[TitleFilter] = None
    ) -> Optional[SearchResult]:
        """
        Search for a movie by title and return a list of titles and names.

        :param title: Title to search for.
        :param locale: Optional locale string (e.g., 'en', 'es').
        :param title_type: Optional filter(s) for media type. Must be a single TitleType enum member or a hashable tuple of TitleType members.
        """
        effective_locale = locale if locale is not None else self.locale
        lang_str = _retrieve_url_lang(effective_locale)
        lang = f"{lang_str}/" if lang_str else ""
        url = f"https://www.imdb.com/{lang}find?q={title}&s=tt"

        if not title_type:
            type_log = "All"
        else:
            if isinstance(title_type, tuple):
                types_list = title_type
            else:
                types_list = [title_type]

            ttype_values = [tt.value for tt in types_list]
            ttype_names = [tt.name for tt in types_list]

            ttype_value = ",".join(ttype_values)
            type_log = ", ".join(ttype_names)

            url += f"&ttype={ttype_value}"

        logger.info("Searching for title '%s' [Type: %s]", title, type_log)

        try:
            raw_json = self._request_json_url(url)
        except Exception as e:
            logger.warning("Search request failed: %s", e)
            return None

        result = parse_json_search(raw_json)
        logger.debug("Search for '%s' returned %s titles", title, len(result.titles))
        return result

    @lru_cache(maxsize=128)
    def get_name(self, person_id: str, locale: Optional[str] = None) -> Optional[PersonDetail]:
        """Fetch person details from IMDb using the provided IMDb ID.
        Preserve the 'nm' prefix or not, it will be stripped in the function.
        """
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
        """Fetch episodes for a movie or series using the provided IMDb ID."""
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
        """wrap until deprecation : use get_season_episodes instead for seasons
        or get_all_episodes for all episodes
        """
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

    def get_filmography(self, imdb_id) -> dict:
        """
        Fetch full filmography for a person using the provided IMDb ID.
        """
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw_json = self._get_extended_name_info(imdb_id)
        if not raw_json:
            logger.warning("No full_credit found for name %s", imdb_id)
            return {}
        full_credits_list = parse_json_filmography(raw_json)
        logger.debug("Fetched full_credits for name %s", imdb_id)
        return full_credits_list


_default_kit = IMDBKit()
sync_session = _default_kit.session


def normalize_imdb_id(imdb_id: str, locale: Optional[str] = None):
    return _default_kit._normalize_imdb_id(imdb_id, locale)

def get_cookies(text, user_agent=None):
    return _default_kit._get_waf_token(text)

def request_json_url(url: str) -> Any:
    return _default_kit._request_json_url(url)

def make_graphql_request(headers, imdbId, payload, url) -> Any:
    return _default_kit._make_graphql_request(headers, imdbId, payload, url)

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

def get_filmography(imdb_id) -> dict:
    return _default_kit.get_filmography(imdb_id)
