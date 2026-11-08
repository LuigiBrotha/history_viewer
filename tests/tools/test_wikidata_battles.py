from tools.wikidata_battles import chosen_article, merge_wikidata, parse_item


def claim(prop_value):
    return {"mainsnak": {"snaktype": "value", "datavalue": {"value": prop_value}}}


def time(text, precision=11):
    return {"time": text, "precision": precision}


ENTITY = {
    "id": "Q1",
    "claims": {
        "P580": [claim(time("+1941-07-10T00:00:00Z"))],
        "P582": [claim(time("+1941-09-00T00:00:00Z", 10))],
        "P625": [claim({"latitude": 50.4, "longitude": 30.5, "globe": "http://www.wikidata.org/entity/Q2"})],
        "P276": [claim({"id": "Q1899"})],
        "P710": [claim({"id": "Q7318"}), claim({"id": "Q15180"})],
        "P1346": [claim({"id": "Q7318"})],
    },
    "sitelinks": {"ukwiki": {"title": "Оборона Києва"}, "cswiki": {"title": "Bitva o Kyjev"}, "commonswiki": {"title": "x"}},
    "labels": {"en": {"value": "Battle of Kiev (1941)"}},
}


def test_parse_item_reads_dates_position_people_and_articles():
    item = parse_item(ENTITY)
    assert item["start"] == "1941-07-10" and item["end"] == "1941-09-30" and item["precision"] == "day"
    assert item["coord"] == [50.4, 30.5]
    assert item["locations"] == ["Q1899"] and item["participants"] == ["Q7318", "Q15180"] and item["winners"] == ["Q7318"]
    assert item["sitelinks"] == {"ukwiki": "Оборона Києва", "cswiki": "Bitva o Kyjev"}
    assert item["label_en"] == "Battle of Kiev (1941)"
    assert parse_item({"id": "Q2", "claims": {}}) is None


def test_chosen_article_follows_the_order_then_the_alphabet():
    assert chosen_article({"cswiki": "B", "ukwiki": "A"}) == ("uk", "A")
    assert chosen_article({"zz_xxwiki": "C", "abwiki": "D"}) == ("ab", "D")
    assert chosen_article({}) is None


NAMES = {"Q7318": "Nazi Germany", "Q15180": "Soviet Union", "Q1899": "Kyiv"}


def test_a_known_veldslag_is_only_filled_in_and_a_new_one_is_made_from_its_article():
    battles = [{"title": "Battle of Kiev (1941)", "lat": None, "lng": None, "winner": []},
               {"title": "Slag om Y", "lang": "nl", "lat": 1, "lng": 2, "winner": ["as"]}]
    items = [
        parse_item({**ENTITY, "id": "Q9", "sitelinks": {"enwiki": {"title": "Battle of Kiev (1941)"}}}),
        parse_item(ENTITY),
        parse_item({**ENTITY, "id": "Q8", "sitelinks": {"dewiki": {"title": "Schlacht Y"}}}),
        parse_item({**ENTITY, "id": "Q7", "claims": {**ENTITY["claims"], "P580": [claim(time("+1914-08-01T00:00:00Z"))],
                                                      "P582": []}}),
    ]
    battles, new = merge_wikidata(battles, items, {("de", "Schlacht Y"): "Slag om Y"}, {}, NAMES)
    kiev, y, made = battles
    assert (kiev["lat"], kiev["lng"], kiev["winner"]) == (50.4, 30.5, ["as"])
    assert kiev["filled"] == {"position": "wikidata", "winner": "wikidata"}
    assert (y["lat"], y["lng"], y["winner"]) == (1, 2, ["as"]) and "filled" not in y
    assert made["title"] == "Оборона Києва" and made["lang"] == "uk" and made["wikidata"] == "Q1"
    assert made["title_en"] == "Battle of Kiev (1941)" and made["title_source"] == "wikidata"
    assert made["countries"] == ["Duitsland", "Sovjet-Unie"] and made["winner"] == ["as"] and made["place"] == "Kyiv"
    assert new == [("uk", "Оборона Києва")]
    assert len(battles) == 3  # the item of 1914 lies outside the war
