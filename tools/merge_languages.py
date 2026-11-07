"""Merge the Veldslagen of other languages into the English ones.

Only language links decide which articles are the same battle. An English Veldslag keeps
its own position and Winnaar; when it has none, the first language in ORDER that has one
fills it. Linked articles without an English Veldslag become one new Veldslag, named and
described by the first language in ORDER. What another language filled in is remembered in
"filled", so merging again (also with fewer languages) starts from the English values.
"""

import gzip
import re

from tools.wiki_languages import ORDER

_ROW = re.compile(r"\((\d+),'((?:[^'\\]|\\.)*)','((?:[^'\\]|\\.)*)'\)")
_ESCAPE = re.compile(r"\\(.)")


def _unescape(value):
    return _ESCAPE.sub(lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), value)


def read_langlinks(path, page_ids, languages):
    """Page id → {language: title} from a langlinks.sql.gz, for the wanted pages and languages."""
    found = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as lines:
        for line in lines:  # one INSERT per line, or one row per line, depending on the dump
            for page_id, lang, title in _ROW.findall(line):
                page_id = int(page_id)
                if page_id in page_ids and lang in languages:
                    found.setdefault(page_id, {})[lang] = _unescape(title)
    return found


def _english_only(battles):
    """The English Veldslagen as the English Wikipedia gives them, without what was filled in."""
    result = []
    for battle in battles:
        if battle.get("lang", "en") != "en":
            continue
        battle = dict(battle)
        filled = battle.pop("filled", {})
        if "position" in filled:
            battle["lat"] = battle["lng"] = None
        if "winner" in filled:
            battle["winner"] = []
        result.append(battle)
    return result


def _groups(others, links):
    """The other-language articles, grouped by their links to each other, in a stable order."""
    nodes = [(lang, b["title"]) for lang in ORDER for b in others.get(lang, [])]
    known = set(nodes)
    parent = {node: node for node in nodes}

    def root(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for node in nodes:
        for lang, title in links.get(node, {}).items():
            target = (lang, title)
            if target in known:
                parent[root(target)] = root(node)
    groups = {}
    for node in nodes:
        groups.setdefault(root(node), []).append(node)
    return list(groups.values())


def merge_languages(battles, others, links):
    """English Veldslagen with gaps filled from other languages, followed by the new Veldslagen.

    battles: the records of battles.json; others: language → records of that language;
    links: (language, title) → {language: title} of its language links."""
    english = _english_only(battles)
    by_title = {b["title"]: b for b in english}
    records = {(lang, b["title"]): b for lang in ORDER for b in others.get(lang, [])}
    new = []
    for group in _groups(others, links):
        group.sort(key=lambda node: ORDER.index(node[0]))
        target = next((links.get(node, {}).get("en") for node in group
                       if links.get(node, {}).get("en") in by_title), None)
        members = [records[node] for node in group]
        if target is not None:
            battle = by_title[target]
            filled = {}
            if battle.get("lat") is None or battle.get("lng") is None:
                source = next((m for m in members if m.get("lat") is not None and m.get("lng") is not None), None)
                if source is not None:
                    battle["lat"], battle["lng"] = source["lat"], source["lng"]
                    filled["position"] = source["lang"]
            if not battle.get("winner"):
                source = next((m for m in members if m.get("winner")), None)
                if source is not None:
                    battle["winner"] = source["winner"]
                    filled["winner"] = source["lang"]
            if filled:
                battle["filled"] = filled
            continue
        record = dict(members[0])
        if record.get("lat") is None or record.get("lng") is None:
            source = next((m for m in members if m.get("lat") is not None and m.get("lng") is not None), None)
            if source is not None:
                record["lat"], record["lng"] = source["lat"], source["lng"]
        if not record.get("winner"):
            record["winner"] = next((m["winner"] for m in members if m.get("winner")), [])
        new.append(record)
    new.sort(key=lambda b: (b["start"], b["title"]))
    return english + new
