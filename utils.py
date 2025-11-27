import logging
import tomllib
from datetime import datetime, timedelta, timezone
from typing import Generator, Self

import requests
from arxiv import Result
from mdBuilder import MdBuilder
from mdElement import *

logging.basicConfig(format="[%(asctime)s %(levelname)s] %(message)s",
                    datefmt="%Y/%m/%d %H:%M:%S",
                    level=logging.INFO)

# load config from file
with open("config.toml", "rb") as f:
    config = tomllib.load(f)


class Paper:
    def __init__(self,
                 date: datetime,
                 title: str,
                 authors: list[Result.Author],
                 id: str,
                 url: str,
                 abstract: str = "") -> None:
        self.date: datetime = date
        self.title: str = title
        self.authors: str = f"{authors[0].name} et al." if len(
            authors) > 1 else authors[0].name
        self.id: str = id
        self.url: str = url
        self.abstract: str = abstract
        self.code: str | None = None

    def get_code_link(self):
        query_url = f"https://arxiv.paperswithcode.com/api/v0/papers/{self.id}"
        try:
            result = requests.get(query_url).json()
            if "official" in result and result["official"]:
                self.code = result["official"]["url"]
            else:
                self.code = None
        except:
            self.code = None

    def __repr__(self) -> str:
        return str({
            "date": self.date.strftime("%Y/%m/%d"),
            "title": self.title,
            "authors": self.authors,
            "id": self.id,
            "url": self.url,
            "code": self.code
        })

    def __lt__(self, other: Self) -> bool:
        return self.date < other.date

    def __gt__(self, other: Self) -> bool:
        return self.date > other.date

    def __eq__(self, other: Self) -> bool:
        return self.id == other.id


def log(message: str):
    logging.info(message)


def concat_filters(
    filters: list[str],
    categories: list[str] | None = None,
    search_field: str = "all"
) -> str:
    """
    Build arXiv query string with keyword filters and optional category constraints.
    
    Args:
        filters: List of keyword search terms
        categories: List of arXiv categories (e.g., ["q-fin.TR", "q-fin"])
                   Use parent category like "q-fin" to search all subcategories
        search_field: Field to search in - "all", "ti" (title), "abs" (abstract), "au" (author)
    
    Returns:
        Query string for arXiv API
    """
    # Expand parent categories to all subcategories
    category_map = {
        "q-fin": ["q-fin.CP", "q-fin.EC", "q-fin.GN", "q-fin.MF",
                  "q-fin.PM", "q-fin.PR", "q-fin.RM", "q-fin.ST", "q-fin.TR"],
        "stat": ["stat.AP", "stat.CO", "stat.ME", "stat.ML", "stat.OT", "stat.TH"],
        "econ": ["econ.EM", "econ.GN", "econ.TH"],
        # cs and physics have too many subcategories - specify them directly
    }
    
    expanded_categories = []
    if categories:
        for cat in categories:
            if cat in category_map and category_map[cat]:
                expanded_categories.extend(category_map[cat])
            else:
                expanded_categories.append(cat)
    
    # Build keyword filter part
    keyword_query = " OR ".join([
        f'{search_field}:"{f}"' if " " in f else f"{search_field}:{f}"
        for f in filters
    ])
    
    # If no categories specified, return just keyword query
    if not expanded_categories:
        return keyword_query
    
    # Build category filter part
    category_query = " OR ".join([f"cat:{cat}" for cat in expanded_categories])
    
    # Combine: (keywords) AND (categories)
    return f"({keyword_query}) AND ({category_query})"


def parse_papers(results: Generator[Result, None, None]) -> list[Paper]:
    return [Paper(
        date=result.published.date(),
        title=result.title,
        authors=result.authors,
        id=result.get_short_id(),
        url=result.entry_id,
        abstract=result.summary.replace("\n", " ")  # Clean up newlines
    ) for result in results]


def format_paper_entry(paper) -> str:
    """Format a single paper as a clean list entry with collapsible abstract."""
    code_link = f' | [Code]({paper.code})' if paper.code else ''
    return f"""- **{paper.title}**
  - {paper.authors} | [{paper.id}]({paper.url}){code_link}
  - <details><summary>Abstract</summary>{paper.abstract}</details>
"""


def content_to_md(content: dict, file: str):
    now = datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=8))).strftime("%Y/%m/%d %H:%M:%S")

    topic_block = []
    for topic, papers in content.items():
        topic_block.append(Heading(2, topic))
        # Group papers by date
        papers_by_date: dict[str, list] = {}
        for paper in papers:
            date_str = paper.date.strftime("%Y/%m/%d")
            if date_str not in papers_by_date:
                papers_by_date[date_str] = []
            papers_by_date[date_str].append(paper)
        
        # Build content with date headers
        for date_str, date_papers in papers_by_date.items():
            topic_block.append(Heading(3, f"📅 {date_str}"))
            for paper in date_papers:
                topic_block.append(format_paper_entry(paper))

    MdBuilder(
        FrontMatter({
            "layout": "default"
        }),
        Blockquote(f"Updated on {now}"),
        "<summary>Table of Contents</summary>",
        "<ol>",
        '\n'.join([
            f" <li><a href=\"#{topic}\">{topic}</a></li>"
            for topic in list(content.keys())]),
        "</ol>",
        topic_block
    ).write_to_file(file)
