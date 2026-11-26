"""Loading and validating a brand's settings and its post queue."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import yaml

PLATFORMS = ("facebook", "instagram")
VIDEO_EXTENSIONS = (".mp4", ".mov")
IMAGE_EXTENSIONS = (".jpg", ".jpeg")  # Instagram publishing accepts JPEG only.
POST_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}$")

IG_CAPTION_LIMIT = 2200
IG_HASHTAG_LIMIT = 30
FB_MESSAGE_LIMIT = 60000


class ConfigError(Exception):
    """Raised when a brand file or post queue is invalid."""


@dataclass
class PlatformSettings:
    max_hashtags: int
    link_text: str = ""


@dataclass
class Brand:
    slug: str
    root: Path
    name: str
    site_url: str
    timezone: str
    image_base_url: str
    platforms: list[str]
    graph_api_version: str
    env: dict[str, str]
    utm_campaign: str
    facebook: PlatformSettings
    instagram: PlatformSettings
    card_style: dict[str, str] = field(default_factory=dict)

    def secret(self, key: str) -> str:
        """Read a credential from the environment variable named in brand.yaml."""
        var = self.env.get(key)
        if not var:
            raise ConfigError(f"brand.yaml has no env.{key} entry")
        value = os.environ.get(var, "").strip()
        if not value:
            raise ConfigError(f"environment variable {var} ({key}) is not set")
        return value


@dataclass
class Post:
    id: str
    caption: str
    hashtags: list[str] = field(default_factory=list)
    link: str | None = None
    media: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    not_before: date | None = None
    overrides: dict[str, str] = field(default_factory=dict)  # platform -> caption
    card: dict[str, Any] | None = None

    @property
    def is_video(self) -> bool:
        return any(m.lower().endswith(VIDEO_EXTENSIONS) for m in self.media)


def load_brand(brands_dir: Path, slug: str) -> Brand:
    root = brands_dir / slug
    path = root / "brand.yaml"
    if not path.is_file():
        raise ConfigError(f"no brand found at {path}")
    raw = _read_yaml(path)
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must be a mapping")

    def need(key: str) -> Any:
        if key not in raw or raw[key] in (None, ""):
            raise ConfigError(f"{path}: missing '{key}'")
        return raw[key]

    platforms = raw.get("platforms") or list(PLATFORMS)
    for p in platforms:
        if p not in PLATFORMS:
            raise ConfigError(f"{path}: unknown platform '{p}'")

    fb = raw.get("facebook") or {}
    ig = raw.get("instagram") or {}
    image_base = str(raw.get("image_base_url") or "")
    if image_base and not image_base.endswith("/"):
        image_base += "/"

    return Brand(
        slug=slug,
        root=root,
        name=str(need("name")),
        site_url=str(need("site_url")).rstrip("/"),
        timezone=str(raw.get("timezone") or "UTC"),
        image_base_url=image_base,
        platforms=list(platforms),
        graph_api_version=str(raw.get("graph_api_version") or "v27.0"),
        env=dict(need("env")),
        utm_campaign=str(raw.get("utm_campaign") or "social-autopilot"),
        facebook=PlatformSettings(max_hashtags=int(fb.get("max_hashtags", 3))),
        instagram=PlatformSettings(
            max_hashtags=int(ig.get("max_hashtags", 15)),
            link_text=str(ig.get("link_text", "Link in bio.")),
        ),
        card_style={k: str(v) for k, v in (raw.get("card_style") or {}).items()},
    )


def load_posts(brand: Brand) -> list[Post]:
    path = brand.root / "posts.yaml"
    raw = _read_yaml(path)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ConfigError(f"{path} must be a list of posts")

    posts: list[Post] = []
    seen: set[str] = set()
    errors: list[str] = []
    for i, item in enumerate(raw, start=1):
        try:
            post = _parse_post(item, brand)
        except ConfigError as exc:
            errors.append(f"post #{i}: {exc}")
            continue
        if post.id in seen:
            errors.append(f"post #{i}: duplicate id '{post.id}'")
        seen.add(post.id)
        posts.append(post)
    if errors:
        raise ConfigError("invalid posts.yaml:\n  " + "\n  ".join(errors))
    return posts


def _parse_post(item: Any, brand: Brand) -> Post:
    if not isinstance(item, dict):
        raise ConfigError("each post must be a mapping")
    pid = str(item.get("id") or "")
    if not POST_ID.match(pid):
        raise ConfigError(f"id '{pid}' must be lowercase letters, digits and dashes")
    caption = str(item.get("caption") or "").strip()
    if not caption:
        raise ConfigError(f"{pid}: caption is required")

    platforms = item.get("platforms") or brand.platforms
    for p in platforms:
        if p not in PLATFORMS:
            raise ConfigError(f"{pid}: unknown platform '{p}'")

    media = item.get("media") or []
    if isinstance(media, str):
        media = [media]
    media = [str(m) for m in media]
    if len(media) > 10:
        raise ConfigError(f"{pid}: at most 10 media items")
    videos = [m for m in media if m.lower().endswith(VIDEO_EXTENSIONS)]
    if videos and len(media) > 1:
        raise ConfigError(f"{pid}: a video post must have exactly one media item")
    for m in media:
        if not m.lower().endswith(VIDEO_EXTENSIONS + IMAGE_EXTENSIONS):
            raise ConfigError(f"{pid}: {m} must be .jpg/.jpeg (Instagram accepts JPEG only) or .mp4/.mov")
    if "instagram" in platforms and not media:
        raise ConfigError(f"{pid}: Instagram posts need at least one image or video")

    hashtags = [str(h).lstrip("#").strip() for h in (item.get("hashtags") or [])]
    if any(not h or " " in h for h in hashtags):
        raise ConfigError(f"{pid}: hashtags must be single words")

    not_before = item.get("not_before")
    if not_before is not None and not isinstance(not_before, date):
        raise ConfigError(f"{pid}: not_before must be a date like 2026-12-01")

    overrides = {}
    for p in PLATFORMS:
        block = item.get(p)
        if isinstance(block, dict) and block.get("caption"):
            overrides[p] = str(block["caption"]).strip()

    card = item.get("card")
    if card is not None and not isinstance(card, dict):
        raise ConfigError(f"{pid}: card must be a mapping")

    return Post(
        id=pid,
        caption=caption,
        hashtags=hashtags,
        link=str(item["link"]) if item.get("link") else None,
        media=media,
        platforms=list(platforms),
        not_before=not_before,
        overrides=overrides,
        card=card,
    )


def media_url(brand: Brand, item: str) -> str:
    """Resolve a media entry to the public URL Meta's servers will download."""
    if item.startswith(("http://", "https://")):
        return item
    if not brand.image_base_url:
        raise ConfigError(f"'{item}' is a relative path but brand.yaml has no image_base_url")
    return urljoin(brand.image_base_url, item.lstrip("/"))


def _read_yaml(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError:
        raise ConfigError(f"{path} not found") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: {exc}") from None
