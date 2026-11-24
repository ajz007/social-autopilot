"""Choosing today's post, publishing it, and recording what happened."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from . import compose
from .config import Brand, Post, media_url
from .graph import Graph, GraphError, check_public_url
from .publishers import Result, publish_facebook, publish_instagram

MAX_ATTEMPTS = 3


class State:
    """Per-brand publishing history, stored as JSON and committed back by the workflow."""

    def __init__(self, path: Path):
        self.path = path
        self.data = {"posts": {}}
        if path.is_file():
            self.data = json.loads(path.read_text(encoding="utf-8"))
            self.data.setdefault("posts", {})

    def record(self, post_id: str, platform: str) -> dict:
        return self.data["posts"].get(post_id, {}).get(platform, {})

    def done(self, post_id: str, platform: str) -> bool:
        return bool(self.record(post_id, platform).get("id"))

    def settled(self, post_id: str, platform: str) -> bool:
        rec = self.record(post_id, platform)
        return bool(rec.get("id")) or rec.get("attempts", 0) >= MAX_ATTEMPTS

    def started(self, post_id: str) -> bool:
        return bool(self.data["posts"].get(post_id))

    def mark_success(self, post_id: str, result: Result, at: datetime) -> None:
        rec = self.data["posts"].setdefault(post_id, {}).setdefault(result.platform, {})
        rec.update({"id": result.remote_id, "permalink": result.permalink, "at": at.isoformat(timespec="seconds")})
        rec.pop("error", None)

    def mark_failure(self, post_id: str, platform: str, error: str, at: datetime) -> None:
        rec = self.data["posts"].setdefault(post_id, {}).setdefault(platform, {})
        rec["attempts"] = rec.get("attempts", 0) + 1
        rec["error"] = error
        rec["last_attempt"] = at.isoformat(timespec="seconds")

    def published_on(self, day: date, tz: ZoneInfo) -> bool:
        for platforms in self.data["posts"].values():
            for rec in platforms.values():
                if rec.get("id") and rec.get("at"):
                    if datetime.fromisoformat(rec["at"]).astimezone(tz).date() == day:
                        return True
        return False

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pending_platforms(post: Post, state: State, only: str | None = None) -> list[str]:
    return [p for p in post.platforms if (only is None or p == only) and not state.settled(post.id, p)]


def choose(posts: list[Post], state: State, today: date, tz: ZoneInfo) -> tuple[Post | None, str]:
    """Return the post to publish now and a reason when there is none."""
    # Finish a post that went out on one platform but not the other before starting a new one.
    for post in posts:
        if state.started(post.id) and pending_platforms(post, state):
            return post, "retrying unfinished post"
    if state.published_on(today, tz):
        return None, "a post already went out today"
    waiting = []
    for post in posts:
        if state.started(post.id):
            continue
        if post.not_before and post.not_before > today:
            waiting.append(post)
            continue
        return post, "next in queue"
    if waiting:
        soonest = min(waiting, key=lambda p: p.not_before)
        return None, f"nothing due yet, {soonest.id} is scheduled for {soonest.not_before}"
    return None, "the queue is empty"


def remaining(posts: list[Post], state: State) -> int:
    return sum(1 for p in posts if not state.started(p.id))


@dataclass
class Outcome:
    post: Post | None
    reason: str
    results: list[Result] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    previews: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def run(
    brand: Brand,
    posts: list[Post],
    state: State,
    *,
    live: bool,
    post_id: str | None = None,
    platform: str | None = None,
    now: datetime | None = None,
    graph_factory: Callable[[str, str], Graph] = Graph,
    url_checker: Callable[[str], str | None] = check_public_url,
) -> Outcome:
    tz = ZoneInfo(brand.timezone)
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(tz).date()

    if post_id:
        match = [p for p in posts if p.id == post_id]
        if not match:
            return Outcome(None, f"no post with id '{post_id}'", errors={"queue": "unknown post id"})
        post, reason = match[0], "requested by id"
    else:
        post, reason = choose(posts, state, today, tz)
    if post is None:
        return Outcome(None, reason)

    targets = pending_platforms(post, state, platform)
    outcome = Outcome(post, reason)
    if not targets:
        outcome.reason = "already published on the requested platforms"
        return outcome

    urls = [media_url(brand, m) for m in post.media]
    for p in targets:
        outcome.previews[p] = compose.text_for(brand, post, p)
    if not live:
        return outcome

    # Check media before touching either platform, so a missing image never leaves
    # a post published on one platform only. This does not count as an attempt.
    unreachable = [msg for msg in map(url_checker, urls) if msg]
    if unreachable:
        outcome.errors["media"] = "; ".join(unreachable)
        return outcome

    graph = graph_factory(brand.secret("page_token"), brand.graph_api_version)
    for p in targets:
        try:
            if p == "facebook":
                result = publish_facebook(graph, brand.secret("page_id"), outcome.previews[p], urls, post.is_video)
            else:
                result = publish_instagram(graph, brand.secret("ig_user_id"), outcome.previews[p], urls, post.is_video)
        except (GraphError, KeyError) as exc:
            msg = str(exc) if isinstance(exc, GraphError) else f"unexpected response, missing {exc}"
            outcome.errors[p] = msg
            state.mark_failure(post.id, p, msg, now)
        else:
            outcome.results.append(result)
            state.mark_success(post.id, result, now)
        state.save()  # Save after each platform so a crash never loses a published post.
    return outcome


def paused() -> bool:
    return os.environ.get("AUTOPILOT_PAUSED", "").lower() in ("1", "true", "yes")
