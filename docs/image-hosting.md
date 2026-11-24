# Image hosting

Instagram's publishing API only accepts media by URL: Meta's servers download the image from a public link. Every file under `brands/<brand>/images/` therefore has to be reachable at `image_base_url` + its path, served as `image/jpeg`.

Pick one option:

| Option | Setup | Notes |
| --- | --- | --- |
| **Your website** (current setting: `https://shaadiplannerpro.com/social/`) | Serve the `images/` folder under `/social/` | Images live on your own domain. Each new batch of images needs a site deploy. |
| **Public GitHub repository** | Make this repository public and set `image_base_url: https://raw.githubusercontent.com/<owner>/social-autopilot/main/brands/shaadi-planner-pro/` | Nothing else to set up, and new images go live as soon as they're pushed. The post queue and publishing history become public too. |
| **A public S3 or CDN prefix** | Upload `images/` to a bucket or prefix that allows public reads, and set `image_base_url` to its URL | Keep it separate from the private bucket that holds paid downloads. |

After changing it, run:

```bash
python -m autopilot validate --brand shaadi-planner-pro --check-urls
```

The daily run also checks the day's images before publishing. If any are missing, nothing is posted and the run fails, so a post never goes out on just one platform.
