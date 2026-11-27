# Social Autopilot

Publishes one post a day to a Facebook Page and an Instagram professional account from a queue you write in YAML. It uses Meta's official Graph API, so it doesn't break Facebook or Instagram rules. A GitHub Actions schedule runs it, and no server is needed.

The first brand is [Shaadi Planner Pro](brands/shaadi-planner-pro/), with 30 days of posts and rendered images.

## How it works

1. `brands/<brand>/posts.yaml` is the content plan: caption, hashtags, link and card design for each day. Card designs can sit on illustrated shaadi scenes (`lights`, `toran`, `diyas`, `mehendi`, `kolam`, `dhol`), drawn in code like the invitation templates.
2. **Every Sunday**, the [Prepare week](.github/workflows/prepare-week.yml) workflow draws the next 7 days of images with headless Chrome and opens a pull request that shows each image and caption.
3. **Merging that pull request approves the week.** Images are served from this public repository, because Meta downloads media from a link rather than accepting uploads.
4. **Every evening at 19:00 IST**, the [Daily post](.github/workflows/daily-post.yml) workflow publishes the next post and saves `state/<brand>.json`, the record of what went out, to the `autopilot-state` branch (so `main` can stay protected). If that day's images haven't been merged yet, nothing is posted and the run fails, so you get GitHub's failure email as a reminder.

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
python -m autopilot prepare  --brand shaadi-planner-pro [--days 7]       # the weekly batch
python -m autopilot preview  --brand shaadi-planner-pro --ref <sha>     # pull request text for that batch
python -m autopilot check    --brand shaadi-planner-pro   # verify token, Page, Instagram account and API quota
python -m autopilot post     --brand shaadi-planner-pro [--live] [--post-id ID] [--platform instagram]
python -m autopilot setup-token                            # get a never-expiring Page token, see docs/meta-setup.md

python -m unittest discover -s tests
```

`render` needs Chrome or Chromium. Set `AUTOPILOT_CHROME` if it isn't found. It converts screenshots to JPEG with Pillow if it's installed, or with Windows PowerShell under WSL.

## Going live

1. Follow [Meta setup](docs/meta-setup.md) to get the Page ID, Instagram user ID and Page token.
2. Add them as repository secrets: `FB_PAGE_ID`, `IG_USER_ID`, `FB_PAGE_TOKEN`.
3. Push the rendered images (they're served from this public repository), then confirm with `python -m autopilot validate --brand shaadi-planner-pro --check-urls`.
4. Under **Actions → Daily post → Run workflow**, run a dry run, then run once with **live** checked.
5. Set the repository variable `AUTOPILOT_LIVE=true` to turn on the daily schedule.

## Writing posts

See the comment at the top of [posts.yaml](brands/shaadi-planner-pro/posts.yaml) for every field. Card layouts:

| Layout | Use for | Fields |
| --- | --- | --- |
| `tip` | Checklists and how-tos (the most-saved format) | `kicker`, `title`, `points` |
| `image` | Products and screenshots | `kicker`, `title`, `body`, `image` (a file under the brand folder) |
| `statement` | Quotes, questions, polls and relatable posts | `kicker`, `title`, `body`, `cta` |

Any layout takes `scene: <name>` for an illustrated background, and `align: top|center` to place the text.

Use `card: { slides: [ ... ] }` with several `media` paths to make a carousel. `status` warns when fewer than seven posts are left.

## Adding a brand

Copy `brands/shaadi-planner-pro/` to `brands/<new-brand>/` and edit `brand.yaml` (name, site, time zone, colours and the names of its secret variables). Then add the brand to the `matrix.brand` list in the workflow, along with its secrets in the job's `env`.
