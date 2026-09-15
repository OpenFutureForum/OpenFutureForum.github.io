#!/usr/bin/env python3
"""Validate the Open Future Forum Pages hub using only the standard library."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]


class HubParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []
        self.headings: list[int] = []
        self.canonical: list[str] = []
        self.json_ld: list[str] = []
        self._json_ld_buffer: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(int(tag[1]))
        if tag == "link" and values.get("rel") == "canonical" and values.get("href"):
            self.canonical.append(values["href"])
        if tag == "script" and values.get("type") == "application/ld+json":
            self._json_ld_buffer = []

    def handle_data(self, data: str) -> None:
        if self._json_ld_buffer is not None:
            self._json_ld_buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_ld_buffer is not None:
            self.json_ld.append("".join(self._json_ld_buffer))
            self._json_ld_buffer = None


def main() -> None:
    required = [
        ROOT / "index.html",
        ROOT / "favicon.svg",
        ROOT / "projects.json",
        ROOT / "robots.txt",
        ROOT / "sitemap.xml",
    ]
    missing = [path.name for path in required if not path.exists()]
    assert not missing, f"Missing public files: {', '.join(missing)}"

    parser = HubParser()
    parser.feed((ROOT / "index.html").read_text(encoding="utf-8"))

    assert len(parser.ids) == len(set(parser.ids)), "Duplicate HTML IDs found"
    assert parser.headings and parser.headings[0] == 1, "The first heading must be H1"
    assert parser.headings.count(1) == 1, "The page must contain exactly one H1"
    assert parser.canonical == ["https://openfutureforum.github.io/"], "Unexpected canonical URL"
    assert parser.json_ld, "JSON-LD is required"
    for block in parser.json_ld:
        json.loads(block)

    for link in parser.links:
        parsed = urlparse(link)
        assert parsed.scheme != "http", f"Insecure link: {link}"
        if link.startswith("#"):
            assert link[1:] in parser.ids, f"Missing fragment target: {link}"

    directory = json.loads((ROOT / "projects.json").read_text(encoding="utf-8"))
    projects = directory.get("projects", [])
    assert len(projects) == 7, f"Expected 7 substantive projects, found {len(projects)}"
    ids = [project["id"] for project in projects]
    assert len(ids) == len(set(ids)), "Duplicate project IDs found"
    for project in projects:
        assert project.get("name") and project.get("description"), "Incomplete project record"
        assert project.get("repository_url", "").startswith("https://"), "Invalid repository URL"

    sitemap = ElementTree.parse(ROOT / "sitemap.xml")
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [node.text for node in sitemap.findall("sm:url/sm:loc", namespace)]
    assert "https://openfutureforum.github.io/" in urls, "Hub missing from sitemap"
    assert all(url and url.startswith("https://openfutureforum.github.io/") for url in urls)

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap: https://openfutureforum.github.io/sitemap.xml" in robots

    print(f"Hub validation passed: {len(projects)} projects, {len(urls)} sitemap URLs")


if __name__ == "__main__":
    main()
