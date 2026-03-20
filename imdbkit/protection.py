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
import json
import logging
from curl_cffi import requests, CurlMime
from .challenge_solver import (
    CHALLENGE_TYPES,
    BANDWIDTH_CHALLENGE,
    build_everything,
)

logger = logging.getLogger(__name__)


class WafHandler:
    def __init__(
        self,
        goku_props: dict,
        endpoint: str,
        domain: str,
        session,
        user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        ),
    ):
        self.session = session
        self.session.headers = {
            "connection": "keep-alive",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "upgrade-insecure-requests": "1",
            "user-agent": user_agent,
        }
        self.goku_props = goku_props
        self.user_agent = user_agent
        self.domain = domain if "www" in domain else f"www.{domain}"
        self.endpoint = endpoint

        existing = self.session.cookies.get("aws-waf-token")
        self.existing_token = existing if existing else None

    @staticmethod
    def parse_challenge(html: str):
        goku_props = json.loads(
            html.split("window.gokuProps = ")[1].split(";")[0]
        )
        host = html.split('src="https://')[1].split("/challenge.js")[0]
        return goku_props, host

    def fetch_challenge_params(self):
        resp = self.session.get(
            f"https://{self.endpoint}/inputs?client=browser", timeout=10
        )
        return resp.json()

    def _build_metrics(self):
        return [
            {"name": "2",         "value": random.uniform(0, 1),      "unit": "2"},
            {"name": "100",       "value": 0,                          "unit": "2"},
            {"name": "101",       "value": 0,                          "unit": "2"},
            {"name": "102",       "value": 0,                          "unit": "2"},
            {"name": "103",       "value": 8,                          "unit": "2"},
            {"name": "104",       "value": 0,                          "unit": "2"},
            {"name": "105",       "value": 0,                          "unit": "2"},
            {"name": "106",       "value": 0,                          "unit": "2"},
            {"name": "107",       "value": 0,                          "unit": "2"},
            {"name": "108",       "value": 1,                          "unit": "2"},
            {"name": "undefined", "value": 0,                          "unit": "2"},
            {"name": "110",       "value": 0,                          "unit": "2"},
            {"name": "111",       "value": 2,                          "unit": "2"},
            {"name": "112",       "value": 0,                          "unit": "2"},
            {"name": "undefined", "value": 0,                          "unit": "2"},
            {"name": "3",         "value": 4,                          "unit": "2"},
            {"name": "7",         "value": 0,                          "unit": "4"},
            {"name": "1",         "value": random.uniform(5, 20),      "unit": "2"},
            {"name": "4",         "value": 36.5,                       "unit": "2"},
            {"name": "5",         "value": random.uniform(0, 1),       "unit": "2"},
            {"name": "6",         "value": random.uniform(100, 500),   "unit": "2"},
            {"name": "0",         "value": random.uniform(135, 500),   "unit": "2"},
            {"name": "8",         "value": 1,                          "unit": "4"},
        ]

    def construct_payload(self, inputs: dict):
        challenge_type = inputs["challenge_type"]
        solver = CHALLENGE_TYPES.get(challenge_type)

        if solver is None or not callable(solver):
            raise ValueError(f"Unsolvable challenge type: '{challenge_type}'.")

        payload_data = build_everything(user_agent=self.user_agent)
        is_bandwidth = challenge_type == BANDWIDTH_CHALLENGE

        if is_bandwidth:
            solution_b64 = solver("", "", inputs["difficulty"])
            return {
                "_is_bandwidth": True,
                "solution_data": solution_b64,
                "solution_metadata": {
                    "challenge": inputs["challenge"],
                    "solution": None,
                    "signals": [{"name": "Zoey", "value": {"Present": payload_data["encrypted"]}}],
                    "checksum": payload_data["checksum"],
                    "client": "Browser",
                    "domain": self.domain,
                    "metrics": self._build_metrics(),
                    "goku_props": self.goku_props,
                },
            }
        else:
            return {
                "_is_bandwidth": False,
                "challenge": inputs["challenge"],
                "checksum": payload_data["checksum"],
                "solution": solver(
                    inputs["challenge"]["input"], payload_data["checksum"], inputs["difficulty"]
                ),
                "signals": [{"name": "Zoey", "value": {"Present": payload_data["encrypted"]}}],
                "existing_token": self.existing_token,
                "client": "Browser",
                "domain": self.domain,
                "metrics": self._build_metrics(),
            }

    def submit_challenge(self, payload: dict) -> str:
        is_bandwidth = payload.pop("_is_bandwidth", False)

        if is_bandwidth:
            mp = CurlMime()
            mp.addpart(
                name="solution_data",
                data=payload["solution_data"].encode("utf-8"),
            )
            mp.addpart(
                name="solution_metadata",
                data=json.dumps(
                    payload["solution_metadata"], separators=(",", ":")
                ).encode("utf-8"),
            )
            resp = self.session.post(
                f"https://{self.endpoint}/mp_verify",
                headers=self.session.headers,
                multipart=mp,
                timeout=10,
            )
        else:
            resp = self.session.post(
                f"https://{self.endpoint}/verify",
                headers=self.session.headers,
                json=payload,
                timeout=10,
            )

        return resp.json()["token"]

    def __call__(self):
        inputs = self.fetch_challenge_params()
        logger.debug("Challenge type: %s", inputs.get("challenge_type"))
        payload = self.construct_payload(inputs)
        return self.submit_challenge(payload)
