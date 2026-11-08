from tools.translate_titles import english_titles, tidy_translation, wikidata_labels


def test_tidy_translation_drops_word_piece_marks_and_a_leading_article():
    assert tidy_translation("The▁Battle of Krosno") == "Battle of Krosno"
    assert tidy_translation("▁Westerplatte▁Defense") == "Westerplatte Defense"
    assert tidy_translation("The Battle of Rzhev") == "Battle of Rzhev"
    assert tidy_translation("The siege of Budapest") == "Siege of Budapest"


def test_wikidata_labels_maps_each_title_back_through_its_sitelink():
    asked = []

    def fetch(params):
        asked.append(params)
        return {"entities": {
            "Q1": {"sitelinks": {"plwiki": {"title": "Bitwa o Krosno"}}, "labels": {"en": {"value": "Battle of Krosno"}}},
            "Q2": {"sitelinks": {"plwiki": {"title": "Bój pod Pęcicami"}}, "labels": {}},
            "-1": {"missing": ""},
        }}

    found = wikidata_labels("pl", ["Bitwa o Krosno", "Bój pod Pęcicami", "Nie ma"], fetch)
    assert found == {"Bitwa o Krosno": "Battle of Krosno", "Bój pod Pęcicami": None, "Nie ma": None}
    assert asked[0]["sites"] == "plwiki" and asked[0]["titles"] == "Bitwa o Krosno|Bój pod Pęcicami|Nie ma"


def test_english_titles_prefers_wikipedia_then_wikidata_then_a_translation():
    battles = [
        {"title": "Battle of Kursk"},
        {"title": "Сталинградская битва", "lang": "ru"},
        {"title": "Ржевская битва", "lang": "ru"},
        {"title": "Бой за Гродно", "lang": "ru"},
        {"title": "Безымянный бой", "lang": "ru"},
    ]
    cache = {"ru|Безымянный бой": None}
    fetched = []

    def fetch(params):
        fetched.append(params["titles"])
        return {"entities": {"Q5": {"sitelinks": {"ruwiki": {"title": "Ржевская битва"}},
                                    "labels": {"en": {"value": "Battles of Rzhev"}}}}}

    def translate(lang, titles):
        return {"Бой за Гродно": "Battle of Grodno"} if lang == "ru" else {}

    english_titles(battles, {"ru": {"Сталинградская битва": "Battle of Stalingrad"}}, cache, translate, fetch)
    assert "title_en" not in battles[0]
    assert (battles[1]["title_en"], battles[1]["title_source"]) == ("Battle of Stalingrad", "wikipedia")
    assert (battles[2]["title_en"], battles[2]["title_source"]) == ("Battles of Rzhev", "wikidata")
    assert (battles[3]["title_en"], battles[3]["title_source"]) == ("Battle of Grodno", "vertaald")
    assert "title_en" not in battles[4]
    # Asked once, and not for what the cache or Wikipedia already knew.
    assert fetched == ["Ржевская битва|Бой за Гродно"]
    assert cache["ru|Бой за Гродно"] is None


from tools.translate_titles import ArgosTranslator


def test_a_language_without_a_model_gives_no_translations(tmp_path):
    assert ArgosTranslator(tmp_path)("be", ["Абарона Брэсцкай крэпасці"]) == {}
