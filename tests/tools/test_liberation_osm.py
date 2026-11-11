from tools.liberation_osm import denmark_stones

PLACES = [
    {"lat": 55.40, "lon": 10.39, "tags": {"name": "Odense"}},
    {"lat": 55.10, "lon": 14.70, "tags": {"name": "Rønne"}},
    {"lat": 56.00, "lon": 9.00, "tags": {"name": "Ver weg"}},
]


def stone(lat, lon, text):
    return {"type": "node", "lat": lat, "lon": lon, "tags": {"historic": "memorial", "inscription": text}}


def test_each_place_with_a_stone_of_4_or_5_may_counts_once():
    memorials = [
        stone(55.41, 10.38, "Befrielsen 5. maj 1945"),
        stone(55.40, 10.40, "4. maj 1945"),            # a second stone in Odense
        stone(55.11, 14.71, "Befrielsen 9. maj 1945"),  # Bornholm names its own day
        stone(55.12, 14.69, "5.5.1945"),
        stone(55.70, 9.50, "5. maj 1945"),              # no place within 5 km
        stone(55.40, 10.39, "Faldne 12. juli 1944"),    # no liberation day
    ]
    found = denmark_stones(memorials, PLACES)
    assert [(b.name, b.liberated, b.kamp, b.occupied) for b in found] == [
        ("Odense", "1945-05-05", "westers", "1940-04-09"),
        ("Rønne", "1945-05-09", "sovjet", "1940-04-09"),
    ]
