import os
import sys

import requests
from bs4 import BeautifulSoup

QYWX_WEBHOOK = os.environ.get("QYWX_WEBHOOK", "")
TRENDING_URL = "https://github.com/trending"
TOP_N = 10


def fetch_trending():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html",
    }
    resp = requests.get(TRENDING_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_trending(html):
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select("article.Box-row")[:TOP_N]

    repos = []
    for article in articles:
        a_tag = article.select_one("h2 a")
        if not a_tag:
            continue

        href = a_tag.get("href", "").strip()
        name = href.strip("/") if href else "unknown/unknown"

        desc_tag = article.select_one("p")
        desc = desc_tag.get_text(strip=True) if desc_tag else ""

        lang_tag = article.select_one("[itemprop='programmingLanguage']")
        lang = lang_tag.get_text(strip=True) if lang_tag else ""

        stars_tag = article.select_one("a[href$='/stargazers']")
        stars = stars_tag.get_text(strip=True).replace(",", "") if stars_tag else "0"

        today_tag = article.select_one("span.float-sm-right")
        today_stars = today_tag.get_text(strip=True) if today_tag else ""

        repos.append(
            {
                "name": name,
                "url": f"https://github.com{href}",
                "desc": desc,
                "lang": lang,
                "stars": stars,
                "today": today_stars,
            }
        )

    return repos


def format_markdown(repos):
    lines = ["## GitHub Trending (Daily Top 10)\n"]
    for i, r in enumerate(repos, 1):
        lang_info = f" `{r['lang']}`" if r["lang"] else ""
        desc_text = r["desc"][:80] + ("..." if len(r["desc"]) > 80 else "")
        today_info = f" | Today: {r['today']}" if r["today"] else ""

        lines.append(
            f"{i}. **[{r['name']}]({r['url']})**{lang_info}\n"
            f"   > {desc_text}\n"
            f"   Stars: {r['stars']}{today_info}"
        )
    return "\n".join(lines)


def push_to_qywx(content):
    if not QYWX_WEBHOOK:
        print("Error: QYWX_WEBHOOK not set", file=sys.stderr)
        sys.exit(1)

    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }
    resp = requests.post(QYWX_WEBHOOK, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode") != 0:
        print(f"WeCom push failed: {data}", file=sys.stderr)
        sys.exit(1)
    print("Push success.")


def main():
    print("Fetching GitHub Trending...")
    html = fetch_trending()
    repos = parse_trending(html)
    if not repos:
        print("No repos found, abort.", file=sys.stderr)
        sys.exit(1)

    md = format_markdown(repos)
    print(md)

    print("Pushing to WeCom...")
    push_to_qywx(md)


if __name__ == "__main__":
    main()
