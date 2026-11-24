# Social Autopilot

Publishes one post a day to a Facebook Page and an Instagram professional account from a queue you write in YAML. It uses Meta's official Graph API, so it doesn't break Facebook or Instagram rules. A GitHub Actions schedule runs it, and no server is needed.

The first brand is [Shaadi Planner Pro](brands/shaadi-planner-pro/), with 30 days of posts and rendered images.

## How it works

1. `brands/<brand>/posts.yaml` holds the queue: caption, hashtags, link and images for each post.
2. `python -m autopilot render` draws branded 1080×1350 JPEG cards from each post's `card` section with headless Chrome.
3. The images are hosted at a public URL, because Meta downloads media from a link rather than accepting uploads. See [image hosting](docs/image-hosting.md).
4. Every evening at 19:00 IST, the [Daily post](.github/workflows/daily-post.yml) workflow publishes the next post and commits `state/<brand>.json`, the record of what went out.

Built-in safeguards:

- **At most one new post per day** in the brand's time zone, even if the workflow runs twice.
- **Dry run by default.** Scheduled runs publish only after you set the repository variable `AUTOPILOT_LIVE` to `true`. Set `AUTOPILOT_PAUSED` to `true` to stop at any time.
- **No duplicate posts.** Publish requests are never retried automatically, and each platform's result is saved as soon as it succeeds.
- **No half-published posts from missing images.** Media URLs are checked before anything is sent. If one platform fails later, the next run retries only that platform, and gives up after three attempts.
- **Links are tracked.** Facebook links get UTM tags, so site analytics show which post brought each visitor. Instagram captions say "Link in bio" instead, because links in captions aren't clickable there.

## Commands

```bash
pip install -r requirements.txt            # PyYAML only

python -m autopilot validate --brand shaadi-planner-pro [--check-urls]
python -m autopilot status   --brand shaadi-planner-pro   # what's posted, what's next, days of content left
python -m autopilot next     --brand shaadi-planner-pro   # preview the exact text for each platform
python -m autopilot render   --brand shaadi-planner-pro [--post-id ID] [--force]
python -m autopilot check    --brand shaadi-planner-pro   # verify token, Page, Instagram account and API quota
python -m autopilot post     --brand shaadi-planner-pro [--live] [--post-id ID] [--platform instagram]
python -m autopilot setup-token                            # get a never-expiring Page token, see docs/meta-setup.md

python -m unittest discover -s tests
```

`render` needs Chrome or Chromium. Set `AUTOPILOT_CHROME` if it isn't found. It converts screenshots to JPEG with Pillow if it's installed, or with Windows PowerShell under WSL.

## Going live

1. Follow [Meta setup](docs/meta-setup.md) to get the Page ID, Instagram user ID and Page token.
2. Add them as repository secrets: `SPP_FB_PAGE_ID`, `SPP_IG_USER_ID`, `SPP_FB_PAGE_TOKEN`.
3. Host the images, then confirm with `python -m autopilot validate --brand shaadi-planner-pro --check-urls`.
4. Under **Actions → Daily post → Run workflow**, run a dry run, then run once with **live** checked.
5. Set the repository variable `AUTOPILOT_LIVE=true` to turn on the daily schedule.

## Writing posts

See the comment at the top of [posts.yaml](brands/shaadi-planner-pro/posts.yaml) for every field. Card layouts:

| Layout | Use for | Fields |
| --- | --- | --- |
| `tip` | Checklists and how-tos (the most-saved format) | `kicker`, `title`, `points` |
| `image` | Products and screenshots | `kicker`, `title`, `body`, `image` (a file under the brand folder) |
| `statement` | Questions, polls and relatable posts that get comments | `kicker`, `title`, `body`, `cta` |

Use `card: { slides: [ ... ] }` with several `media` paths to make a carousel. `status` warns when fewer than seven posts are left.

## Adding a brand

Copy `brands/shaadi-planner-pro/` to `brands/<new-brand>/` and edit `brand.yaml` (name, site, time zone, colours and the names of its secret variables). Then add the brand to the `matrix.brand` list in the workflow, along with its secrets in the job's `env`.
