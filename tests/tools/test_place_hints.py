import bz2
import gzip

from tools.place_hints import build_places, choose, hints_for, linked_places, lookup_names, name_candidates, name_key

BATTLE = """{{Infobox military conflict
| conflict = Battle of Bir Hakeim
| place = [[Bir Hakeim]], [[Libya]]
| combatant1 = [[Free France]]
| commander2 = [[Erwin Rommel]]
}}
The '''Battle of Bir Hakeim''' was fought near [[Tobruk]] and [[Gazala|the Gazala line]] by [[Germany|German]]
troops under [[Erwin Rommel]].<ref>{{cite book|title=Desert War}}</ref> The French then broke out towards
El Adem and Sidi Barrani. See [[File:Map.png]].

== References ==
* Smith, ''Desert War'', [[University of Maryland]] Press, Washington.
"""


def test_linked_places_takes_the_place_field_then_the_text_without_countries_or_files():
    assert linked_places("en", BATTLE) == [
        ("Bir Hakeim", "infobox"), ("Libya", "infobox"), ("Tobruk", "artikel"), ("Gazala", "artikel"),
        ("Erwin Rommel", "artikel"),
    ]


def test_name_key_is_the_bare_name():
    assert name_key("Alexandria (Virginia)") == "alexandria"
    assert name_key("Alexandria, Egypt") == "alexandria"
    assert name_key("Sidi Barrani") == "sidi barrani"


def test_name_candidates_are_capitalised_groups_outside_links_and_references():
    keys = name_candidates("en", BATTLE)
    assert {"el adem", "sidi barrani", "french"} <= keys
    assert "desert war" not in keys  # inside a reference
    assert "tobruk" not in keys  # linked, counted apart
    assert name_candidates("ja", "ミッドウェー島の戦い") == set()
    assert "washington" not in keys  # after the References heading


def test_nothing_after_the_sources_heading_is_linked():
    assert ("University of Maryland", "artikel") not in linked_places("en", BATTLE)


def test_choose_takes_the_candidate_nearest_the_linked_places_or_the_only_one():
    alexandrias = [("Alexandria", 31.2, 29.92), ("Alexandria, Virginia", 38.8, -77.05)]
    tobruk = (32.08, 23.97)
    assert choose(alexandrias, [tobruk])[0] == "Alexandria"
    assert choose([("Alexandria, Virginia", 38.8, -77.05)], [tobruk]) is None  # too far
    assert choose(alexandrias, []) is None
    assert choose([("Sidi Barrani", 31.61, 25.93)], [])[0] == "Sidi Barrani"


def test_far_linked_places_are_dropped_and_without_infobox_the_battle_position_anchors():
    links = [("en", "Tobruk", "artikel"), ("en", "University of Maryland", "artikel")]
    positions = {("en", "Tobruk"): (32.08, 23.97, "city"), ("en", "University of Maryland"): (38.99, -76.94, None)}
    hints = hints_for(links, positions, [], {}, position=(31.6, 23.5))
    assert [h["name"] for h in hints] == ["Tobruk"]
    # Without infobox or position: the core of the linked places.
    links.append(("en", "Gazala", "artikel"))
    positions[("en", "Gazala")] = (32.15, 23.1, None)
    assert [h["name"] for h in hints_for(links, positions, [], {})] == ["Tobruk", "Gazala"]


def test_hints_put_the_infobox_first_then_links_then_names_without_links():
    links = [("en", "Tobruk", "artikel"), ("en", "Erwin Rommel", "artikel"), ("en", "Bir Hakeim", "infobox")]
    positions = {("en", "Tobruk"): (32.08, 23.97, "city"), ("en", "Bir Hakeim"): (31.6, 23.48, None)}
    names = [("en", "sidi barrani"), ("en", "alexandria"), ("en", "french")]
    named = {("en", "sidi barrani"): [("Sidi Barrani", 31.61, 25.93)],
             ("en", "alexandria"): [("Alexandria, Virginia", 38.8, -77.05), ("Alexandria", 31.2, 29.92)]}
    assert [(h["name"], h["kind"]) for h in hints_for(links, positions, names, named)] == [
        ("Bir Hakeim", "infobox"), ("Tobruk", "artikel"), ("Sidi Barrani", "artikel"), ("Alexandria", "artikel"),
    ]


def test_build_places_follows_redirects_skips_countries_and_events_and_keeps_names(tmp_path):
    index = tmp_path / "enwiki-index.txt.bz2"
    index.write_bytes(bz2.compress("\n".join([
        "1:1:Tobruk", "1:2:Tobrouk", "1:3:Libya", "1:4:Battle of Gazala", "1:5:Alexandria", "1:6:Alexandria, Virginia",
        "1:7:Erwin Rommel",
    ]).encode() + b"\n"))
    redirects = tmp_path / "enwiki-redirect.sql.gz"
    redirects.write_bytes(gzip.compress(b"INSERT INTO `redirect` VALUES (2,0,'Tobruk','','');\n"))
    geotags = tmp_path / "enwiki-geo_tags.sql.gz"
    geotags.write_bytes(gzip.compress("\n".join([
        "INSERT INTO `geo_tags` VALUES",
        "(10,1,'earth',1,32.08,23.97,NULL,'city',NULL,NULL,NULL,32,23),",
        "(11,3,'earth',1,27.0,17.0,NULL,'country',NULL,NULL,NULL,27,17),",
        "(12,4,'earth',1,32.15,23.1,NULL,'event',NULL,NULL,NULL,32,23),",
        "(13,5,'earth',1,31.2,29.92,NULL,'city',NULL,NULL,NULL,31,29),",
        "(14,6,'earth',1,38.8,-77.05,NULL,NULL,NULL,NULL,NULL,38,-77),",
        "(15,1,'earth',0,0.0,0.0,NULL,NULL,NULL,NULL,NULL,0,0),",
        "(16,7,'earth',1,60.0,90.0,2000000,NULL,NULL,NULL,NULL,60,90);",
    ]).encode()))
    db = tmp_path / "places.sqlite"
    positions = build_places(index, redirects, geotags, {"Tobruk", "Tobrouk", "Libya", "Battle of Gazala", "Erwin Rommel"}, db)
    assert positions == {"Tobruk": (32.08, 23.97, "city"), "Tobrouk": (32.08, 23.97, "city")}
    found = lookup_names(db, {"alexandria", "tobruk", "libya"})
    # One word only names a place whose title is exactly that word.
    assert found["alexandria"] == [("Alexandria", 31.2, 29.92)]
    assert found["tobruk"] == [("Tobruk", 32.08, 23.97)]
    assert "libya" not in found


def test_countries_by_their_capital_or_their_english_link_and_battles_are_no_places(tmp_path):
    from tools.place_hints import english_regions

    index = tmp_path / "nlwiki-index.txt.bz2"
    index.write_bytes(bz2.compress("\n".join([
        "1:1:Tsjaad", "1:2:Libië", "1:3:Tobroek", "1:4:Slag om Tobroek", "1:5:Bir Hakeim (oase)",
    ]).encode() + b"\n"))
    redirects = tmp_path / "nlwiki-redirect.sql.gz"
    redirects.write_bytes(gzip.compress(b"-- none\n"))
    geotags = tmp_path / "nlwiki-geo_tags.sql.gz"
    geotags.write_bytes(gzip.compress("\n".join([
        "(1,1,'earth',1,15.0,19.0,1000,NULL,NULL,NULL,NULL,15,19),",
        "(2,1,'earth',0,12.1,15.04,10000,'city',NULL,NULL,NULL,12,15),",
        "(3,2,'earth',1,26.05,18.2,NULL,NULL,NULL,NULL,NULL,26,18),",
        "(4,3,'earth',1,32.08,23.97,NULL,NULL,NULL,NULL,NULL,32,23),",
        "(5,4,'earth',1,32.08,23.97,NULL,NULL,NULL,NULL,NULL,32,23),",
        "(6,5,'earth',1,31.6,23.48,NULL,NULL,NULL,NULL,NULL,31,23);",
    ]).encode()))
    langlinks = tmp_path / "nlwiki-langlinks.sql.gz"
    langlinks.write_bytes(gzip.compress(b"INSERT INTO `langlinks` VALUES (2,'en','Libya'),(3,'en','Tobruk');\n"))
    positions = build_places(index, redirects, geotags, {"Tsjaad", "Libië", "Tobroek", "Slag om Tobroek", "Bir Hakeim (oase)"},
                             tmp_path / "places.sqlite", langlinks, frozenset({"Libya"}), frozenset({"Bir Hakeim (oase)"}))
    assert set(positions) == {"Tobroek"}

    en_index = tmp_path / "enwiki-index.txt.bz2"
    en_index.write_bytes(bz2.compress(b"1:7:Libya\n1:8:Chad\n1:9:Tobruk\n"))
    en_geotags = tmp_path / "enwiki-geo_tags.sql.gz"
    en_geotags.write_bytes(gzip.compress("\n".join([
        "(7,7,'earth',1,27.0,17.0,1500000,'country',NULL,'LY',NULL,27,17),",
        "(8,8,'earth',1,15.0,19.0,1000,NULL,NULL,NULL,NULL,15,19),",
        "(9,8,'earth',0,12.1,15.04,10000,'city',NULL,NULL,NULL,12,15),",
        "(10,9,'earth',1,32.08,23.97,NULL,'city',NULL,NULL,NULL,32,23);",
    ]).encode()))
    assert english_regions(en_geotags, en_index) == {"Libya", "Chad"}


def test_one_place_named_in_two_languages_is_one_hint():
    links = [("en", "Alexandria", "artikel"), ("pl", "Aleksandria", "artikel")]
    positions = {("en", "Alexandria"): (31.2, 29.92, "city"), ("pl", "Aleksandria"): (31.2, 29.91, None)}
    assert [h["name"] for h in hints_for(links, positions, [], {})] == ["Alexandria"]
