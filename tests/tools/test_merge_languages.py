import gzip

from tools.merge_languages import merge_languages, read_langlinks


def en(title, lat=None, lng=None, winner=None, **extra):
    return {"title": title, "start": "1942-01-01", "end": "1942-02-01", "lat": lat, "lng": lng,
            "winner": winner or [], **extra}


def other(lang, title, lat=None, lng=None, winner=None, start="1942-01-01"):
    return {"title": title, "start": start, "end": "1942-02-01", "lat": lat, "lng": lng,
            "winner": winner or [], "lang": lang, "url": f"https://{lang}.wikipedia.org/wiki/{title}"}


def test_read_langlinks_keeps_wanted_pages_and_languages(tmp_path):
    sql = ("INSERT INTO `langlinks` VALUES (5,'en','Battle of Arnhem'),(5,'de','Schlacht um Arnheim'),"
           "(5,'fr','Bataille d\\'Arnhem'),(6,'en','Other');\n")
    path = tmp_path / "l.sql.gz"
    path.write_bytes(gzip.compress(sql.encode("utf-8")))
    assert read_langlinks(path, {5}, {"en", "de", "pl"}) == {5: {"en": "Battle of Arnhem", "de": "Schlacht um Arnheim"}}


def test_read_langlinks_one_row_per_line(tmp_path):
    sql = "INSERT INTO `langlinks` VALUES\n(5,'en','A'),\n(5,'pl','B');\n"
    path = tmp_path / "l.sql.gz"
    path.write_bytes(gzip.compress(sql.encode("utf-8")))
    assert read_langlinks(path, {5}, {"en", "pl"}) == {5: {"en": "A", "pl": "B"}}


def test_an_english_battle_without_position_takes_the_first_language_in_order():
    battles = [en("Battle of Arnhem")]
    others = {"nl": [other("nl", "Slag om Arnhem")], "de": [other("de", "Schlacht um Arnheim", 52.0, 5.9)],
              "pl": [other("pl", "Bitwa pod Arnhem", 51.0, 5.0)]}
    links = {("nl", "Slag om Arnhem"): {"en": "Battle of Arnhem"},
             ("de", "Schlacht um Arnheim"): {"en": "Battle of Arnhem"},
             ("pl", "Bitwa pod Arnhem"): {"en": "Battle of Arnhem"}}
    merged = merge_languages(battles, others, links)
    assert len(merged) == 1
    assert (merged[0]["lat"], merged[0]["lng"]) == (52.0, 5.9)


def test_an_english_position_and_winner_stay():
    battles = [en("Battle of Arnhem", 1.0, 2.0, ["as"])]
    others = {"nl": [other("nl", "Slag om Arnhem", 52.0, 5.9, ["westers"])]}
    links = {("nl", "Slag om Arnhem"): {"en": "Battle of Arnhem"}}
    merged = merge_languages(battles, others, links)
    assert (merged[0]["lat"], merged[0]["lng"], merged[0]["winner"]) == (1.0, 2.0, ["as"])


def test_an_unknown_english_winner_takes_the_first_known_in_order():
    battles = [en("Battle of X")]
    others = {"de": [other("de", "Schlacht X", winner=["as"])], "pl": [other("pl", "Bitwa X", winner=["sovjet"])]}
    links = {("de", "Schlacht X"): {"en": "Battle of X"}, ("pl", "Bitwa X"): {"en": "Battle of X"}}
    assert merge_languages(battles, others, links)[0]["winner"] == ["as"]


def test_battles_linked_only_to_each_other_form_one_new_battle_named_in_the_first_language():
    others = {"nl": [other("nl", "Slag om Kornwerderzand")],
              "de": [other("de", "Schlacht um Kornwerderzand", 53.07, 5.33, ["westers"])]}
    links = {("de", "Schlacht um Kornwerderzand"): {"nl": "Slag om Kornwerderzand"}}
    merged = merge_languages([], others, links)
    assert len(merged) == 1
    new = merged[0]
    assert (new["title"], new["lang"]) == ("Slag om Kornwerderzand", "nl")
    assert (new["lat"], new["lng"], new["winner"]) == (53.07, 5.33, ["westers"])


def test_a_battle_without_links_is_its_own_new_battle():
    others = {"de": [other("de", "Kesselschlacht bei Uman", 48.7, 30.2)]}
    merged = merge_languages([en("Battle of Uman")], others, {})
    assert [b["title"] for b in merged] == ["Battle of Uman", "Kesselschlacht bei Uman"]
    assert merged[1]["lang"] == "de"


def test_a_link_to_an_english_article_that_is_not_a_veldslag_makes_a_new_battle():
    others = {"pl": [other("pl", "Bitwa X", 1.0, 2.0)]}
    links = {("pl", "Bitwa X"): {"en": "Some English page"}}
    merged = merge_languages([], others, links)
    assert [(b["title"], b["lang"]) for b in merged] == [("Bitwa X", "pl")]


def test_merging_again_gives_the_same_result():
    battles = [en("Battle of Arnhem")]
    others = {"de": [other("de", "Schlacht um Arnheim", 52.0, 5.9, ["as"])], "pl": [other("pl", "Nowa", 3.0, 4.0)]}
    links = {("de", "Schlacht um Arnheim"): {"en": "Battle of Arnhem"}}
    once = merge_languages(battles, others, links)
    twice = merge_languages(once, others, links)
    assert twice == once


def test_merging_with_fewer_languages_takes_back_what_they_filled():
    battles = [en("Battle of Arnhem")]
    others = {"de": [other("de", "Schlacht um Arnheim", 52.0, 5.9, ["as"])], "pl": [other("pl", "Nowa")]}
    links = {("de", "Schlacht um Arnheim"): {"en": "Battle of Arnhem"}}
    filled = merge_languages(battles, others, links)
    assert merge_languages(filled, {}, {}) == battles


def test_owners_names_the_veldslag_of_each_article():
    owners = {}
    others = {"nl": [other("nl", "Slag om Arnhem"), other("nl", "Slag om K")], "de": [other("de", "Schlacht um K")]}
    links = {("nl", "Slag om Arnhem"): {"en": "Battle of Arnhem"}, ("de", "Schlacht um K"): {"nl": "Slag om K"}}
    merge_languages([en("Battle of Arnhem")], others, links, owners)
    assert owners == {("nl", "Slag om Arnhem"): "Battle of Arnhem", ("nl", "Slag om K"): "Slag om K",
                      ("de", "Schlacht um K"): "Slag om K"}
