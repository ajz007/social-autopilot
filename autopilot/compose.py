"""Turning a queued post into the exact text each platform receives."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import FB_MESSAGE_LIMIT, IG_CAPTION_LIMIT, IG_HASHTAG_LIMIT, Brand, Post


def tracked_link(brand: Brand, post: Post, platform: str) -> str | None:
    """Absolute link with UTM tags, placed before any #fragment so hash routes keep working."""
    if not post.link:
        return None
    link = post.link
    if not link.startswith(("http://", "https://")):
        link = brand.site_url + "/" + link.lstrip("/")
    parts = urlsplit(link)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith("utm_")]
    query += [
        ("utm_source", platform),
        ("utm_medium", "social"),
        ("utm_campaign", brand.utm_campaign),
        ("utm_content", post.id),
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), parts.fragment))


def hashtag_line(tags: list[str], limit: int) -> str:
    return " ".join("#" + t for t in tags[:limit])


def facebook_text(brand: Brand, post: Post) -> str:
    body = post.overrides.get("facebook", post.caption)
    pieces = [body]
    link = tracked_link(brand, post, "facebook")
    if link:
        pieces.append(link)
    tags = hashtag_line(post.hashtags, brand.facebook.max_hashtags)
    if tags:
        pieces.append(tags)
    return "\n\n".join(pieces)


def instagram_text(brand: Brand, post: Post) -> str:
    body = post.overrides.get("instagram", post.caption)
    pieces = [body]
    # Links in Instagram captions are not clickable, so point people to the bio instead.
    if post.link and brand.instagram.link_text:
        pieces.append(brand.instagram.link_text)
    tags = hashtag_line(post.hashtags, min(brand.instagram.max_hashtags, IG_HASHTAG_LIMIT))
    if tags:
        pieces.append(tags)
    return "\n\n".join(pieces)


def text_for(brand: Brand, post: Post, platform: str) -> str:
    return facebook_text(brand, post) if platform == "facebook" else instagram_text(brand, post)


def problems(brand: Brand, post: Post) -> list[str]:
    """Length and format checks that depend on the composed text."""
    issues = []
    if "instagram" in post.platforms:
        text = instagram_text(brand, post)
        if len(text) > IG_CAPTION_LIMIT:
            issues.append(f"{post.id}: Instagram caption is {len(text)} characters (limit {IG_CAPTION_LIMIT})")
        if text.count("#") > IG_HASHTAG_LIMIT:
            issues.append(f"{post.id}: Instagram allows at most {IG_HASHTAG_LIMIT} hashtags")
    if "facebook" in post.platforms:
        text = facebook_text(brand, post)
        if len(text) > FB_MESSAGE_LIMIT:
            issues.append(f"{post.id}: Facebook message is too long")
    return issues
