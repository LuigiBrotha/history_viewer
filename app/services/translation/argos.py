"""Offline translation with the Argos models, through ctranslate2 (group `translate`).

Each model is a folder translate-<from>_<to>-<version> as unpacked from its .argosmodel; the
newer ones split words with SentencePiece, the older ones (cs, fi, hu) with Moses and BPE.
Argos has models into and out of English, so another language reaches Dutch through English.

Languages Argos has no model or only a bad one for (NLLB_CODES) go into English with NLLB-200, in the folder NLLB_FOLDER next to the Argos models. Its licence is
CC BY-NC 4.0: fine for this private app, not for commercial use.
"""

import re
import threading
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path

DEFAULT_MODELS = Path("~/.cache/uboats/argos")
# A language whose Wikipedia code is not the code of its Argos model.
MODEL_CODES = {"no": "nb"}
ENGLISH = ("en", "simple")  # Simple English needs no translation into English
NLLB_FOLDER = "nllb-200-distilled-1.3B"
# Argos has no model for the first five; for the others NLLB is clearly better on real articles
# (the Spanish Argos model only repeats itself, the Ukrainian one invents names).
NLLB_CODES = {
    "be": "bel_Cyrl", "sr": "srp_Cyrl", "sh": "hrv_Latn", "mk": "mkd_Cyrl", "lij": "lij_Latn",
    "uk": "ukr_Cyrl", "zh": "zho_Hans", "es": "spa_Latn", "lt": "lit_Latn",
}
NLLB_TARGET = "eng_Latn"
NLLB_QUOTES = re.compile(r"[«»„“”]")
NLLB_DASHES = re.compile(r"[–—]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
LOADED = 2  # models kept in memory; an Argos model takes a few hundred MB, NLLB about 1.4 GB
MAX_PIECE = 400  # characters; longer sentences are cut at a semicolon or comma
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=\S)|(?<=[。！？])")
DASH = re.compile(r"[–—]")
INITIAL = re.compile(r"(?:^|[\s(.\"«])[^\W\d_]\.$")
CUT = re.compile(r"(?<=[;,，、])\s*")


def split_sentences(text: str) -> list[str]:
    """The sentences of a text, none longer than MAX_PIECE where a comma allows it."""
    pieces = []
    for sentence in _whole_sentences(SENTENCE.split(text)):
        while len(sentence) > MAX_PIECE:
            cuts = [m.end() for m in CUT.finditer(sentence, 0, MAX_PIECE) if m.end() > MAX_PIECE // 4]
            if not cuts:
                break
            pieces.append(sentence[: cuts[-1]].strip())
            sentence = sentence[cuts[-1]:]
        pieces.append(sentence.strip())
    return pieces


def _whole_sentences(parts):
    """The parts, joined again where one ends in a single letter and a stop: an initial ("K. E.
    Voroshilov") or an abbreviation ("1941 г."), not the end of a sentence."""
    joined = []
    for part in parts:
        if not part.strip():
            continue
        if joined and INITIAL.search(joined[-1]):
            joined[-1] = f"{joined[-1]} {part}"
        else:
            joined.append(part)
    return joined


def nllb_code(lang: str, text: str) -> str:
    """NLLB's name for a language. Serbian and Serbo-Croatian are written in either script."""
    if lang in ("sr", "sh"):
        return "srp_Cyrl" if len(CYRILLIC.findall(text)) > len(LATIN.findall(text)) else "hrv_Latn"
    return NLLB_CODES[lang]


def nllb_text(text: str) -> str:
    """The text without the quotes and dashes NLLB would answer with an unknown-word mark."""
    return NLLB_DASHES.sub("-", NLLB_QUOTES.sub('"', text))


class Models:
    """The Argos models in one folder, loaded when first used, at most LOADED at a time."""

    def __init__(self, folder=DEFAULT_MODELS):
        self.folder = Path(folder).expanduser()
        self._loaded = OrderedDict()
        self._lock = threading.Lock()

    def _path(self, source, target):
        source, target = MODEL_CODES.get(source, source), MODEL_CODES.get(target, target)
        nllb = self.folder / NLLB_FOLDER
        if source in NLLB_CODES and target == "en" and (nllb / "model.bin").exists():
            return nllb
        found = sorted(self.folder.glob(f"translate-{source}_{target}-*/*/model"))
        return found[-1].parent if found else None

    def has(self, source: str, target: str) -> bool:
        return self._path(source, target) is not None

    def can_reach_dutch(self, lang: str) -> bool:
        if lang == "nl":
            return False
        return self.has("en", "nl") and (lang in ENGLISH or self.has(lang, "en"))

    def translate(self, source: str, target: str, texts: Sequence[str]) -> list[str]:
        """Each text translated, sentence by sentence; the texts themselves when there is no model."""
        if not texts:
            return []
        with self._lock:
            model = self._model(source, target)
            if model is None:
                return list(texts)
            translator, encode, decode, options = model
            pieces = [split_sentences(text) for text in texts]
            flat = [p for ps in pieces for p in ps]
            options = options(len(flat)) if callable(options) else options
            results = translator.translate_batch([encode(p) for p in flat], **options)
        out = iter(_clean(decode(r.hypotheses[0])) for r in results)
        joiner = "" if target in ("ja", "zh") else " "
        return [joiner.join(next(out) for _ in ps) for ps in pieces]

    def to_dutch(self, lang: str, texts: Sequence[str]) -> list[str]:
        """Texts of a language in Dutch; other languages than English go through English. The
        models drop dashes (1–7 September became 17 september), so they go in as hyphens and
        come out as dashes again."""
        texts = [DASH.sub("-", text) for text in texts]
        if lang not in ENGLISH:
            texts = self.translate(lang, "en", texts)
        return [restore_dashes(text) for text in self.translate("en", "nl", texts)]

    def _model(self, source, target):
        key = (source, target)
        if key in self._loaded:
            self._loaded.move_to_end(key)
            return self._loaded[key]
        path = self._path(source, target)
        if path is None:
            return None
        while len(self._loaded) >= LOADED:
            self._loaded.popitem(last=False)
        self._loaded[key] = _load(path, MODEL_CODES.get(source, source), target)
        return self._loaded[key]


def restore_dashes(text: str) -> str:
    """A spaced hyphen, or one between numbers, as a dash."""
    return re.sub(r"(?<=\d)-(?=\d)", "–", text.replace(" - ", " – "))


def _clean(text):
    return re.sub(r"\s+", " ", text.replace("▁", " ")).strip()


def _load(folder, source, target):
    """(translator, encode, decode) of one unpacked model."""
    import ctranslate2

    if folder.name == NLLB_FOLDER:
        return _load_nllb(folder, source)
    translator = ctranslate2.Translator(str(folder / "model"), device="cpu", compute_type="int8", intra_threads=4)
    options = {"beam_size": 2, "max_batch_size": 32}
    if (folder / "sentencepiece.model").exists():
        import sentencepiece

        pieces = sentencepiece.SentencePieceProcessor(model_file=str(folder / "sentencepiece.model"))
        return translator, lambda text: pieces.encode(text, out_type=str), pieces.decode, options
    from sacremoses import MosesDetokenizer, MosesPunctNormalizer, MosesTokenizer
    from subword_nmt.apply_bpe import BPE

    normalizer, words, joiner = MosesPunctNormalizer(lang=source), MosesTokenizer(lang=source), MosesDetokenizer(lang=target)
    with open(folder / "bpe.model", encoding="utf-8") as codes:
        bpe = BPE(codes)

    def encode(text):
        return bpe.process_line(" ".join(words.tokenize(normalizer.normalize(text), escape=False))).split()

    def decode(tokens):
        return joiner.detokenize(" ".join(tokens).replace("@@ ", "").split(" "))

    return translator, encode, decode, options


def _load_nllb(folder, source):
    """(translator, encode, decode, options) of NLLB-200: each sentence starts with its language,
    each answer with the language asked for."""
    import ctranslate2
    import sentencepiece

    translator = ctranslate2.Translator(str(folder), device="cpu", compute_type="int8", intra_threads=4)
    pieces = sentencepiece.SentencePieceProcessor(model_file=str(folder / "sentencepiece.bpe.model"))

    def encode(text):
        return [nllb_code(source, text), *pieces.encode(nllb_text(text), out_type=str), "</s>"]

    def decode(tokens):
        return pieces.decode(tokens[1:]).replace("⁇", "")

    def options(count):
        return {"beam_size": 4, "max_batch_size": 8, "target_prefix": [[NLLB_TARGET]] * count}

    return translator, encode, decode, options
