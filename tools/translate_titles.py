"""An English title for every Veldslag that is not from the English Wikipedia.

In this order (the user's choice): the title of its English Wikipedia article, found through the
language links (tools.english_names); else its English label on Wikidata; else a translation
made offline by an Argos model. The original title stays the Veldslag's `title`; the English
one goes in `title_en`, with `title_source` "wikipedia", "wikidata" or "vertaald":

    poetry run python -m tools.translate_titles [--battles FILE] [--dir DIR] [--models DIR]

Wikidata is asked 50 titles at a time, at most one request a second, and its answers are kept
in `wikidata-labels.json` next to the dumps, so a second run asks nothing again.
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from tools.english_names import read_names
from tools.extract_battles import DEFAULT_OUTPUT, _write_atomically

DEFAULT_DIR = Path("~/.cache/uboats/wikipedia/other")
DEFAULT_MODELS = Path("~/.cache/uboats/argos")
USER_AGENT = "uboats-battle-extract/1.0"
BATCH = 50
PAUSE_SECONDS = 2.0
RETRIES = 10
# A language whose Wikipedia code is not the code of its Argos model.
MODEL_CODES = {"no": "nb"}


def wikidata_labels(lang, titles, fetch=None):
    """Title → English Wikidata label (None when the item has none), for one language's titles."""
    fetch = fetch or _fetch_json
    found = {}
    titles = list(titles)
    for start in range(0, len(titles), BATCH):
        chunk = titles[start:start + BATCH]
        data = fetch({"action": "wbgetentities", "sites": f"{lang}wiki", "titles": "|".join(chunk),
                      "props": "labels|sitelinks", "languages": "en", "sitefilter": f"{lang}wiki",
                      "format": "json"})
        for entity in (data.get("entities") or {}).values():
            link = (entity.get("sitelinks") or {}).get(f"{lang}wiki")
            if link:
                found[link["title"]] = (entity.get("labels") or {}).get("en", {}).get("value")
        for title in chunk:
            found.setdefault(title, None)
    return found


def _fetch_json(params, url="https://www.wikidata.org/w/api.php", sleep=time.sleep):
    """One API answer. Asked too often (429) or busy (503), it waits as long as the server asks,
    else a minute, and tries again, up to RETRIES times."""
    import urllib.error

    request = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": USER_AGENT})
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            sleep(PAUSE_SECONDS)
            return data
        except urllib.error.HTTPError as error:
            if error.code not in (429, 503) or attempt == RETRIES - 1:
                raise
            wait = error.headers.get("Retry-After", "") if error.headers else ""
            seconds = int(wait) if wait.isdigit() else 60
            print(f"Wikidata: {error.code}, waiting {seconds} s", file=sys.stderr, flush=True)
            sleep(seconds)


def tidy_translation(text):
    """What an Argos model gives, as a title: no word-piece marks, no leading article."""
    text = re.sub(r"\s+", " ", text.replace("▁", " ")).strip()
    text = re.sub(r"^(?:The|A|An) (?=\w)", "", text)
    return text[:1].upper() + text[1:]


class ArgosTranslator:
    """Translates titles into English with the Argos models in `models` (one folder per
    language, as unpacked from translate-<lang>_en-<version>.argosmodel)."""

    def __init__(self, models=DEFAULT_MODELS):
        self.models = Path(models).expanduser()
        self.loaded = {}

    def _model(self, lang):
        # One model in memory at a time: each takes a few hundred MB.
        if lang not in self.loaded:
            self.loaded.clear()
            code = MODEL_CODES.get(lang, lang)
            found = sorted(self.models.glob(f"translate-{code}_en-*/*/model"))
            self.loaded[lang] = _load(found[-1].parent, code) if found else None
        return self.loaded[lang]

    def __call__(self, lang, titles):
        model = self._model(lang)
        if model is None or not titles:
            return {}
        translator, encode, decode = model
        results = translator.translate_batch([encode(t) for t in titles], beam_size=4)
        return {title: tidy_translation(decode(r.hypotheses[0])) for title, r in zip(titles, results)}


def _load(folder, code):
    """(translator, encode, decode) of one unpacked model: SentencePiece, or Moses words split
    by BPE in the older models (cs, fi, hu)."""
    import ctranslate2

    translator = ctranslate2.Translator(str(folder / "model"), device="cpu", compute_type="int8")
    if (folder / "sentencepiece.model").exists():
        import sentencepiece

        pieces = sentencepiece.SentencePieceProcessor(model_file=str(folder / "sentencepiece.model"))
        return translator, lambda text: pieces.encode(text, out_type=str), pieces.decode
    from sacremoses import MosesDetokenizer, MosesPunctNormalizer, MosesTokenizer
    from subword_nmt.apply_bpe import BPE

    normalizer, words, joiner = MosesPunctNormalizer(lang=code), MosesTokenizer(lang=code), MosesDetokenizer(lang="en")
    with open(folder / "bpe.model", encoding="utf-8") as codes:
        bpe = BPE(codes)

    def encode(text):
        return bpe.process_line(" ".join(words.tokenize(normalizer.normalize(text), escape=False))).split()

    def decode(tokens):
        return joiner.detokenize(" ".join(tokens).replace("@@ ", "").split(" "))

    return translator, encode, decode


def english_titles(battles, wikipedia, labels_cache, translate, fetch=None, save=None):
    """Sets title_en and title_source on each Veldslag of another language. `wikipedia` is
    {lang: {title: English article}}, `labels_cache` {"lang|title": label or None} (filled in)."""
    by_lang = {}
    for battle in battles:
        lang = battle.get("lang", "en")
        if lang != "en":
            by_lang.setdefault(lang, []).append(battle)
    for lang, group in by_lang.items():
        unknown = [b["title"] for b in group if b["title"] not in wikipedia.get(lang, {})
                   and f"{lang}|{b['title']}" not in labels_cache]
        if unknown:
            print(f"{lang}: asking Wikidata for {len(unknown)} titles", file=sys.stderr, flush=True)
            for title, label in wikidata_labels(lang, unknown, fetch).items():
                labels_cache[f"{lang}|{title}"] = label
            if save:
                save()
        rest = [b["title"] for b in group if b["title"] not in wikipedia.get(lang, {})
                and not labels_cache.get(f"{lang}|{b['title']}")]
        translated = translate(lang, rest) if rest else {}
        for battle in group:
            title = battle["title"]
            if english := wikipedia.get(lang, {}).get(title):
                battle["title_en"], battle["title_source"] = english, "wikipedia"
            elif label := labels_cache.get(f"{lang}|{title}"):
                battle["title_en"], battle["title_source"] = label, "wikidata"
            elif text := translated.get(title):
                battle["title_en"], battle["title_source"] = text, "vertaald"
            else:
                battle.pop("title_en", None)
                battle.pop("title_source", None)
    return battles


def run(battles_path=DEFAULT_OUTPUT, directory=DEFAULT_DIR, models=DEFAULT_MODELS):
    battles_path = Path(battles_path)
    directory = Path(directory).expanduser()
    cache_path = directory / "wikidata-labels.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    battles = json.loads(battles_path.read_text(encoding="utf-8"))
    def save():
        _write_atomically(cache_path, json.dumps(cache, ensure_ascii=False))

    try:
        english_titles(battles, read_names(directory), cache, ArgosTranslator(models), save=save)
    finally:
        save()
    _write_atomically(battles_path, json.dumps(battles, ensure_ascii=False, separators=(",", ":")))
    counts = {}
    for battle in battles:
        if battle.get("title_source"):
            counts[battle["title_source"]] = counts.get(battle["title_source"], 0) + 1
    print(f"English titles: {counts}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--battles", default=DEFAULT_OUTPUT, help="the battles.json to give English titles")
    parser.add_argument("--dir", default=DEFAULT_DIR, help="directory with the *wiki-names.json files")
    parser.add_argument("--models", default=DEFAULT_MODELS, help="directory with the unpacked Argos models")
    arguments = parser.parse_args(argv)
    run(arguments.battles, arguments.dir, arguments.models)


if __name__ == "__main__":
    main()
