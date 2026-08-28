from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.text import clean_text


def test_clean_text_collapses_whitespace_between_inline_elements():
    node = HTMLParser("<table><tr><td>Kptlt.  <a>Otto Kretschmer</a></td></tr></table>").css_first("td")

    assert clean_text(node) == "Kptlt. Otto Kretschmer"


def test_clean_text_strips_leading_and_trailing_whitespace():
    node = HTMLParser("<p>  hello world  </p>").css_first("p")

    assert clean_text(node) == "hello world"
