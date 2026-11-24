"""Render branded 1080x1350 JPEG cards from HTML with headless Chrome.

Rendering is a local authoring step: the cards are committed and then hosted
at a public URL, because Meta downloads media from a URL rather than accepting uploads.
"""

from __future__ import annotations

import base64
import html
import mimetypes
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import Brand, ConfigError, Post

WIDTH, HEIGHT = 1080, 1350
TEMPLATE = Path(__file__).parent / "templates" / "card.html"

DEFAULT_STYLE = {
    "background": "#fff8e9",
    "ink": "#203c32",
    "accent": "#762747",
    "accent_ink": "#fff8e9",
    "gold": "#ac7937",
    "heading_font": "Playfair Display",
    "body_font": "Inter",
}

CHROME_CANDIDATES = [
    "google-chrome",
    "chromium",
    "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
]


class RenderError(Exception):
    pass


def cards_for(post: Post) -> list[tuple[dict, str]]:
    """Pair each card spec with the media path it renders to."""
    if not post.card:
        return []
    specs = post.card.get("slides") if "slides" in post.card else [post.card]
    images = [m for m in post.media if not m.startswith(("http://", "https://"))]
    if len(specs) > len(images):
        raise ConfigError(f"{post.id}: {len(specs)} card(s) but only {len(images)} local media path(s)")
    return list(zip(specs, images))


def render_post(brand: Brand, post: Post, style: dict, force: bool = False) -> list[Path]:
    written = []
    for spec, rel in cards_for(post):
        out = brand.root / rel
        if out.exists() and not force:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        page = card_html(brand, spec, style)
        screenshot(page, out)
        written.append(out)
    return written


def card_html(brand: Brand, spec: dict, style: dict) -> str:
    s = {**DEFAULT_STYLE, **(style or {})}
    layout = spec.get("layout", "tip")
    if layout not in ("tip", "image", "statement"):
        raise ConfigError(f"unknown card layout '{layout}'")
    e = html.escape

    points = "".join(
        f'<li><span class="n">{i:02d}</span><span>{e(str(p))}</span></li>'
        for i, p in enumerate(spec.get("points") or [], start=1)
    )
    image = ""
    if spec.get("image"):
        image = f'<div class="shot"><img src="{_data_uri(brand.root / spec["image"])}" alt=""></div>'

    domain = brand.site_url.split("://", 1)[-1]
    replacements = {
        "{{layout}}": layout,
        "{{kicker}}": e(str(spec.get("kicker", ""))),
        "{{title}}": e(str(spec.get("title", ""))).replace("\n", "<br>"),
        "{{body}}": e(str(spec.get("body", ""))).replace("\n", "<br>"),
        "{{points}}": f"<ol>{points}</ol>" if points else "",
        "{{image}}": image,
        "{{cta}}": e(str(spec.get("cta", ""))),
        "{{brand}}": e(brand.name),
        "{{domain}}": e(domain),
        "{{heading_font_url}}": s["heading_font"].replace(" ", "+"),
        "{{body_font_url}}": s["body_font"].replace(" ", "+"),
    }
    for key, value in s.items():
        replacements["{{" + key + "}}"] = e(str(value))
    page = TEMPLATE.read_text(encoding="utf-8")
    for key, value in replacements.items():
        page = page.replace(key, value)
    return page


def _data_uri(path: Path) -> str:
    if not path.is_file():
        raise ConfigError(f"card image not found: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    if path.suffix.lower() == ".webp":
        mime = "image/webp"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def find_chrome() -> str:
    override = os.environ.get("AUTOPILOT_CHROME")
    if override:
        return override
    for candidate in CHROME_CANDIDATES:
        found = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if found:
            return found
    raise RenderError("Chrome or Chromium not found; set AUTOPILOT_CHROME to its path")


def _host_path(path: Path, chrome: str) -> str:
    """Windows Chrome running under WSL needs Windows-style paths."""
    if chrome.lower().endswith(".exe") and shutil.which("wslpath"):
        return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()
    return str(path)


def _file_url(path: str) -> str:
    path = path.replace("\\", "/")
    if path.startswith("//"):  # UNC path such as //wsl.localhost/Ubuntu/...
        return "file:" + path
    return "file:///" + path.lstrip("/")


def screenshot(page: str, out: Path) -> None:
    chrome = find_chrome()
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=".render-") as tmp:
        tmpdir = Path(tmp)
        src = tmpdir / "card.html"
        png = tmpdir / "card.png"
        src.write_text(page, encoding="utf-8")
        url = _file_url(_host_path(src, chrome))
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={WIDTH},{HEIGHT}",
            "--virtual-time-budget=5000",
            f"--screenshot={_host_path(png, chrome)}",
            url,
        ]
        subprocess.run(cmd, check=False, capture_output=True, timeout=120)
        if not png.is_file():
            raise RenderError(f"Chrome did not produce a screenshot for {out.name}")
        to_jpeg(png, out)


def to_jpeg(png: Path, out: Path, quality: int = 90) -> None:
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        Image = None
    if Image is not None:
        Image.open(png).convert("RGB").save(out, "JPEG", quality=quality, optimize=True)
        return
    if shutil.which("powershell.exe") and shutil.which("wslpath"):
        src = subprocess.check_output(["wslpath", "-w", str(png)], text=True).strip()
        dst = subprocess.check_output(["wslpath", "-w", str(out)], text=True).strip()
        script = (
            "Add-Type -AssemblyName System.Drawing;"
            f"$i=[System.Drawing.Image]::FromFile('{src}');"
            "$c=[System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders()|?{$_.MimeType -eq 'image/jpeg'};"
            "$p=New-Object System.Drawing.Imaging.EncoderParameters 1;"
            f"$p.Param[0]=New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality,[long]{quality});"
            f"$i.Save('{dst}',$c,$p);$i.Dispose()"
        )
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], check=True, capture_output=True)
        if out.is_file():
            return
    raise RenderError("cannot convert PNG to JPEG: install Pillow (pip install pillow)")
