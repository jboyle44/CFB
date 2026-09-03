"""
Builds draft_prospects.json from Tankathon's NFL Draft Big Board.

Usage: python build_draft_prospects.py [output_path]
"""
import sys
import json
import datetime

from scrape_tankathon import scrape_big_board


def build(output_path=None):
    prospects = scrape_big_board()

    wrapped = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "prospects": prospects,
    }

    if output_path:
        with open(output_path, "w") as f:
            json.dump(wrapped, f, indent=2)
        print(f"Wrote {len(prospects)} prospects to {output_path}", file=sys.stderr)

    return wrapped


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "draft_prospects.json"
    build(out_path)
