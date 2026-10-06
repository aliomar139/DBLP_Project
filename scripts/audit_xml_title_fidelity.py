"""Count title child nodes the current findtext-based importer can omit."""
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]


def inspect(xml):
    start = perf_counter()
    total = child_titles = empty_prefixes = 0
    context = etree.iterparse(str(xml), events=("end",),
        tag=("article", "inproceedings", "proceedings", "book", "incollection", "phdthesis", "mastersthesis"),
        load_dtd=False, resolve_entities=False, no_network=True)
    for _, elem in context:
        total += 1
        title = elem.find("title")
        if title is not None and len(title):
            child_titles += 1
            if not (elem.findtext("title") or "").strip():
                empty_prefixes += 1
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    return {"audit": "full supported XML records, unresolved entities, title child-node loss risk",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": total, "titles_with_child_nodes": child_titles,
        "child_node_titles_with_empty_stored_prefix": empty_prefixes,
        "seconds": perf_counter()-start, "database_modified": False,
        "qualification": "Structural extraction-risk count; not a repaired-title comparison"}


if __name__ == "__main__":
    result = inspect(ROOT / "data/dblp.xml")
    output = ROOT / "reports/assistant/xml-title-fidelity-v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))
