import bz2
import gzip
from xml.sax.saxutils import escape

from tools.place_hints import hints_for, linked_places, place_coordinates, place_positions

BATTLE = """{{Infobox military conflict
| conflict = Battle of Bir Hakeim
| place = [[Bir Hakeim]], [[Libya]]
| combatant1 = [[Free France]]
| commander2 = [[Erwin Rommel]]
}}
The '''Battle of Bir Hakeim''' was fought near [[Tobruk]] and [[Gazala|the Gazala line]] by [[Germany|German]]
troops under [[Erwin Rommel]]. See [[File:Map.png]] and [[Bir Hakeim]].
"""


def test_linked_places_takes_the_place_field_then_the_text_without_countries_or_files():
    assert linked_places("en", BATTLE) == [
        ("Bir Hakeim", "infobox"), ("Libya", "infobox"), ("Tobruk", "artikel"), ("Gazala", "artikel"), ("Erwin Rommel", "artikel"),
    ]


def test_place_coordinates_reads_the_ways_languages_write_a_position():
    assert place_coordinates("en", "{{Infobox settlement|coordinates={{coord|32|04|N|23|58|E}}}}") == (32.06667, 23.96667)
    assert place_coordinates("fr", "{{Infobox Commune de France|latitude=48.7|longitude=44.5}}") == (48.7, 44.5)
    assert place_coordinates("pl", "{{Miejscowość infobox|stopniN=49|minutN=41|stopniE=21|minutE=46}}") == (49.68333, 21.76667)
    assert place_coordinates("it", "{{Divisione amministrativa|Latitudine decimale=45.4|Longitudine decimale=9.2}}") == (45.4, 9.2)
    assert place_coordinates("en", "A person, born somewhere.") is None
    assert place_coordinates("en", "{{Infobox country|coordinates={{coord|27|N|17|E}}}}") is None
    assert place_coordinates("de", "{{Infobox Staat|BREITENGRAD=27}} {{Coordinate|NS=27|EW=17}}") is None


def test_hints_put_the_infobox_first_and_skip_what_is_not_a_place():
    links = [("en", "Tobruk", "artikel"), ("en", "Erwin Rommel", "artikel"), ("en", "Bir Hakeim", "infobox"),
             ("fr", "Tobrouk", "artikel")]
    positions = {("en", "Tobruk"): (32.08, 23.97), ("en", "Bir Hakeim"): (31.6, 23.48), ("fr", "Tobrouk"): (32.08, 23.97)}
    assert hints_for(links, positions) == [
        {"name": "Bir Hakeim", "lat": 31.6, "lng": 23.48, "kind": "infobox"},
        {"name": "Tobruk", "lat": 32.08, "lng": 23.97, "kind": "artikel"},
        {"name": "Tobrouk", "lat": 32.08, "lng": 23.97, "kind": "artikel"},
    ]


def page_xml(page_id, title, text):
    return (f"<page><title>{escape(title)}</title><ns>0</ns><id>{page_id}</id>"
            f"<revision><text>{escape(text)}</text></revision></page>")


def test_place_positions_reads_the_dump_and_follows_redirects(tmp_path):
    pages = [(1, "Tobruk", "{{coord|32|04|N|23|58|E}}"), (2, "Erwin Rommel", "A field marshal.")]
    data = bz2.compress(b"<mediawiki>")
    offset = len(data)
    data += bz2.compress("".join(page_xml(*p) for p in pages).encode("utf-8"))
    dump, index, redirects = tmp_path / "d.xml.bz2", tmp_path / "i.txt.bz2", tmp_path / "r.sql.gz"
    dump.write_bytes(data)
    index.write_bytes(bz2.compress(f"{offset}:1:Tobruk\n{offset}:2:Erwin Rommel\n{offset}:3:Tobrouk\n".encode()))
    redirects.write_bytes(gzip.compress(b"INSERT INTO `redirect` VALUES (3,0,'Tobruk','','');\n"))
    found = place_positions("en", dump, index, redirects, {"Tobruk", "Erwin Rommel", "Tobrouk", "Nowhere"})
    assert found == {"Tobruk": (32.06667, 23.96667), "Tobrouk": (32.06667, 23.96667)}
