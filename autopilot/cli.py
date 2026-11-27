"""Command line entry point: python -m autopilot <command> --brand <slug>."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import compose, render, runner
from .config import ConfigError, load_brand, load_posts, media_url
from .graph import Graph, GraphError, check_public_url

REPO = Path(__file__).resolve().parent.parent
LOW_QUEUE_WARNING = 7


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autopilot", description=__doc__)
    parser.add_argument("--brands-dir", type=Path, default=REPO / "brands")
    parser.add_argument("--state-dir", type=Path, default=REPO / "state")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help)
        p.add_argument("--brand", required=True, help="folder name under brands/")
        return p

    v = add("validate", "check brand.yaml and posts.yaml")
    v.add_argument("--check-urls", action="store_true", help="also confirm every media URL is publicly reachable")
    add("status", "show the queue and how many days of posts are left")
    n = add("next", "preview the next post exactly as each platform will receive it")
    n.add_argument("--post-id")
    p = add("post", "publish the next post (a dry run unless --live)")
    p.add_argument("--live", action="store_true", help="actually publish")
    p.add_argument("--post-id", help="publish this post instead of the next one")
    p.add_argument("--platform", choices=["facebook", "instagram"])
    add("check", "verify the access token, Page and Instagram account")
    sub.add_parser("setup-token", help="turn a short-lived user token into a never-expiring Page token")
    pr = add("prepare", "render images for the next few unpublished posts (the weekly review batch)")
    pr.add_argument("--days", type=int, default=7)
    pr.add_argument("--force", action="store_true", help="re-render images that already exist")
    pr.add_argument("--manifest", type=Path, default=REPO / "build" / "prepared.json")
    pv = add("preview", "write a Markdown preview of the prepared posts, for the review pull request")
    pv.add_argument("--manifest", type=Path, default=REPO / "build" / "prepared.json")
    pv.add_argument("--ref", required=True, help="commit SHA or branch the images are pushed to")
    pv.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="owner/name on GitHub")
    r = add("render", "render card images for posts that define a card")
    r.add_argument("--post-id")
    r.add_argument("--force", action="store_true", help="re-render cards that already exist")

    args = parser.parse_args(argv)
    if args.command == "setup-token":
        return cmd_setup_token()
    try:
        brand = load_brand(args.brands_dir, args.brand)
        posts = load_posts(brand)
        state = runner.State(args.state_dir / f"{brand.slug}.json")
        return COMMANDS[args.command](args, brand, posts, state)
    except (ConfigError, render.RenderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def cmd_validate(args, brand, posts, state) -> int:
    issues = [msg for post in posts for msg in compose.problems(brand, post)]
    for post in posts:
        if post.card and not post.media:
            issues.append(f"{post.id}: has a card but no media path to render it to")
        if post.card:
            try:
                render.cards_for(post)
            except ConfigError as exc:
                issues.append(str(exc))
    awaiting = [p.id for p in posts if runner.missing_media(brand, p) and not state.started(p.id)]
    if args.check_urls:
        for post in posts:
            missing = set(runner.missing_media(brand, post))
            for m in post.media:
                if m in missing:
                    continue  # not rendered yet; the weekly batch will make it
                problem = check_public_url(media_url(brand, m))
                if problem:
                    issues.append(f"{post.id}: {problem}")
    for msg in issues:
        print(f"problem: {msg}")
    print(f"{len(posts)} posts checked, {len(issues)} problem(s), {len(awaiting)} awaiting images")
    return 1 if issues else 0


def cmd_status(args, brand, posts, state) -> int:
    tz = ZoneInfo(brand.timezone)
    for post in posts:
        marks = []
        for p in post.platforms:
            rec = state.record(post.id, p)
            if rec.get("id"):
                marks.append(f"{p}: posted {rec['at'][:10]}")
            elif rec:
                marks.append(f"{p}: failed x{rec.get('attempts', 0)}")
            else:
                marks.append(f"{p}: queued")
        print(f"{post.id:48} {' | '.join(marks)}")
    left = runner.remaining(posts, state)
    print(f"\n{left} unpublished post(s) left, about {left} day(s) of content.")
    nxt, reason = runner.choose(posts, state, datetime.now(tz).date(), tz)
    print(f"Next: {nxt.id if nxt else '-'} ({reason})")
    if left < LOW_QUEUE_WARNING:
        print(f"warning: fewer than {LOW_QUEUE_WARNING} posts left, add more to posts.yaml")
    return 0


def cmd_next(args, brand, posts, state) -> int:
    args.live, args.platform = False, None
    return cmd_post(args, brand, posts, state)


def cmd_post(args, brand, posts, state) -> int:
    if args.live and runner.paused():
        print("AUTOPILOT_PAUSED is set, nothing published.")
        return 0
    outcome = runner.run(brand, posts, state, live=args.live, post_id=args.post_id, platform=args.platform)
    lines = []
    if outcome.post is None:
        lines.append(f"Nothing to publish: {outcome.reason}.")
    else:
        mode = "LIVE" if args.live else "DRY RUN (add --live to publish)"
        lines.append(f"## {outcome.post.id} ({outcome.reason}) [{mode}]")
        for m in outcome.post.media:
            lines.append(f"- media: {media_url(brand, m)}")
        for platform, text in outcome.previews.items():
            lines.append(f"\n### {platform}\n```\n{text}\n```")
        for res in outcome.results:
            lines.append(f"- published to {res.platform}: {res.permalink or res.remote_id}")
        for platform, err in outcome.errors.items():
            lines.append(f"- FAILED on {platform}: {err}")
        if not outcome.previews and not outcome.errors:
            lines.append(outcome.reason)
    left = runner.remaining(posts, state)
    if left < LOW_QUEUE_WARNING:
        lines.append(f"\nwarning: only {left} unpublished post(s) left in the queue.")
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and args.command == "post":
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    return 0 if outcome.ok else 1


def cmd_check(args, brand, posts, state) -> int:
    graph = Graph(brand.secret("page_token"), brand.graph_api_version)
    ok = True
    page_id = brand.secret("page_id")
    try:
        page = graph.get(page_id, fields="name,instagram_business_account")
        print(f"Facebook Page: {page.get('name')} ({page_id})")
        linked = (page.get("instagram_business_account") or {}).get("id")
    except GraphError as exc:
        print(f"Facebook Page check failed: {exc}")
        return 1
    if "instagram" in brand.platforms:
        ig_id = brand.secret("ig_user_id")
        if linked and linked != ig_id:
            print(f"warning: the Page is linked to Instagram account {linked}, but {brand.env['ig_user_id']} is {ig_id}")
            ok = False
        try:
            ig = graph.get(ig_id, fields="username,followers_count")
            print(f"Instagram: @{ig.get('username')} ({ig.get('followers_count')} followers)")
            quota = graph.get(f"{ig_id}/content_publishing_limit", fields="quota_usage,config").get("data", [{}])[0]
            limit = (quota.get("config") or {}).get("quota_total")
            print(f"Instagram API posts in the last 24h: {quota.get('quota_usage')} of {limit}")
        except GraphError as exc:
            print(f"Instagram check failed: {exc}")
            ok = False
    return 0 if ok else 1


def cmd_render(args, brand, posts, state) -> int:
    targets = [p for p in posts if p.card and (not args.post_id or p.id == args.post_id)]
    written = 0
    for post in targets:
        for path in render.render_post(brand, post, brand.card_style, force=args.force):
            print(f"rendered {path.relative_to(REPO) if path.is_relative_to(REPO) else path}")
            written += 1
    print(f"{written} card(s) rendered, {len(targets)} post(s) with cards")
    return 0


def _schedule(brand, posts, state) -> list[tuple]:
    """Unpublished posts paired with the day each is expected to go out."""
    tz = ZoneInfo(brand.timezone)
    today = datetime.now(tz).date()
    day = today + timedelta(days=1) if state.published_on(today, tz) else today
    planned = []
    for post in posts:
        if state.started(post.id):
            continue
        if post.not_before and post.not_before > day:
            day = post.not_before
        planned.append((post, day))
        day += timedelta(days=1)
    return planned


def cmd_prepare(args, brand, posts, state) -> int:
    batch = _schedule(brand, posts, state)[: args.days]
    rendered = []
    for post, day in batch:
        written = render.render_post(brand, post, brand.card_style, force=args.force) if post.card else []
        if written:
            rendered.append({"id": post.id, "day": day.isoformat()})
            print(f"rendered {post.id} for {day:%a %d %b}")
        missing = runner.missing_media(brand, post)
        if missing:
            print(f"warning: {post.id} still has no image for {', '.join(missing)} (no card to render it from)")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps({"brand": brand.slug, "posts": rendered}, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rendered)} post(s) prepared")
    return 0


def cmd_preview(args, brand, posts, state) -> int:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    by_id = {p.id: p for p in posts}
    root = f"https://raw.githubusercontent.com/{args.repo}/{args.ref}/brands/{brand.slug}/"
    out = [
        f"Images and captions for the next {len(manifest['posts'])} {brand.name} posts.",
        "",
        "**Merging this pull request approves them.** Each goes out on its day at the usual time. "
        "To change one, edit `posts.yaml` on this branch (the images re-render on the next prepare run), "
        "or delete its image here to hold it back. Nothing is published until this is merged.",
    ]
    for item in manifest["posts"]:
        post = by_id[item["id"]]
        day = datetime.fromisoformat(item["day"])
        imgs = " ".join(f'<img src="{root}{m}" width="260">' for m in post.media)
        out += [
            "", "---", f"### {day:%a %d %b} · `{post.id}`", "", imgs, "",
            "<details><summary>Instagram caption</summary>", "", "```", compose.instagram_text(brand, post), "```", "</details>",
            "",
            "<details><summary>Facebook text</summary>", "", "```", compose.facebook_text(brand, post), "```", "</details>",
        ]
    print("\n".join(out))
    return 0


def cmd_setup_token() -> int:
    """Exchange a Graph API Explorer token for a long-lived Page token and print the IDs to store as secrets."""
    import getpass

    print("Paste values when asked. Nothing is echoed or saved.")
    app_id = input("Meta app ID: ").strip()
    app_secret = getpass.getpass("Meta app secret: ").strip()
    short_token = getpass.getpass("User access token from Graph API Explorer: ").strip()
    version = "v27.0"
    try:
        user = Graph(short_token, version).get(
            "oauth/access_token",
            grant_type="fb_exchange_token",
            client_id=app_id,
            client_secret=app_secret,
            fb_exchange_token=short_token,
        )
        long_user = Graph(user["access_token"], version)
        pages = long_user.get("me/accounts", fields="id,name,access_token,instagram_business_account").get("data", [])
    except (GraphError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not pages:
        print("No Pages found. Make sure you granted pages_show_list and selected your Page.", file=sys.stderr)
        return 1
    for page in pages:
        ig = (page.get("instagram_business_account") or {}).get("id", "(no Instagram account linked)")
        print(f"\nPage: {page['name']}")
        print(f"  FB_PAGE_ID     {page['id']}")
        print(f"  IG_USER_ID     {ig}")
        print(f"  FB_PAGE_TOKEN  {page['access_token']}")
    print("\nStore these as repository secrets (for example SPP_FB_PAGE_ID, SPP_IG_USER_ID, SPP_FB_PAGE_TOKEN).")
    print("A Page token made from a long-lived user token does not expire, but changing your")
    print("Facebook password or removing the app from your account revokes it.")
    return 0


COMMANDS = {
    "validate": cmd_validate,
    "status": cmd_status,
    "next": cmd_next,
    "post": cmd_post,
    "check": cmd_check,
    "render": cmd_render,
    "prepare": cmd_prepare,
    "preview": cmd_preview,
}
