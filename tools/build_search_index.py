"""Builds the index behind the search field of the column Onderwerpen.

    poetry run python -m tools.build_search_index [--battles FILE] [--database FILE] [--output FILE]

Run it again after new articles or translations came in. The app keeps using the old index
until the new one is complete.
"""

import argparse
import json
from pathlib import Path

from app.services.search.index import INDEX_NAME, build_index
from tools.extract_battles import DEFAULT_OUTPUT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--battles", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--database", type=Path, default=Path("uboats.db"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    database = args.database.resolve()
    output = args.output or database.with_name(INDEX_NAME)
    count = build_index(database, json.loads(args.battles.read_text(encoding="utf-8")), output)
    print(f"{count} texts in {output}")


if __name__ == "__main__":
    main()
