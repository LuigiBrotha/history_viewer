"""Offline translation with the Argos models, through ctranslate2 (group `translate`).

Each model is a folder translate-<from>_<to>-<version> as unpacked from its .argosmodel; the
newer ones split words with SentencePiece, the older ones (cs, fi, hu) with Moses and BPE.
Argos has models into and out of English, so another language reaches Dutch through English.
"""

import re
import threading
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path

DEFAULT_MODELS = Path("~/.cache/uboats/argos")
# A language whose Wikipedia code is not the code of its Argos model.
MODEL_CODES = {"no": "nb"}
LOADED = 2  # models kept in memory; each takes a few hundred MB
MAX_PIECE = 400  # characters; longer sentences are cut at a semicolon or comma
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=\S)|(?<=[。！？])")
DASH = re.compile(r"[–—]")
CUT = re.compile(r"(?<=[;,，、])\s*")


def split_sentences(text: str) -> list[str]:
    """The sentences of a text, none longer than MAX_PIECE where a comma allows it."""
    pieces = []
    for sentence in SENTENCE.split(text):
        if not sentence.strip():
            continue
        while len(sentence) > MAX_PIECE:
            cuts = [m.end() for m in CUT.finditer(sentence, 0, MAX_PIECE) if m.end() > MAX_PIECE // 4]
            if not cuts:
                break
            pieces.append(sentence[: cuts[-1]].strip())
            sentence = sentence[cuts[-1]:]
        pieces.append(sentence.strip())
    return pieces


class Models:
    """The Argos models in one folder, loaded when first used, at most LOADED at a time."""

    def __init__(self, folder=DEFAULT_MODELS):
        self.folder = Path(folder).expanduser()
        self._loaded = OrderedDict()
        self._lock = threading.Lock()

    def _path(self, source, target):
        source, target = MODEL_CODES.get(source, source), MODEL_CODES.get(target, target)
        found = sorted(self.folder.glob(f"translate-{source}_{target}-*/*/model"))
        return found[-1].parent if found else None

    def has(self, source: str, target: str) -> bool:
        return self._path(source, target) is not None

    def can_reach_dutch(self, lang: str) -> bool:
        if lang == "nl":
            return False
        return self.has("en", "nl") and (lang == "en" or self.has(lang, "en"))

    def translate(self, source: str, target: str, texts: Sequence[str]) -> list[str]:
        """Each text translated, sentence by sentence; the texts themselves when there is no model."""
        if not texts:
            return []
        with self._lock:
            model = self._model(source, target)
            if model is None:
                return list(texts)
            translator, encode, decode = model
            pieces = [split_sentences(text) for text in texts]
            flat = [p for ps in pieces for p in ps]
            results = translator.translate_batch([encode(p) for p in flat], beam_size=2, max_batch_size=32)
        out = iter(_clean(decode(r.hypotheses[0])) for r in results)
        joiner = "" if target in ("ja", "zh") else " "
        return [joiner.join(next(out) for _ in ps) for ps in pieces]

    def to_dutch(self, lang: str, texts: Sequence[str]) -> list[str]:
        """Texts of a language in Dutch; other languages than English go through English. The
        models drop dashes (1–7 September became 17 september), so they go in as hyphens and
        come out as dashes again."""
        texts = [DASH.sub("-", text) for text in texts]
        if lang != "en":
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

    translator = ctranslate2.Translator(str(folder / "model"), device="cpu", compute_type="int8", intra_threads=4)
    if (folder / "sentencepiece.model").exists():
        import sentencepiece

        pieces = sentencepiece.SentencePieceProcessor(model_file=str(folder / "sentencepiece.model"))
        return translator, lambda text: pieces.encode(text, out_type=str), pieces.decode
    from sacremoses import MosesDetokenizer, MosesPunctNormalizer, MosesTokenizer
    from subword_nmt.apply_bpe import BPE

    normalizer, words, joiner = MosesPunctNormalizer(lang=source), MosesTokenizer(lang=source), MosesDetokenizer(lang=target)
    with open(folder / "bpe.model", encoding="utf-8") as codes:
        bpe = BPE(codes)

    def encode(text):
        return bpe.process_line(" ".join(words.tokenize(normalizer.normalize(text), escape=False))).split()

    def decode(tokens):
        return joiner.detokenize(" ".join(tokens).replace("@@ ", "").split(" "))

    return translator, encode, decode
