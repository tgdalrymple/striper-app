"""
MD DNR weekly fishing report scraper.

Why this matters: the score-based ranking gives mathematical "best" windows,
but a real-world report ("stripers blitzing in Eastern Bay this week, topwater
working at dawn near Poplar") is the most valuable single piece of context
you can have. We pull the most recent post from MD DNR for display.

If the page structure changes or the site is down, we just continue without it.
The app still works.
"""
from __future__ import annotations
import requests
from bs4 import BeautifulSoup

URL = "https://news.maryland.gov/dnr/?s=fishing+report"


def fetch_latest_report() -> dict | None:
    """Return {'title': str, 'date': str, 'url': str, 'excerpt': str} or None."""
    try:
        r = requests.get(URL, timeout=15,
                         headers={"User-Agent": "striper-fishing-app/1.0"})
        r.raise_for_status()
    except Exception as e:
        print(f"[dnr] could not reach MD DNR: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # The search results page uses <a class="more-link"> for each post.
    # The first one is the most recent.
    more = soup.find("a", class_="more-link")
    if not more or not more.get("href"):
        return None

    post_url = more["href"]
    title, date_str = _title_and_date_from_url(post_url)
    excerpt = _fetch_excerpt(post_url)

    return {
        "title": title,
        "url": post_url,
        "date": date_str,
        "excerpt": excerpt,
    }


def _title_and_date_from_url(url: str) -> tuple:
    """
    Convert a post URL like
        https://news.maryland.gov/dnr/2026/05/06/maryland-fishing-report-may-6/
    into ("Maryland Fishing Report — May 6", "May 6 2026").
    """
    import re
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/([^/]+)/", url)
    if not m:
        return ("Maryland Fishing Report", "")
    year, month, day, slug = m.groups()
    title = slug.replace("-", " ").title()
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    date_str = f"{months[int(month)]} {int(day)} {year}"
    return (title, date_str)


def _fetch_excerpt(url: str) -> str:
    """Pull the first paragraph or two from the post itself."""
    try:
        r = requests.get(url, timeout=15,
                         headers={"User-Agent": "striper-fishing-app/1.0"})
        r.raise_for_status()
    except Exception:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    # WordPress single-post body lives in .entry-content or main <article>
    body = soup.find(class_="entry-content") or soup.find("article") or soup
    paragraphs = []
    for p in body.find_all("p"):
        txt = p.get_text(strip=True)
        if len(txt) > 40 and "Tags:" not in txt:
            paragraphs.append(txt)
        if len(paragraphs) >= 2:
            break
    return " ".join(paragraphs)[:500]
