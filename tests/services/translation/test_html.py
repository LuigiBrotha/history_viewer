from app.services.translation.html import translate_html


def fake(texts):
    """A 'translation' that is easy to check: known sentences mapped, the rest upper-cased."""
    known = {
        "The battle began near Kursk.": "De slag begon bij Koersk.",
        "Soviet victory": "Sovjetoverwinning",
        "Army Group South": "Legergroep Zuid",
        "German penetration near the town": "Duitse doorbraak bij de stad",
    }
    return [known.get(t, t.upper()) for t in texts]


def test_a_link_is_found_by_its_own_name_or_by_its_translated_name():
    html = ('<p>The battle began near <a href="u" data-battle="Kursk">Kursk</a>.</p>'
            '<p>Led by <a href="v">Army Group South</a> today</p>')
    out = translate_html(html, lambda texts: [
        {"The battle began near Kursk.": "De slag begon bij Kursk.",
         "Led by Army Group South today": "Geleid door Legergroep Zuid vandaag",
         "Army Group South": "Legergroep Zuid", "Kursk": "Koersk"}[t] for t in texts])
    assert out == ('<p>De slag begon bij <a href="u" data-battle="Kursk">Kursk</a>.</p>'
                   '<p>Geleid door <a href="v">Legergroep Zuid</a> vandaag</p>')


def test_a_link_whose_name_is_gone_is_dropped_but_its_text_stays_translated():
    html = '<p>Near <a href="u">the town</a> it rained</p>'
    out = translate_html(html, lambda texts: ["Bij het stadje regende het" if "rained" in t else "de plaats"
                                              for t in texts])
    assert out == "<p>Bij het stadje regende het</p>"


def test_line_breaks_split_the_text_and_lists_of_links_are_left_alone():
    html = ('<table><tr><th>Resultaat</th><td>Soviet victory</td></tr>'
            '<tr><td><a href="a">Adolf Hitler</a><br><a href="b">Kurt Zeitzler</a><br>'
            '<a href="c">Army Group South</a>:<br><b><a href="d">OKH</a>:</b></td></tr></table>')
    asked = []

    def translate(texts):
        asked.extend(texts)
        return fake(texts)

    out = translate_html(html, translate)
    assert out == ('<table><tr><th>Resultaat</th><td>Sovjetoverwinning</td></tr>'
                   '<tr><td><a href="a">Adolf Hitler</a><br><a href="b">Kurt Zeitzler</a><br>'
                   '<a href="c">Army Group South</a>:<br><b><a href="d">OKH</a>:</b></td></tr></table>')
    # The Dutch labels of the infobox and names that are only links are not sent at all.
    assert asked == ["Soviet victory"]


def test_figures_headings_and_list_items_are_translated_and_images_kept():
    html = ('<figure><img src="/i.jpg" alt="x" loading="lazy"><figcaption>German penetration near the town'
            '</figcaption></figure><h3>Background</h3><ul><li>One &amp; two</li></ul>')
    out = translate_html(html, fake)
    assert out == ('<figure><img src="/i.jpg" alt="x" loading="lazy"><figcaption>Duitse doorbraak bij de stad'
                   '</figcaption></figure><h3>BACKGROUND</h3><ul><li>ONE &amp; TWO</li></ul>')


def test_bold_and_italic_come_back_like_links():
    html = "<p>The ship <i>Bismarck</i> sank</p>"
    out = translate_html(html, lambda texts: ["Het schip Bismarck zonk" if "sank" in t else t for t in texts])
    assert out == "<p>Het schip <i>Bismarck</i> zonk</p>"


def test_every_text_is_sent_in_one_call():
    calls = []

    def translate(texts):
        calls.append(list(texts))
        return [t.upper() for t in texts]

    translate_html("<p>One <a href='a'>two</a></p><p>Three</p>", translate)
    assert len(calls) == 1


def test_a_name_is_only_found_as_a_whole_word():
    html = '<p>The <a href="p">Polish</a> army</p>'
    out = translate_html(html, lambda texts: ["Het Poolse leger" if "army" in t else "Pools" for t in texts])
    assert out == "<p>Het Poolse leger</p>"


def test_field_names_of_another_infobox_get_dutch_labels_without_the_model():
    html = "<table><tr><th>Дата</th><td>1942</td></tr><tr><th>Командир1</th><td>Paulus</td></tr></table>"
    asked = []

    def translate(texts):
        asked.extend(texts)
        return [t.upper() for t in texts]

    out = translate_html(html, translate)
    assert out == "<table><tr><th>Datum</th><td>1942</td></tr><tr><th>Bevelhebber 1</th><td>PAULUS</td></tr></table>"
    assert "Дата" not in asked
