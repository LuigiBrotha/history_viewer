from app.services.wiki.sanitize import sanitize


def test_sanitize_strips_hostile_input():
    html = (
        '<p onclick="steal()">Hi<script>alert(1)</script>'
        '<img src="/api/battles/images/a.jpg" onerror="steal()" alt="a">'
        '<span style="color:red" class="note">s</span>'
        '<a href="javascript:alert(1)">bad</a>'
        '<a href="https://en.wikipedia.org/wiki/X" data-title="X" data-battle="Second Happy Time">good</a>'
        '<iframe src="https://evil.example"></iframe></p>'
    )

    result = sanitize(html)

    assert "<script" not in result
    assert "alert(1)" not in result
    assert "onerror" not in result
    assert "onclick" not in result
    assert "style=" not in result
    assert "javascript:" not in result
    assert "<iframe" not in result
    assert 'data-battle="Second Happy Time"' in result
    assert 'src="/api/battles/images/a.jpg"' in result
    assert '<span class="note">s</span>' in result


def test_sanitize_drops_tags_outside_the_whitelist_but_keeps_their_text():
    assert sanitize("<div><center>kept</center></div>") == "kept"


def test_sanitize_keeps_whitelisted_markup():
    html = (
        "<h3>H</h3><blockquote>q<sup>1</sup><sub>2</sub><br></blockquote>"
        '<table class="article-table"><tbody><tr><td colspan="2">c</td></tr></tbody></table>'
    )

    assert sanitize(html) == html
