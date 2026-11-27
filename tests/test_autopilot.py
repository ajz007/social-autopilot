import io
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from autopilot import compose, runner
from autopilot.cli import main
from autopilot.config import ConfigError, load_brand, load_posts
from autopilot.graph import Graph

BRAND_YAML = """
name: Test Brand
site_url: https://example.com
timezone: Asia/Kolkata
image_base_url: https://cdn.example.com/social
env: {page_id: T_PAGE_ID, page_token: T_TOKEN, ig_user_id: T_IG_ID}
facebook: {max_hashtags: 2}
instagram: {max_hashtags: 3, link_text: "Link in bio"}
"""

POSTS_YAML = """
- id: first
  caption: Hello families
  hashtags: [one, two, three, four]
  link: /#demo
  media: images/first.jpg
- id: second
  caption: Carousel time
  media: [images/a.jpg, images/b.jpg]
- id: third
  caption: Facebook only text
  platforms: [facebook]
  not_before: 2030-01-01
"""

ENV = {"T_PAGE_ID": "PAGE", "T_TOKEN": "SECRET", "T_IG_ID": "IG"}


class FakeGraph:
    """Records calls and answers like the Graph API would."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.counter = 0
        self.fail_on = fail_on

    def __call__(self, method, url, params):
        path = url.split("/v27.0/", 1)[1]
        self.calls.append((method, path, dict(params)))
        if self.fail_on and self.fail_on in path:
            return 400, json.dumps({"error": {"message": "boom", "code": 100}}).encode()
        self.counter += 1
        if method == "GET" and "fields" in params and "status_code" in params["fields"]:
            return 200, b'{"status_code": "FINISHED"}'
        if method == "GET":
            return 200, json.dumps({"permalink": "https://ig/p", "permalink_url": "https://fb/p"}).encode()
        if path.endswith("/photos"):
            return 200, json.dumps({"id": f"photo{self.counter}", "post_id": f"PAGE_{self.counter}"}).encode()
        return 200, json.dumps({"id": f"id{self.counter}"}).encode()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "brands" / "test").mkdir(parents=True)
        (root / "brands" / "test" / "brand.yaml").write_text(BRAND_YAML)
        (root / "brands" / "test" / "posts.yaml").write_text(POSTS_YAML)
        self.root = root
        images = root / "brands" / "test" / "images"
        images.mkdir()
        for name in ("first", "a", "b"):
            (images / f"{name}.jpg").write_bytes(b"jpeg")
        self.brand = load_brand(root / "brands", "test")
        self.posts = load_posts(self.brand)
        self.state = runner.State(root / "state" / "test.json")
        self.env = mock.patch.dict(os.environ, ENV)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_live(self, fake, now=None, **kw):
        factory = lambda token, version: Graph(token, version, transport=fake, sleep=lambda s: None)
        now = now or datetime(2026, 12, 1, 13, 30, tzinfo=timezone.utc)
        kw.setdefault("url_checker", lambda url: None)
        return runner.run(self.brand, self.posts, self.state, live=True, now=now, graph_factory=factory, **kw)


class ComposeTests(Base):
    def test_facebook_gets_tracked_link_before_fragment_and_limited_hashtags(self):
        text = compose.facebook_text(self.brand, self.posts[0])
        self.assertIn(
            "https://example.com/?utm_source=facebook&utm_medium=social&utm_campaign=social-autopilot&utm_content=first#demo",
            text,
        )
        self.assertTrue(text.endswith("#one #two"))

    def test_instagram_gets_link_text_not_url(self):
        text = compose.instagram_text(self.brand, self.posts[0])
        self.assertNotIn("http", text)
        self.assertIn("Link in bio", text)
        self.assertTrue(text.endswith("#one #two #three"))


class ConfigTests(Base):
    def write_posts(self, body):
        (self.root / "brands" / "test" / "posts.yaml").write_text(body)
        return load_posts(self.brand)

    def test_instagram_requires_media(self):
        with self.assertRaisesRegex(ConfigError, "need at least one image"):
            self.write_posts("- id: x1\n  caption: hi\n")

    def test_png_rejected(self):
        with self.assertRaisesRegex(ConfigError, "JPEG"):
            self.write_posts("- id: x1\n  caption: hi\n  media: a.png\n")

    def test_duplicate_ids_rejected(self):
        with self.assertRaisesRegex(ConfigError, "duplicate"):
            self.write_posts("- {id: x1, caption: a, media: a.jpg}\n- {id: x1, caption: b, media: b.jpg}\n")

    def test_missing_secret_is_reported_by_variable_name(self):
        with mock.patch.dict(os.environ, {"T_TOKEN": ""}):
            with self.assertRaisesRegex(ConfigError, "T_TOKEN"):
                self.brand.secret("page_token")


class RunnerTests(Base):
    def test_dry_run_calls_nothing_and_records_nothing(self):
        fake = FakeGraph()
        outcome = runner.run(self.brand, self.posts, self.state, live=False,
                             graph_factory=lambda *a: self.fail("graph used in dry run"))
        self.assertEqual(outcome.post.id, "first")
        self.assertEqual(set(outcome.previews), {"facebook", "instagram"})
        self.assertEqual(fake.calls, [])
        self.assertFalse(self.state.path.exists())

    def test_single_image_publishes_to_both_platforms(self):
        fake = FakeGraph()
        outcome = self.run_live(fake)
        self.assertTrue(outcome.ok, outcome.errors)
        paths = [(m, p) for m, p, _ in fake.calls if m == "POST"]
        self.assertEqual(paths, [("POST", "PAGE/photos"), ("POST", "IG/media"), ("POST", "IG/media_publish")])
        photo = fake.calls[0][2]
        self.assertEqual(photo["url"], "https://cdn.example.com/social/images/first.jpg")
        self.assertEqual(photo["access_token"], "SECRET")
        saved = json.loads(self.state.path.read_text())
        self.assertEqual(set(saved["posts"]["first"]), {"facebook", "instagram"})

    def test_only_one_new_post_per_day(self):
        self.run_live(FakeGraph())
        outcome = self.run_live(FakeGraph(), now=datetime(2026, 12, 1, 18, 0, tzinfo=timezone.utc))
        self.assertIsNone(outcome.post)
        self.assertIn("already went out today", outcome.reason)
        nxt = self.run_live(FakeGraph(), now=datetime(2026, 12, 2, 13, 30, tzinfo=timezone.utc))
        self.assertEqual(nxt.post.id, "second")

    def test_day_boundary_uses_brand_timezone(self):
        # 20:00 UTC on 1 Dec is already 2 Dec in India.
        self.run_live(FakeGraph(), now=datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc))
        outcome = self.run_live(FakeGraph(), now=datetime(2026, 12, 1, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(outcome.post.id, "second")

    def test_partial_failure_retries_only_the_failed_platform(self):
        outcome = self.run_live(FakeGraph(fail_on="IG/media"))
        self.assertEqual(set(outcome.errors), {"instagram"})
        self.assertTrue(self.state.done("first", "facebook"))
        retry_fake = FakeGraph()
        retry = self.run_live(retry_fake)
        self.assertEqual(retry.post.id, "first")
        self.assertEqual([r.platform for r in retry.results], ["instagram"])
        self.assertFalse(any("PAGE/" in p for _, p, _ in retry_fake.calls))

    def test_gives_up_after_max_attempts(self):
        for day in range(1, runner.MAX_ATTEMPTS + 1):
            self.run_live(FakeGraph(fail_on="IG/media"), now=datetime(2026, 12, day, 13, 0, tzinfo=timezone.utc))
        outcome = self.run_live(FakeGraph(), now=datetime(2026, 12, 9, 13, 0, tzinfo=timezone.utc))
        self.assertEqual(outcome.post.id, "second")

    def test_unreachable_media_blocks_both_platforms_without_using_an_attempt(self):
        fake = FakeGraph()
        outcome = self.run_live(fake, url_checker=lambda url: f"{url} is not reachable")
        self.assertIn("media", outcome.errors)
        self.assertEqual(fake.calls, [])
        self.assertFalse(self.state.started("first"))

    def test_unapproved_images_block_publishing_without_using_an_attempt(self):
        (self.brand.root / "images" / "first.jpg").unlink()
        fake = FakeGraph()
        outcome = self.run_live(fake)
        self.assertIn("approval", outcome.errors)
        self.assertIn("Merge that week", outcome.errors["approval"])
        self.assertEqual(fake.calls, [])
        self.assertFalse(self.state.started("first"))

    def test_carousel_flow(self):
        self.run_live(FakeGraph())
        fake = FakeGraph()
        outcome = self.run_live(fake, now=datetime(2026, 12, 2, 13, 0, tzinfo=timezone.utc))
        self.assertTrue(outcome.ok, outcome.errors)
        posts = [(p, params) for m, p, params in fake.calls if m == "POST"]
        fb_photos = [params for p, params in posts if p == "PAGE/photos"]
        self.assertEqual([x["published"] for x in fb_photos], ["false", "false"])
        feed = [params for p, params in posts if p == "PAGE/feed"][0]
        self.assertIn("attached_media[1]", feed)
        carousel = [params for p, params in posts if p == "IG/media" and params.get("media_type") == "CAROUSEL"]
        self.assertEqual(len(carousel), 1)
        self.assertEqual(len(carousel[0]["children"].split(",")), 2)

    def test_not_before_is_respected(self):
        self.state.data["posts"] = {"first": {"facebook": {"id": "1", "at": "2026-11-01T00:00:00+00:00"},
                                              "instagram": {"id": "2", "at": "2026-11-01T00:00:00+00:00"}},
                                    "second": {"facebook": {"id": "3", "at": "2026-11-02T00:00:00+00:00"},
                                               "instagram": {"id": "4", "at": "2026-11-02T00:00:00+00:00"}}}
        post, reason = runner.choose(self.posts, self.state, date(2026, 12, 1), ZoneInfo("Asia/Kolkata"))
        self.assertIsNone(post)
        self.assertIn("third is scheduled for 2030-01-01", reason)


class CliTests(Base):
    def test_paused_live_run_publishes_nothing(self):
        with mock.patch.dict(os.environ, {"AUTOPILOT_PAUSED": "1"}):
            code = main(["--brands-dir", str(self.root / "brands"), "--state-dir", str(self.root / "state"),
                         "post", "--brand", "test", "--live"])
        self.assertEqual(code, 0)
        self.assertFalse((self.root / "state" / "test.json").exists())


class RenderTests(Base):
    def test_cover_blurs_a_region_with_an_escaped_label(self):
        from autopilot import render

        src = self.brand.root / "sources" / "art.png"
        src.parent.mkdir()
        src.write_bytes(b"\x89PNG fake")
        page = render.card_html(self.brand, {
            "layout": "image", "title": "T", "image": "sources/art.png",
            "cover": [{"left": 10, "top": 20, "width": 30, "height": 5, "shape": "circle", "label": "a<b\nc", "size": 20}],
        }, {})
        self.assertIn("left:10.0%;top:20.0%;width:30.0%;height:5.0%;border-radius:50%", page)
        self.assertIn('<span style="font-size:20px">a&lt;b<br>c</span>', page)

    def test_cover_requires_numeric_box(self):
        from autopilot import render

        with self.assertRaisesRegex(ConfigError, "cover needs"):
            render._cover_html({"left": 1, "top": 2, "width": "wide"})


class PrepareTests(Base):
    def cli(self, *args):
        return main(["--brands-dir", str(self.root / "brands"), "--state-dir", str(self.root / "state"), *args])

    def test_prepare_renders_only_the_next_unpublished_batch(self):
        from autopilot import render

        self.state.data["posts"] = {"first": {"facebook": {"id": "1", "at": "2026-11-01T00:00:00+00:00"},
                                              "instagram": {"id": "2", "at": "2026-11-01T00:00:00+00:00"}}}
        self.state.save()
        rendered = []
        manifest = self.root / "build" / "prepared.json"
        with mock.patch.object(render, "render_post", side_effect=lambda brand, post, style, force=False:
                               rendered.append(post.id) or [Path("x.jpg")]):
            for post in self.posts:
                post.card = {"layout": "statement", "title": post.id}
            with mock.patch("autopilot.cli.load_posts", return_value=self.posts):
                code = self.cli("prepare", "--brand", "test", "--days", "1", "--manifest", str(manifest))
        self.assertEqual(code, 0)
        self.assertEqual(rendered, ["second"])
        self.assertEqual([p["id"] for p in json.loads(manifest.read_text())["posts"]], ["second"])

    def test_preview_links_images_at_the_given_commit(self):
        manifest = self.root / "prepared.json"
        manifest.write_text(json.dumps({"brand": "test", "posts": [{"id": "second", "day": "2026-12-02"}]}))
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            code = self.cli("preview", "--brand", "test", "--manifest", str(manifest), "--ref", "abc123", "--repo", "o/r")
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("https://raw.githubusercontent.com/o/r/abc123/brands/test/images/a.jpg", text)
        self.assertIn("Wed 02 Dec", text)
        self.assertIn("Merging this pull request approves them", text)


class RealBrandTests(unittest.TestCase):
    def test_bundled_brands_load_and_fit_platform_limits(self):
        brands_dir = Path(__file__).resolve().parent.parent / "brands"
        for folder in brands_dir.iterdir():
            if (folder / "brand.yaml").is_file():
                brand = load_brand(brands_dir, folder.name)
                posts = load_posts(brand)
                self.assertTrue(posts)
                problems = [p for post in posts for p in compose.problems(brand, post)]
                self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
