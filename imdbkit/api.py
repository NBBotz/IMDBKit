import random
import re
from typing import Optional, Dict, Union, List, Tuple, Any
from functools import lru_cache
from time import time
import logging
import json
from lxml import html
from enum import Enum

from curl_cffi import Session as SyncSession  # single import — direct, explicit, no shim

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


class TitleType(Enum):
    Movies   = "ft"
    Series   = "tv"
    Episodes = "ep"
    Shorts   = "sh"
    TvMovie  = "tvm"
    Video    = "v"


TitleFilter = Union[TitleType, Tuple[TitleType, ...]]

logger = logging.getLogger(__name__)

USER_AGENTS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

# Global WAF state flag.
# True  -> Chrome impersonation + WAF token on every request (safe mode)
# False -> plain request, no overhead (fast mode, used after a clean run)
# Automatically flips back to True if a 202/403 is encountered again.
WAF_DETECTED = True


class IMDBKit:
    def __init__(self, locale: Optional[str] = None):
        self.locale = locale
        self.session = SyncSession(impersonate="chrome")
        self._reset_browse_headers()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reset_browse_headers(self):
        """Restore standard browser navigation headers on the shared session.
        Called after WafHandler overwrites headers with its own CORS-style ones."""
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

    def _solve_waf(self, html_text: str, user_agent: str) -> dict:
        """
        Solve the AWS WAF challenge using a FRESH dedicated session.
        Isolated from self.session so no conflicting headers/cookies interfere.
        Mirrors imdbinfo exactly:
            session = cffi_requests.Session(impersonate="chrome")
            token = AwsWaf(tk, host, "www.imdb.com", session)()
        """
        try:
            tk, host = WafHandler.parse_challenge(html_text)
            solve_session = SyncSession(impersonate="chrome")
            token = WafHandler(
                tk, host, "www.imdb.com", session=solve_session, user_agent=user_agent
            )()
            # Merge ALL cookies from solve session (not just the token)
            # AWS WAF may set additional session-binding cookies during /inputs and /verify
            all_cookies = dict(solve_session.cookies)
            all_cookies["aws-waf-token"] = token
            # Also store on main session for future requests
            for name, value in all_cookies.items():
                self.session.cookies.set(name, value, domain=".imdb.com")
            logger.debug("WAF token obtained: %s... (total cookies: %d)", token[:20], len(all_cookies))
            return all_cookies
        except Exception as e:
            logger.warning("WAF challenge solve failed: %s", e)
            import traceback
            logger.debug("WAF solve traceback: %s", traceback.format_exc())
            return {}

    def _safe_request(self, method: str, url: str, **kwargs) -> Any:
        global WAF_DETECTED
        from curl_cffi import requests as cffi_requests
        user_agent = random.choice(USER_AGENTS_LIST)
        self.session.headers["user-agent"] = user_agent
        logger.debug("Using User-Agent: %s", user_agent)

        if method.upper() == "GET":
            resp = self.session.get(url, **kwargs)
        else:
            resp = self.session.post(url, **kwargs)

        waf_hit = (
            resp.status_code in [202, 403]
            or (resp.status_code == 200 and "window.gokuProps" in resp.text)
        )

        retried = False
        if waf_hit:
            WAF_DETECTED = True
            logger.warning(
                "HTTP %s -- WAF challenge detected. Solving from response body...",
                resp.status_code,
            )
            cookies = self._solve_waf(resp.text, user_agent)
            logger.info("WAF solved. Retrying as standalone request with explicit cookie...")
            # Retry as a BARE standalone cffi request -- NOT self.session.get()
            # Mirrors imdbinfo:
            #   resp = cffi_requests.get(url, cookies={'aws-waf-token': token}, impersonate="chrome")
            try:
                if method.upper() == "GET":
                    resp = cffi_requests.get(url, cookies=cookies, impersonate="chrome")
                else:
                    post_kwargs = {k: v for k, v in kwargs.items() if k != "cookies"}
                    resp = cffi_requests.post(url, cookies=cookies, impersonate="chrome", **post_kwargs)
            except Exception as e:
                logger.warning("Standalone retry failed: %s -- falling back to session", e)
                retry_kwargs = dict(kwargs)
                retry_kwargs["cookies"] = cookies
                if method.upper() == "GET":
                    resp = self.session.get(url, **retry_kwargs)
                else:
                    resp = self.session.post(url, **retry_kwargs)
            retried = True
        else:
            if WAF_DETECTED:
                logger.debug("Clean response -- disabling WAF overhead.")
            WAF_DETECTED = False

        if resp.status_code != 200:
            logger.error("Request failed: %s %s", url, resp.status_code)
            msg = f"Request failed for {url}: HTTP {resp.status_code} [{user_agent}]"
            if retried:
                msg += " (after WAF retry)"
            if resp.text:
                msg += f" -- {resp.text[:200]}"
            raise Exception(msg)

        return resp

    def _request_json_url(self, url: str) -> Any:
        resp = self._safe_request("GET", url)
        tree = html.fromstring(resp.content or b"")
        script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
        if not script or not isinstance(script, list):
            raise Exception("No script found with id '__NEXT_DATA__'")
        return json.loads(str(script[0]))

    def _make_graphql_request(self, headers, imdbId, payload, url) -> Any:
        resp = self._safe_request("POST", url, headers=headers, json=payload)
        data = resp.json()
        if "errors" in data:
            raise Exception(f"GraphQL error for {imdbId}: {data['errors']}")
        return data

    # ------------------------------------------------------------------
    # Extended info (GraphQL)
    # ------------------------------------------------------------------

    @lru_cache(maxsize=128)
    def _get_extended_title_info(self, imdb_id: str) -> dict:
        imdbId = "tt" + imdb_id
        url = "https://api.graphql.imdb.com/"
        headers = {"Content-Type": "application/json"}
        query = """
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
                      country { name: text  code: id }
                      language { name: text  code: id }
                      title: text
                    }
                  }
                }
                trivia(first: 50) {
                  edges {
                    node {
                      id
                      displayableArticle { body { plaidHtml } }
                      interestScore { usersVoted  usersInterested }
                    }
                  }
                }
                reviews(first: 50) {
                  edges {
                    node {
                      id  spoiler
                      author { nickName }
                      summary { originalText }
                      text { originalText { plaidHtml } }
                      authorRating  submissionDate
                      helpfulness { upVotes  downVotes }
                      __typename
                    }
                  }
                }
                parentsGuide {
                  categories {
                    category { id  text }
                    guideItems(first: 10) {
                      edges { node { isSpoiler  text { plaidHtml } } }
                    }
                    severity { id  votedFor }
                    severityBreakdown { votedFor  voteType }
                  }
                }
              }
            }
        """ % imdbId
        data = self._make_graphql_request(headers, imdbId, {"query": query}, url)
        return data.get("data", {}).get("title", {})

    def _get_extended_name_info(self, person_id: str) -> dict:
        nm_id = "nm" + person_id
        query = """
            query {
              name(id: "%s") {
                nameText { text }
                credits(first: 250 filter: {
                  categories: [
                    "actor" "actress" "director" "writer" "producer"
                    "composer" "cinematographer" "editor" "casting_director"
                    "casting_department" "production_designer" "art_director"
                    "set_decorator" "costume_designer" "make_up_department"
                    "sound_department" "visual_effects" "stunt_coordinator"
                    "stunts" "executive" "animation_department"
                    "music_department" "transportation_department"
                    "editorial_department" "assistant_director"
                    "special_effects" "production_manager" "location_management"
                    "camera_department" "art_department" "costume_department"
                    "script_department" "publicist" "talent_agent" "soundtrack"
                    "archive_sound"
                  ]
                }) {
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
                  pageInfo { endCursor  hasNextPage }
                }
              }
            }
        """ % nm_id
        url = "https://api.graphql.imdb.com/"
        headers = {"Content-Type": "application/json"}
        data = self._make_graphql_request(headers, nm_id, {"query": query}, url)
        return data.get("data", {}).get("name", {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @lru_cache(maxsize=128)
    def get_movie(self, imdb_id: str, locale: Optional[str] = None) -> Optional[MovieDetail]:
        imdb_id, lang = self._normalize_imdb_id(imdb_id, locale)
        url = f"https://www.imdb.com/{lang}/title/tt{imdb_id}/reference"
        logger.info("Fetching movie %s", imdb_id)
        return parse_json_movie(self._request_json_url(url))

    @lru_cache(maxsize=128)
    def search_movie(
        self,
        title: str,
        locale: Optional[str] = None,
        title_type: Optional[TitleFilter] = None,
    ) -> Optional[SearchResult]:
        effective_locale = locale if locale is not None else self.locale
        lang_str = _retrieve_url_lang(effective_locale)
        lang = f"{lang_str}/" if lang_str else ""
        url = f"https://www.imdb.com/{lang}find?q={title}&s=tt"

        if title_type:
            types_list = title_type if isinstance(title_type, tuple) else [title_type]
            url += "&ttype=" + ",".join(tt.value for tt in types_list)

        try:
            resp = self._safe_request("GET", url)
        except Exception as e:
            logger.warning("Search request failed: %s", e)
            return None

        tree = html.fromstring(resp.content or b"")
        script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
        if not script or not isinstance(script, list):
            raise Exception("No script found with id '__NEXT_DATA__'")
        return parse_json_search(json.loads(str(script[0])))

    @lru_cache(maxsize=128)
    def get_name(self, person_id: str, locale: Optional[str] = None) -> Optional[PersonDetail]:
        person_id, lang = self._normalize_imdb_id(person_id, locale)
        url = f"https://www.imdb.com/{lang}/name/nm{person_id}/"
        logger.info("Fetching person %s", person_id)
        return parse_json_person_detail(self._request_json_url(url))

    @lru_cache(maxsize=128)
    def get_season_episodes(
        self, imdb_id: str, season: int = 1, locale: Optional[str] = None
    ) -> SeasonEpisodesList:
        imdb_id, lang = self._normalize_imdb_id(imdb_id, locale)
        url = f"https://www.imdb.com/{lang}/title/tt{imdb_id}/episodes/?season={season}"
        logger.info("Fetching episodes for %s season %s", imdb_id, season)
        return parse_json_season_episodes(self._request_json_url(url))

    @lru_cache(maxsize=128)
    def get_all_episodes(self, imdb_id: str, locale: Optional[str] = None):
        series_id, lang = self._normalize_imdb_id(imdb_id, locale)
        url = f"https://www.imdb.com/{lang}/search/title/?count=250&series=tt{series_id}&sort=release_date,asc"
        logger.info("Fetching all episodes for series %s", imdb_id)
        return parse_json_bulked_episodes(self._request_json_url(url))

    @lru_cache(maxsize=128)
    def get_episodes(
        self, imdb_id: str, season: int = 1, locale: Optional[str] = None
    ) -> SeasonEpisodesList:
        logger.warning("get_episodes is deprecated, use get_season_episodes or get_all_episodes.")
        return self.get_season_episodes(imdb_id, season, locale)

    def get_akas(self, imdb_id: str) -> Union[AkasData, list]:
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw = self._get_extended_title_info(imdb_id)
        return parse_json_akas(raw) if raw else []

    def get_all_interests(self, imdb_id: str):
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw = self._get_extended_title_info(imdb_id)
        if not raw:
            return []
        return [
            edge["node"]["primaryText"]["text"]
            for edge in raw.get("interests", {}).get("edges", [])
            if edge["node"].get("primaryText", {}).get("text")
        ]

    def get_trivia(self, imdb_id: str) -> List[Dict]:
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw = self._get_extended_title_info(imdb_id)
        return parse_json_trivia(raw) if raw else []

    def get_reviews(self, imdb_id: str) -> List[Dict]:
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw = self._get_extended_title_info(imdb_id)
        return parse_json_reviews(raw) if raw else []

    def get_parental_guide(self, imdb_id: str) -> Dict:
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw = self._get_extended_title_info(imdb_id)
        from .data_parsing import parse_json_parental_guide
        return parse_json_parental_guide(raw) if raw else {}

    def get_filmography(self, imdb_id: str) -> dict:
        imdb_id, _ = self._normalize_imdb_id(imdb_id)
        raw = self._get_extended_name_info(imdb_id)
        return parse_json_filmography(raw) if raw else {}


# ---------------------------------------------------------------------------
# Module-level default instance + backward-compatible free functions
# ---------------------------------------------------------------------------

_default_kit = IMDBKit()


def normalize_imdb_id(imdb_id: str, locale: Optional[str] = None):
    return _default_kit._normalize_imdb_id(imdb_id, locale)

def get_cookies(text: str, user_agent: Optional[str] = None) -> dict:
    return _default_kit._get_cookies(text, user_agent)

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
    imdb_id: str, season: int = 1, locale: Optional[str] = None
) -> SeasonEpisodesList:
    return _default_kit.get_season_episodes(imdb_id, season, locale)

def get_all_episodes(imdb_id: str, locale: Optional[str] = None):
    return _default_kit.get_all_episodes(imdb_id, locale)

def get_episodes(
    imdb_id: str, season: int = 1, locale: Optional[str] = None
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

def get_filmography(imdb_id: str) -> dict:
    return _default_kit.get_filmography(imdb_id)
