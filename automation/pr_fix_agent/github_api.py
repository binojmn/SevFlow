from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from requests import HTTPError


@dataclass
class PullRequestContext:
    number: int
    title: str
    body: str
    base_ref: str
    head_ref: str
    head_sha: str
    author: str
    files: list[dict[str, Any]]
    html_url: str


class GitHubClient:
    def __init__(self, token: str, repository: str, api_url: str = "https://api.github.com") -> None:
        self.repository = repository
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        response = self.session.request(method, f"{self.api_url}{path}", timeout=30, **kwargs)
        try:
            response.raise_for_status()
        except HTTPError as exc:
            details = response.text.strip()
            if details:
                raise HTTPError(
                    f"{exc} | GitHub response: {details}",
                    response=response,
                    request=exc.request,
                ) from exc
            raise
        return response

    def get_pull_request(self, number: int) -> PullRequestContext:
        pr = self._request("GET", f"/repos/{self.repository}/pulls/{number}").json()
        files = self._request("GET", f"/repos/{self.repository}/pulls/{number}/files?per_page=100").json()
        return PullRequestContext(
            number=pr["number"],
            title=pr["title"],
            body=pr.get("body") or "",
            base_ref=pr["base"]["ref"],
            head_ref=pr["head"]["ref"],
            head_sha=pr["head"]["sha"],
            author=pr["user"]["login"],
            files=files,
            html_url=pr["html_url"],
        )

    def create_pull_request(self, title: str, body: str, head: str, base: str) -> dict[str, Any]:
        payload = {"title": title, "body": body, "head": head, "base": base}
        return self._request("POST", f"/repos/{self.repository}/pulls", json=payload).json()
