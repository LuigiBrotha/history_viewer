from app.services.translation.argos import NLLB_FOLDER, Models, nllb_code, nllb_text, split_sentences


def test_nllb_serves_the_languages_argos_has_no_model_for(tmp_path):
    (tmp_path / "translate-en_nl-1_8" / "inner" / "model").mkdir(parents=True)
    (tmp_path / NLLB_FOLDER).mkdir()
    (tmp_path / NLLB_FOLDER / "model.bin").touch()
    models = Models(tmp_path)
    for lang in ("be", "sr", "sh", "mk", "lij"):
        assert models.has(lang, "en") and models.can_reach_dutch(lang)
    assert not models.has("en", "be")  # only into English
    assert not models.has("ko", "en")


def test_nllb_goes_before_a_bad_argos_model(tmp_path):
    (tmp_path / "translate-uk_en-1_9" / "inner" / "model").mkdir(parents=True)
    (tmp_path / NLLB_FOLDER).mkdir()
    (tmp_path / NLLB_FOLDER / "model.bin").touch()
    assert Models(tmp_path)._path("uk", "en").name == NLLB_FOLDER


def test_simple_english_needs_only_the_english_model(tmp_path):
    (tmp_path / "translate-en_nl-1_8" / "inner" / "model").mkdir(parents=True)
    assert Models(tmp_path).can_reach_dutch("simple")


def test_serbo_croatian_is_read_in_the_script_it_is_written_in():
    assert nllb_code("sh", "Borbe za Čazmu vođene su juna 1944.") == "hrv_Latn"
    assert nllb_code("sh", "Борбе за Чазму") == "srp_Cyrl"
    assert nllb_code("sr", "Битка за Ивањицу (Ivanjica)") == "srp_Cyrl"
    assert nllb_code("be", "Абарона Мінска") == "bel_Cyrl"


def test_marks_nllb_does_not_know_are_made_plain():
    assert nllb_text("Аперацыя «Іваноў» — назва „х“") == 'Аперацыя "Іваноў" - назва "х"'


def test_sentences_are_split_and_long_ones_cut_at_a_comma():
    assert split_sentences("One thing. Another one! Last?") == ["One thing.", "Another one!", "Last?"]
    assert split_sentences("戦いが始まった。日本軍は退いた。") == ["戦いが始まった。", "日本軍は退いた。"]
    long = ", ".join(["word " * 20] * 6)
    pieces = split_sentences(long)
    assert len(pieces) > 1 and all(len(p) <= 400 for p in pieces)
    assert " ".join(pieces).split() == long.split()


def test_which_languages_reach_dutch(tmp_path):
    for name in ("translate-en_nl-1_8", "translate-ru_en-1_9", "translate-nb_en-1_9"):
        (tmp_path / name / "inner" / "model").mkdir(parents=True)
    models = Models(tmp_path)
    assert models.can_reach_dutch("en") and models.can_reach_dutch("ru") and models.can_reach_dutch("no")
    assert not models.can_reach_dutch("be")
    assert not models.can_reach_dutch("nl")


def test_without_a_model_the_texts_come_back_as_they_were(tmp_path):
    assert Models(tmp_path).translate("be", "en", ["Бітва"]) == ["Бітва"]


from app.services.translation.argos import restore_dashes


def test_dashes_come_back_between_numbers_and_spaced():
    assert restore_dashes("1-7 september 1939") == "1–7 september 1939"
    assert restore_dashes("5 juli 1943 - 23 augustus 1943") == "5 juli 1943 – 23 augustus 1943"
    assert restore_dashes("Sovjet-Unie") == "Sovjet-Unie"
