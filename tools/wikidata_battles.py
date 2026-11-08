"""Veldslagen of every other Wikipedia, through Wikidata.

Writing rules per language, as for nl/de/pl/ru/fr/it/ja, does not scale to the rest, so for
every other language the battle items of Wikidata are used: each knows its dates, often its
coordinates or its location, its participants and winner, and its article in every language.

    poetry run python -m tools.wikidata_battles [--battles FILE] [--database URL]

1. All items that are a battle, military operation, siege or naval battle are found through
   the search API (haswbstatement), and fetched 50 at a time; what was fetched is kept in
   battles.json under ~/.cache/uboats/wikidata, so a stopped run goes on where it was.
2. The locations, participants and winners they name are fetched too, for their coordinates
   and English titles (a participant's English title gives its Land, as tools.countries knows it).
3. Items during the war are merged into battles.json: one that is already a Veldslag (its English
   article, or its article in one of the languages read from their dumps) only fills a missing
   position or Winnaar, last in the order of languages. Any other item becomes a new Veldslag,
   named after its article in the first language of WIKI_ORDER that has one, whose wikitext is
   fetched and stored so that the Artikel can be shown.

Wikidata is asked at most one request every two seconds; told to wait (429), it waits.
"""

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.services.storage.models import ForeignBattleArticle
from tools.countries import COUNTRY_KAMP, land_of
from tools.extract_battles import DEFAULT_DATABASE, DEFAULT_OUTPUT, WAR_END, WAR_START, _write_atomically
from tools.translate_titles import _fetch_json
from tools.wiki_languages import ORDER, wiki_url

CACHE = Path("~/.cache/uboats/wikidata/battles.json")
API = "https://www.wikidata.org/w/api.php"
BATCH = 50
# Battle, military operation, siege, naval battle. The battles are split by coordinates, as one
# search gives at most 10,000 results.
SEARCHES = (
    "haswbstatement:P31=Q178561 haswbstatement:P625",
    "haswbstatement:P31=Q178561 -haswbstatement:P625",
    "haswbstatement:P31=Q645883",
    "haswbstatement:P31=Q188055",
    "haswbstatement:P31=Q1261499",
)
# After English and the languages read from their dumps, the Wikipedias whose article names a new
# Veldslag, roughly by their size; any other comes after these, alphabetically.
WIKI_ORDER = ("en", *ORDER, "uk", "es", "pt", "sv", "cs", "zh", "fi", "hu", "sr", "sh", "hr", "ro", "he", "el",
              "bg", "no", "da", "sk", "lt", "lv", "et", "ko", "tr", "be", "kk", "ca", "id", "vi", "ar", "fa", "sl")
PRECISION = {11: "day", 10: "month", 9: "year"}


def _claims(entity, prop):
    return [c["mainsnak"].get("datavalue", {}).get("value") for c in entity.get("claims", {}).get(prop, [])
            if c.get("mainsnak", {}).get("snaktype") == "value"]


def _time(value):
    """(date, precision) of a Wikidata time value; None for one that is not a usable date."""
    if not value or not value.get("time", "").startswith("+"):
        return None
    year, month, day = value["time"][1:11].split("-")
    precision = PRECISION.get(value.get("precision"))
    if precision is None:
        return None
    try:
        return date(int(year), max(1, int(month)), max(1, int(day))), precision
    except ValueError:
        return None


def _end_of(day, precision):
    if precision == "year":
        return date(day.year, 12, 31)
    if precision == "month":
        following = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
        return date.fromordinal(following.toordinal() - 1)
    return day


def parse_item(entity):
    """What a battle item says, or None when it has no date: {"qid", "start", "end", "precision",
    "coord", "locations", "participants", "winners", "sitelinks", "label_en"}."""
    start = _time(next(iter(_claims(entity, "P580")), None)) or _time(next(iter(_claims(entity, "P585")), None))
    if start is None:
        return None
    end = _time(next(iter(_claims(entity, "P582")), None)) or start
    coord = next((v for v in _claims(entity, "P625") if v and v.get("globe", "").endswith("Q2")), None)
    return {
        "qid": entity["id"],
        "start": start[0].isoformat(),
        "end": max(_end_of(*end), start[0]).isoformat(),
        "precision": start[1],
        "coord": [coord["latitude"], coord["longitude"]] if coord else None,
        "locations": [v["id"] for v in _claims(entity, "P276") if v],
        "participants": [v["id"] for v in _claims(entity, "P710") if v],
        "winners": [v["id"] for v in _claims(entity, "P1346") if v],
        "sitelinks": {site: link["title"] for site, link in entity.get("sitelinks", {}).items()
                      if site.endswith("wiki") and site not in ("commonswiki", "specieswiki", "metawiki")},
        "label_en": entity.get("labels", {}).get("en", {}).get("value"),
    }


def during_the_war(item):
    return date.fromisoformat(item["end"]) >= WAR_START and date.fromisoformat(item["start"]) <= WAR_END


def _wiki_lang(site):
    return site[:-4].replace("_", "-")


def chosen_article(sitelinks):
    """(lang, title) of the article that names a new Veldslag: the first language of WIKI_ORDER
    that has one, else the first other language alphabetically; None without any."""
    by_lang = {_wiki_lang(site): title for site, title in sitelinks.items()}
    for lang in WIKI_ORDER:
        if lang in by_lang:
            return lang, by_lang[lang]
    if by_lang:
        lang = sorted(by_lang)[0]
        return lang, by_lang[lang]
    return None


def kamp_of(qids, names):
    """The Kampen of the given items (winners), through the Land of their English title."""
    kampen = []
    for qid in qids:
        land = land_of(names.get(qid, "")) if names.get(qid) else None
        kamp = COUNTRY_KAMP.get(land) if land else None
        if kamp and kamp not in kampen:
            kampen.append(kamp)
    return kampen


def lands_of(qids, names):
    lands = []
    for qid in qids:
        land = land_of(names.get(qid, "")) if names.get(qid) else None
        if land and land not in lands:
            lands.append(land)
    return lands


def merge_wikidata(battles, items, owners, positions, names):
    """battles.json with the war's Wikidata items merged in (see the module's docstring).

    owners: {(lang, title): Veldslag title} of the articles read from dumps; positions:
    {qid: (lat, lng)} of locations; names: {qid: English title or label} of participants and
    winners. Returns (battles, new): new = [(lang, title)] of the articles to fetch."""
    by_title = {b["title"]: b for b in battles}
    new = []
    for item in items:
        if not during_the_war(item):
            continue
        known = None
        for site, title in item["sitelinks"].items():
            lang = _wiki_lang(site)
            if lang == "en" and title in by_title and by_title[title].get("lang", "en") == "en":
                known = by_title[title]
            elif (lang, title) in owners and owners[(lang, title)] in by_title:
                known = by_title[owners[(lang, title)]]
            if known:
                break
        position = item["coord"] or next((positions[q] for q in item["locations"] if q in positions), None)
        winner = kamp_of(item["winners"], names)
        if known:
            known["wikidata"] = item["qid"]
            filled = known.setdefault("filled", {})
            if (known.get("lat") is None or known.get("lng") is None) and position:
                known["lat"], known["lng"] = position
                filled["position"] = "wikidata"
            if not known.get("winner") and winner:
                known["winner"] = winner
                filled["winner"] = "wikidata"
            if not filled:
                known.pop("filled")
            continue
        chosen = chosen_article(item["sitelinks"])
        if chosen is None:
            continue
        lang, title = chosen
        if title in by_title:
            continue
        record = {
            "title": title,
            "url": wiki_url(lang, title),
            "start": item["start"],
            "end": item["end"],
            "precision": item["precision"],
            "date_text": item["start"] if item["start"] == item["end"] else f"{item['start']} – {item['end']}",
            "lat": position[0] if position else None,
            "lng": position[1] if position else None,
            "part_of": None,
            "place": next((names.get(q) for q in item["locations"] if names.get(q)), None),
            "winner": winner,
            "lang": lang,
            "wikidata": item["qid"],
            "countries": lands_of(item["participants"], names),
        }
        if item.get("label_en") and lang != "en":
            record["title_en"], record["title_source"] = item["label_en"], "wikidata"
        battles.append(record)
        by_title[title] = record
        new.append((lang, title))
    return battles, new


def _entities(ids, props, fetch):
    found = {}
    ids = list(ids)
    for start in range(0, len(ids), BATCH):
        data = fetch({"action": "wbgetentities", "ids": "|".join(ids[start:start + BATCH]), "props": props,
                      "languages": "en", "format": "json"}, API)
        found.update(data.get("entities", {}))
    return found


def search_ids(fetch):
    ids = set()
    for query in SEARCHES:
        offset = 0
        while offset is not None and offset < 10_000:
            data = fetch({"action": "query", "list": "search", "srsearch": query, "srnamespace": 0, "srlimit": 500,
                          "sroffset": offset, "srprop": "", "format": "json"}, API)
            ids.update(hit["title"] for hit in data.get("query", {}).get("search", []))
            offset = data.get("continue", {}).get("sroffset")
        print(f"{query}: {len(ids)} items so far", file=sys.stderr, flush=True)
    return sorted(ids)


def collect(cache_path=CACHE, fetch=_fetch_json):
    """The battle items, their locations' positions and their participants' names; resumable."""
    cache_path = Path(cache_path).expanduser()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    save = lambda: _write_atomically(cache_path, json.dumps(state, ensure_ascii=False))  # noqa: E731
    if "ids" not in state:
        state["ids"] = search_ids(fetch)
        save()
    state.setdefault("items", {})
    todo = [qid for qid in state["ids"] if qid not in state["items"]]
    for start in range(0, len(todo), BATCH):
        chunk = todo[start:start + BATCH]
        for qid, entity in _entities(chunk, "claims|sitelinks|labels", fetch).items():
            state["items"][qid] = parse_item(entity) if "missing" not in entity else None
        for qid in chunk:
            state["items"].setdefault(qid, None)
        save()
        print(f"items: {len(state['items'])} of {len(state['ids'])}", file=sys.stderr, flush=True)
    war = [item for item in state["items"].values() if item and during_the_war(item)]
    linked = {q for item in war for q in item["locations"] + item["participants"] + item["winners"]}
    state.setdefault("linked", {})
    todo = sorted(linked - set(state["linked"]))
    for start in range(0, len(todo), BATCH):
        chunk = todo[start:start + BATCH]
        for qid, entity in _entities(chunk, "claims|sitelinks|labels", fetch).items():
            coord = next((v for v in _claims(entity, "P625") if v and v.get("globe", "").endswith("Q2")), None)
            state["linked"][qid] = {
                "name": entity.get("sitelinks", {}).get("enwiki", {}).get("title")
                or entity.get("labels", {}).get("en", {}).get("value"),
                "coord": [coord["latitude"], coord["longitude"]] if coord else None,
            }
        for qid in chunk:
            state["linked"].setdefault(qid, {"name": None, "coord": None})
        save()
    return state


def fetch_wikitexts(pages, fetch=_fetch_json):
    """{(lang, title): wikitext} of the given articles, 50 at a time per language."""
    by_lang = {}
    for lang, title in pages:
        by_lang.setdefault(lang, []).append(title)
    found = {}
    for lang, titles in by_lang.items():
        for start in range(0, len(titles), BATCH):
            chunk = titles[start:start + BATCH]
            data = fetch({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                          "titles": "|".join(chunk), "format": "json", "formatversion": "2"},
                         f"https://{lang}.wikipedia.org/w/api.php")
            for page in data.get("query", {}).get("pages", []):
                revisions = page.get("revisions")
                if revisions:
                    found[(lang, page["title"])] = revisions[0]["slots"]["main"]["content"]
    return found


def run(battles_path=DEFAULT_OUTPUT, database_url=DEFAULT_DATABASE, cache_path=CACHE):
    state = collect(cache_path)
    battles_path = Path(battles_path)
    battles = json.loads(battles_path.read_text(encoding="utf-8"))
    engine = create_engine(database_url)
    with Session(engine) as session:
        owners = {(lang, title): battle for lang, title, battle in session.execute(
            select(ForeignBattleArticle.lang, ForeignBattleArticle.title, ForeignBattleArticle.battle)).all() if battle}
    items = [item for item in state["items"].values() if item]
    positions = {qid: tuple(v["coord"]) for qid, v in state["linked"].items() if v["coord"]}
    names = {qid: v["name"] for qid, v in state["linked"].items() if v["name"]}
    before = len(battles)
    battles, new = merge_wikidata(battles, items, owners, positions, names)
    texts = fetch_wikitexts([(lang, title) for lang, title in new if lang != "en"])
    now = datetime.now(timezone.utc)
    with Session(engine) as session, session.begin():
        for (lang, title), wikitext in texts.items():
            session.merge(ForeignBattleArticle(lang=lang, title=title, battle=title, wikitext=wikitext,
                                               dump_name="wikipedia api", extracted_at=now))
    engine.dispose()
    _write_atomically(battles_path, json.dumps(battles, ensure_ascii=False, separators=(",", ":")))
    filled = sum(1 for b in battles if any(v == "wikidata" for v in (b.get("filled") or {}).values()))
    print(f"{len(battles)} Veldslagen: {len(battles) - before} new from Wikidata ({len(texts)} articles stored), "
          f"{filled} filled in from Wikidata")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--battles", default=DEFAULT_OUTPUT, help="the battles.json to merge into")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database that receives the articles (an SQLite URL)")
    arguments = parser.parse_args(argv)
    run(arguments.battles, arguments.database)


if __name__ == "__main__":
    main()
