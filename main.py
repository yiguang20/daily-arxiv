import arxiv

from utils import Paper, config, content_to_md, log, parse_papers, concat_filters

max_results = config["max_results"]

# get papers from arxiv via arxiv api
client = arxiv.Client()

content: dict[str, list[Paper]] = {}
for k in config["topics"]:
    topic: str = k["name"]
    categories = k.get("categories", [])

    log(f"Query topic {topic}" + (f" in categories {categories}" if categories else ""))
    content[topic] = parse_papers(client.results(arxiv.Search(
        query=concat_filters(k["filters"], categories if categories else None),
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )))
    content[topic].sort(reverse=True)

    if len(content[topic]) == 0:
        log(f"Warning: No papers found for topic '{topic}'")
        continue

    log(f"Get code link of {topic}")
    for paper in content[topic]:
        paper.get_code_link()

# Filter out empty topics and write to markdown
content = {k: v for k, v in content.items() if v}

if content:
    content_to_md(content, config["file_path"])
    log(f"Successfully wrote {len(content)} topics to {config['file_path']}")
else:
    log("Warning: No papers found for any topic. Markdown file not updated.")
