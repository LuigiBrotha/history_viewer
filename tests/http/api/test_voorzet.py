import itertools
import math
import random

from app.http.api.battles.hint_summary import _unit, summarise, voorzet


def hint(lat, lng):
    return {"name": "x", "lat": lat, "lng": lng, "kind": "artikel"}


def spread(vectors):
    middle = [sum(v[i] for v in vectors) / len(vectors) for i in range(3)]
    return sum(sum((v[i] - middle[i]) ** 2 for i in range(3)) for v in vectors)


def test_one_or_two_places_keep_all_of_them():
    assert voorzet([hint(52, 5)]) == (52.0, 5.0)
    lat, lng = voorzet([hint(50, 4), hint(52, 6)])
    assert 50 < lat < 52 and 4 < lng < 6


def test_the_far_tenth_does_not_count():
    near = [hint(52 + i / 10, 5 + i / 10) for i in range(10)]
    lat, lng = voorzet([*near, hint(-30, 150)])
    assert abs(lat - 52.45) < 0.05 and abs(lng - 5.45) < 0.05


def test_five_places_keep_four():
    lat, lng = voorzet([hint(10, 10), hint(10.2, 10), hint(10, 10.2), hint(10.2, 10.2), hint(60, 60)])
    assert abs(lat - 10.1) < 0.01 and abs(lng - 10.1) < 0.01


def test_the_date_line_is_no_edge():
    lat, lng = voorzet([hint(0, 179), hint(0, -179), hint(1, 179.5)])
    assert abs(abs(lng) - 180) < 1.5 and 0 <= lat <= 1


def test_the_kept_points_are_the_tightest_possible():
    generator = random.Random(4)
    for _ in range(40):
        count = generator.randint(5, 12)
        hints = [hint(generator.uniform(-40, 60), generator.uniform(-40, 60)) for _ in range(count)]
        vectors = [_unit(h) for h in hints]
        keep = math.ceil(0.9 * count - 0.5)
        best = min(itertools.combinations(vectors, keep), key=spread)
        lat, lng = voorzet(hints)
        found = _unit({"lat": lat, "lng": lng})
        x, y, z = (sum(v[i] for v in best) for i in range(3))
        size = math.sqrt(x * x + y * y + z * z)
        assert all(abs(a - b / size) < 1e-6 for a, b in zip(found, (x, y, z)))


def test_the_summary_carries_the_voorzet():
    out = summarise([hint(52, 5), hint(52, 5.2)])
    assert out.voorzet_lat == 52.0 or abs(out.voorzet_lat - 52) < 0.01
    assert abs(out.voorzet_lng - 5.1) < 0.01
