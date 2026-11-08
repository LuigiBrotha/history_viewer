from app.services.translation.argos import Models, split_sentences


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
