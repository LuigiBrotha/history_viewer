from pathlib import Path

from app.services.scraping.uboat_net.listing import parse_listing

_FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "uboat_net" / "listing.html"


def test_parse_listing_extracts_boat_refs_from_real_fixture():
    html = _FIXTURE.read_text(encoding="utf-8")

    refs = parse_listing(html)

    assert len(refs) > 1000
    slugs = {ref.slug for ref in refs}
    assert "u99" in slugs
    assert "u1000" in slugs


def test_parse_listing_pairs_slug_with_display_number():
    html = _FIXTURE.read_text(encoding="utf-8")

    refs = parse_listing(html)

    by_slug = {ref.slug: ref.number for ref in refs}
    assert by_slug["u1000"] == "U-1000"


def test_parse_listing_deduplicates_repeated_links():
    html = '<a href="/boats/u99.htm">U-99</a> ... <a href="/boats/u99.htm">U-99</a>'

    refs = parse_listing(html)

    assert len(refs) == 1


def test_parse_listing_ignores_non_boat_links():
    html = '<a href="/boats/patrols/u99.html">patrols</a><a href="/boats/u99.htm">U-99</a>'

    refs = parse_listing(html)

    assert len(refs) == 1
    assert refs[0].slug == "u99"
