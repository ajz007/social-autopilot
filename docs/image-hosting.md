# Image hosting

Instagram's publishing API only accepts media by URL: Meta's servers download the image from a public link. Every file under `brands/<brand>/images/` therefore has to be reachable at `image_base_url` + its path, served as `image/jpeg`.

Pick one option:

| Option | Setup | Notes |
| --- | --- | --- |
| **Your website**, for example `https://shaadiplannerpro.com/social/` | Serve the `images/` folder under `/social/` | Images live on your own domain. Each new batch of images needs a site deploy. |
| **Public GitHub repository** (current setting) | `image_base_url: https://raw.githubusercontent.com/ajz007/social-autopilot/main/brands/shaadi-planner-pro/` | Nothing else to set up, and new images go live as soon as they're pushed. The post queue and publishing history become public too. |
| **A public S3 or CDN prefix** | Upload `images/` to a bucket or prefix that allows public reads, and set `image_base_url` to its URL | Keep it separate from the private bucket that holds paid downloads. |

After changing it, run:

```bash
python -m autopilot validate --brand shaadi-planner-pro --check-urls
```

The daily run also checks the day's images before publishing. If any are missing, nothing is posted and the run fails, so a post never goes out on just one platform.

## Hiding parts of a source image

Product art sometimes shows details that shouldn't be posted, such as prices. Add a `cover` to the card to blur an area of the source image, optionally with a short label on top. Positions are percentages of the source image:

```yaml
card:
  layout: image
  image: sources/sangeet-host-kit.webp
  cover:
    - {left: 31, top: 75.5, width: 38.5, height: 12.5, label: "Ready-to-use scripts"}
    - {left: 85.5, top: 3, width: 14, height: 25, shape: circle, label: "35\nmessages", size: 21}
```

Then re-render with `python -m autopilot render --brand <brand> --post-id <id> --force`.
