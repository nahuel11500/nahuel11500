"""Refresh the blog and upstream columns of README.md.

Blog posts come from the site's RSS feed, merged pull requests from the GitHub
search API. Standard library only, so the workflow needs no install step.
"""

import email.utils
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER = "nahuel11500"
FEED = "https://nahuelcanavy.com/rss.xml"
# Pull requests to my own repositories and to my employer's are not "upstream".
EXCLUDED_OWNERS = (USER, "wiremind")
LIMIT = 4
README = Path(__file__).resolve().parent.parent / "README.md"


def get(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "profile-readme", **(headers or {})})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def blog_posts() -> list[str]:
    items = ET.fromstring(get(FEED)).iter("item")
    posts = [
        (email.utils.parsedate_to_datetime(i.findtext("pubDate")), i.findtext("title"), i.findtext("link"))
        for i in items
    ]
    posts.sort(reverse=True)
    return [f"[{title}]({link}) - {date:%Y-%m-%d}" for date, title, link in posts[:LIMIT]]


def merged_upstream() -> list[str]:
    query = f"author:{USER} is:pr is:merged " + " ".join(f"-user:{o}" for o in EXCLUDED_OWNERS)
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode(
        {"q": query, "sort": "updated", "order": "desc", "per_page": 20}
    )
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    items = json.loads(get(url, headers))["items"]
    items.sort(key=lambda i: i["closed_at"], reverse=True)
    lines = []
    for item in items[:LIMIT]:
        repo = item["repository_url"].split("/repos/", 1)[1]
        # "fix(scope): do the thing" reads better as "Do the thing".
        title = re.sub(r"^\w+(\([^)]*\))?!?:\s*", "", item["title"])
        title = title[:1].upper() + title[1:]
        lines.append(f"[{repo}]({item['html_url']}) - {title}")
    return lines


def replace(text: str, marker: str, lines: list[str]) -> str:
    pattern = re.compile(rf"(<!-- {marker} starts -->\n).*?(<!-- {marker} ends -->)", re.S)
    body = "".join(f"{line}\n\n" for line in lines)
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), text)


def main() -> None:
    text = README.read_text()
    text = replace(text, "blog", blog_posts())
    text = replace(text, "upstream", merged_upstream())
    README.write_text(text)


if __name__ == "__main__":
    main()
