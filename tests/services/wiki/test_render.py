import json
from pathlib import Path

from app.services.wiki.infobox import render_infobox
from app.services.wiki.render import render_article

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "wikipedia" / "battle_pages.json"


def image_src(name, width):
    return f"/api/battles/images/{width}/{name}"


def render(wikitext, battle_index=None):
    return render_article(wikitext, battle_index=battle_index or {}, image_src=image_src)


def test_headings_render_one_level_below_the_article_title():
    result = render("== Background ==\ntext\n=== Detail ===\nmore")

    assert "<h3>Background</h3>" in result
    assert "<h4>Detail</h4>" in result


def test_blank_lines_separate_paragraphs():
    assert render("First line\ncontinues.\n\nSecond.") == "<p>First line\ncontinues.</p><p>Second.</p>"


def test_italic_and_bold():
    assert render("''x'' and '''y'''") == "<p><i>x</i> and <b>y</b></p>"


def test_bullet_and_numbered_lists():
    assert render("* a\n* b") == "<ul><li>a</li><li>b</li></ul>"
    assert render("# a\n# b") == "<ol><li>a</li><li>b</li></ol>"


def test_nested_list_items_open_an_inner_list():
    assert render("* a\n** b\n* c") == "<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>"


def test_wikilink_points_at_wikipedia_with_its_title():
    result = render("See [[Battle of Britain|the air war]].")

    assert (
        '<a href="https://en.wikipedia.org/wiki/Battle_of_Britain" data-title="Battle of Britain">the air war</a>'
        in result
    )


def test_wikilink_to_a_battle_carries_the_battle_title():
    result = render("[[second Happy Time]]", battle_index={"Second Happy Time": "Second Happy Time"})

    assert 'data-battle="Second Happy Time"' in result
    assert ">second Happy Time</a>" in result


def test_link_to_battle_redirect_gets_real_title():
    result = render("[[Operation Drumbeat]]", battle_index={"Operation Drumbeat": "Second Happy Time"})

    assert 'data-title="Operation Drumbeat" data-battle="Second Happy Time"' in result


def test_external_link_keeps_its_label():
    assert render("[http://x.example/a label]") == '<p><a href="http://x.example/a">label</a></p>'


def test_file_link_renders_a_figure_with_its_caption():
    expected = (
        '<figure><img src="/api/battles/images/330/X.jpg" alt="caption" loading="lazy">'
        "<figcaption>caption</figcaption></figure>"
    )

    assert render("[[File:X.jpg|thumb|caption]]") == expected
    assert render("[[Image:X.jpg|thumb|upright|left|caption]]") == expected


def test_figure_in_running_text_closes_the_paragraph():
    result = render("Before [[File:X.jpg|thumb|cap]] after")

    assert result.startswith("<p>Before</p><figure>")
    assert result.endswith("</figure><p>after</p>")


def test_infobox_renders_first_with_dutch_labels_in_order():
    wikitext = (
        "'''Battle''' intro.\n"
        "{{Infobox military conflict\n"
        "|conflict = Battle\n|image = File:Map.png\n|caption = The map\n"
        "|date = {{start date|1942|1|14}}\n|place = [[Atlantic]]\n|result = German victory\n"
        "|territory = None\n|combatant1 = Germany\n|combatant2 = United States\n"
        "|commander1 = Dönitz\n|commander2 = King\n|strength1 = 5 U-boats\n|strength2 = \n"
        "|casualties1 = 2 U-boats<br />\n|casualties2 = 600 ships\n}}"
    )

    result = render(wikitext)

    assert result.startswith('<table class="article-infobox">')
    assert result.index("</table>") < result.index("intro.")
    labels = ["Datum", "Plaats", "Resultaat", "Gebied", "Strijdende partijen", "Bevelhebbers", "Sterkte", "Verliezen"]
    positions = [result.index(f">{label}</th>") for label in labels]
    assert positions == sorted(positions)
    assert '<img src="/api/battles/images/330/Map.png" alt="The map" loading="lazy">' in result
    assert "14 January 1942" in result
    assert "<td>Germany</td><td>United States</td>" in result
    assert "<td>5 U-boats</td><td></td>" in result
    assert "2 U-boats<br>" in result
    assert "{{" not in result


def test_infobox_leaves_out_empty_rows_and_accepts_location():
    fields = {"location": "Halifax", "result": " ", "commander1": "", "commander2": ""}

    result = render_infobox(fields, lambda text: text.strip())

    assert ">Plaats</th><td>Halifax</td>" in result
    assert "Resultaat" not in result
    assert "Bevelhebbers" not in result


def test_infobox_variants_are_recognised():
    for name in ("Infobox military operation", "Infobox battle", "infobox_military_conflict"):
        assert 'class="article-infobox"' in render(f"{{{{{name}|date=1940}}}}\ntext")


def test_convert_shows_value_and_unit():
    assert render("A {{convert|5|km}} march") == "<p>A 5 km march</p>"


def test_flag_templates_show_the_country_or_nothing():
    assert render("{{flag|Germany}} vs {{flagicon|USA}}{{flagcountry|Japan}}") == "<p>Germany vs Japan</p>"


def test_text_templates_keep_their_text():
    assert render("{{lang|de|Befehlshaber}} {{nowrap|8:00 a.m.}} {{small|tiny}}") == (
        "<p>Befehlshaber 8:00 a.m. tiny</p>"
    )


def test_date_templates_render_the_date():
    assert render("From {{start date|1942|1|14}} to {{end date|1942|7|31}}") == (
        "<p>From 14 January 1942 to 31 July 1942</p>"
    )


def test_unknown_templates_references_comments_and_categories_vanish():
    wikitext = (
        "Fact{{sfn|Rohwer|2005|p=44}}<ref>Rohwer, p. 44</ref><ref name=a/><!-- hidden --> stays.\n\n"
        "[[Category:Naval battles]]\n[[de:Zweite glückliche Zeit]]"
    )

    assert render(wikitext) == "<p>Fact stays.</p>"


def test_reference_sections_are_dropped_until_the_next_heading_of_that_level():
    wikitext = (
        "== Aftermath ==\nkept\n"
        "== See also ==\n* [[Other]]\n=== Lists ===\ngone\n"
        "== References ==\n{{reflist}}\n"
        "== Legacy ==\nalso kept\n"
        "== Further reading ==\nbook"
    )

    result = render(wikitext)

    assert "kept" in result and "also kept" in result
    assert "<h3>Legacy</h3>" in result
    for dropped in ("See also", "Other", "Lists", "gone", "References", "Further reading", "book"):
        assert dropped not in result


def test_inline_html_on_the_whitelist_is_kept():
    result = render("a<br />b<sup>1</sup><sub>2</sub>\n\n<blockquote>quote</blockquote>")

    assert "a<br>b<sup>1</sup><sub>2</sub>" in result
    assert "<blockquote>quote</blockquote>" in result


def test_simple_table_renders_rows_and_cells_without_attributes():
    wikitext = '{| class="wikitable" style="x"\n! Ship !! Tons\n|-\n| style="color:red" | Alpha || 5,000\n|}'

    result = render(wikitext)

    assert result.startswith('<table class="article-table">')
    assert "<th>Ship</th><th>Tons</th>" in result
    assert "<td>Alpha</td><td>5,000</td>" in result
    assert "style" not in result and "wikitable" not in result


def test_text_is_escaped():
    assert render("1 < 2 & <b>bold</b> <script>x</script>") == "<p>1 &lt; 2 &amp; <b>bold</b></p>"


def test_unbalanced_markup_renders_partially():
    result = render("Intro ''open {{Infobox military conflict|date=1942\n\n== H ==\ntext")

    assert "text" in result
    assert "<h3>H</h3>" in result


def test_renders_convoy_hx_79_fixture():
    wikitext = json.loads(FIXTURES.read_text())["Convoy HX 79"]

    result = render(wikitext)

    assert 'class="article-infobox"' in result
    # The excerpt has two == sections and four === subsections, so the three headings span both levels.
    assert result.count("<h3>") + result.count("<h4>") >= 3
    assert "<h3>Background</h3>" in result
    assert "{{" not in result
    assert "<ref" not in result
    assert "References" not in result
