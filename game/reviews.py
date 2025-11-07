"""Utilities to create review files in a GitHub repository via the Contents API.

Environment variables required:
  GITHUB_TOKEN  - Personal access token with repo:write scope (classic) or contents:write (fine-grained)
  GITHUB_REPO   - Target repository in the form owner/repo (defaults to current origin if unset -> raises)
  GITHUB_REVIEWS_PATH - Optional subfolder path inside repo (default: "reviews")

Each call to submit_review() creates a new text file named:
  {timestamp_iso}_{uuid}_{rating}of5.txt
with contents including rating, optional text, and metadata.

NOTE: This module performs direct network I/O. Failures raise ReviewError.
"""

from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
import json
import urllib.request
import urllib.error


class ReviewError(Exception):
    pass


@dataclass
class ReviewResult:
    path: str
    sha: Optional[str]
    url: Optional[str]


def _github_request(method: str, url: str, token: str, data: dict) -> dict:
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        raise ReviewError(f"GitHub API HTTPError {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise ReviewError(f"GitHub API connection failed: {e}")


def submit_review(rating: int, text: str | None = None) -> ReviewResult:
    if rating < 1 or rating > 5:
        raise ReviewError("Rating must be between 1 and 5")
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ReviewError("Missing GITHUB_TOKEN environment variable")
    repo = os.getenv("GITHUB_REPO")
    if not repo or "/" not in repo:
        raise ReviewError("GITHUB_REPO must be set as owner/repo")
    subdir = os.getenv("GITHUB_REVIEWS_PATH", "reviews").strip("/")
    # Compose file name
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    uid = uuid.uuid4().hex[:8]
    fname = f"{ts}_{uid}_{rating}of5.txt"
    rel_path = f"{subdir}/{fname}" if subdir else fname
    lines = [
        f"Rating: {rating}/5",
        f"Timestamp: {ts}",
    ]
    if text and text.strip():
        lines.append("")
        lines.append(text.strip())
    content_str = "\n".join(lines) + "\n"
    b64 = base64.b64encode(content_str.encode("utf-8")).decode("ascii")
    api_url = f"https://api.github.com/repos/{repo}/contents/{rel_path}"
    commit_msg = f"Add review {uid} rating {rating}/5"
    body = {
        "message": commit_msg,
        "content": b64,
    }
    branch = os.getenv("GITHUB_REVIEWS_BRANCH")
    if branch:
        body["branch"] = branch
    data = _github_request("PUT", api_url, token, body)
    content = data.get("content") if isinstance(data, dict) else None
    return ReviewResult(
        path=rel_path,
        sha=(content or {}).get("sha"),
        url=(content or {}).get("html_url"),
    )
