"""Publishing one post to a Facebook Page or an Instagram professional account."""

from __future__ import annotations

from dataclasses import dataclass

from .graph import Graph, GraphError


@dataclass
class Result:
    platform: str
    remote_id: str
    permalink: str | None = None


def publish_facebook(graph: Graph, page_id: str, text: str, media_urls: list[str], is_video: bool) -> Result:
    if is_video:
        resp = graph.post(f"{page_id}/videos", file_url=media_urls[0], description=text)
        rid = resp["id"]
    elif len(media_urls) == 1:
        resp = graph.post(f"{page_id}/photos", url=media_urls[0], message=text)
        rid = resp.get("post_id") or resp["id"]
    elif media_urls:
        # Multi-photo post: upload each photo unpublished, then attach them all to one feed post.
        attached = {}
        for i, url in enumerate(media_urls):
            photo = graph.post(f"{page_id}/photos", url=url, published=False)
            attached[f"attached_media[{i}]"] = {"media_fbid": photo["id"]}
        resp = graph.post(f"{page_id}/feed", message=text, **attached)
        rid = resp["id"]
    else:
        resp = graph.post(f"{page_id}/feed", message=text)
        rid = resp["id"]
    return Result("facebook", rid, _facebook_permalink(graph, rid))


def _facebook_permalink(graph: Graph, rid: str) -> str | None:
    try:
        return graph.get(rid, fields="permalink_url", retries=1).get("permalink_url")
    except GraphError:
        return None  # The post exists; a missing permalink is cosmetic.


def publish_instagram(graph: Graph, ig_user_id: str, caption: str, media_urls: list[str], is_video: bool) -> Result:
    if is_video:
        container = graph.post(f"{ig_user_id}/media", media_type="REELS", video_url=media_urls[0], caption=caption)["id"]
        wait_until_ready(graph, container, timeout=600)
    elif len(media_urls) == 1:
        container = graph.post(f"{ig_user_id}/media", image_url=media_urls[0], caption=caption)["id"]
        wait_until_ready(graph, container, timeout=120)
    else:
        children = []
        for url in media_urls:
            child = graph.post(f"{ig_user_id}/media", image_url=url, is_carousel_item=True)["id"]
            wait_until_ready(graph, child, timeout=120)
            children.append(child)
        container = graph.post(
            f"{ig_user_id}/media", media_type="CAROUSEL", children=",".join(children), caption=caption
        )["id"]
        wait_until_ready(graph, container, timeout=120)

    media_id = graph.post(f"{ig_user_id}/media_publish", creation_id=container)["id"]
    permalink = None
    try:
        permalink = graph.get(media_id, fields="permalink", retries=1).get("permalink")
    except GraphError:
        pass
    return Result("instagram", media_id, permalink)


def wait_until_ready(graph: Graph, container_id: str, timeout: int, interval: int = 5) -> None:
    waited = 0
    while True:
        status = graph.get(container_id, fields="status_code,status").get("status_code")
        if status in ("FINISHED", "PUBLISHED"):
            return
        if status in ("ERROR", "EXPIRED"):
            detail = graph.get(container_id, fields="status").get("status", "")
            raise GraphError(f"Instagram could not process the media ({status}): {detail}")
        if waited >= timeout:
            raise GraphError(f"Instagram media was still processing after {timeout}s")
        graph.sleep(interval)
        waited += interval
