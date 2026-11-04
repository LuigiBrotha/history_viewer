from unittest.mock import Mock, patch

from app.services.scraping.uboat_net.http_client import PoliteHttpClient, build_user_agent


def test_build_user_agent_without_contact():
    assert build_user_agent("") == "uboats-scraper/0.1"


def test_build_user_agent_with_contact():
    assert build_user_agent("d_verhoef@hotmail.com") == "uboats-scraper/0.1 (+contact: d_verhoef@hotmail.com)"


@patch("app.services.scraping.uboat_net.http_client.time.sleep")
@patch("app.services.scraping.uboat_net.http_client.time.monotonic")
@patch("app.services.scraping.uboat_net.http_client.requests.Session.get")
def test_first_request_does_not_sleep(mock_get, mock_monotonic, mock_sleep):
    mock_get.return_value = Mock(text="hello", raise_for_status=Mock())
    mock_monotonic.return_value = 100.0
    client = PoliteHttpClient(delay_seconds=10, user_agent="test-agent")

    result = client.get_text("https://uboat.net/x")

    assert result == "hello"
    mock_sleep.assert_not_called()


@patch("app.services.scraping.uboat_net.http_client.time.sleep")
@patch("app.services.scraping.uboat_net.http_client.time.monotonic")
@patch("app.services.scraping.uboat_net.http_client.requests.Session.get")
def test_second_request_sleeps_for_remaining_delay(mock_get, mock_monotonic, mock_sleep):
    mock_get.return_value = Mock(text="hello", raise_for_status=Mock())
    mock_monotonic.side_effect = [100.0, 103.0, 103.0]
    client = PoliteHttpClient(delay_seconds=10, user_agent="test-agent")

    client.get_text("https://uboat.net/x")
    client.get_text("https://uboat.net/y")

    mock_sleep.assert_called_once_with(7.0)


@patch("app.services.scraping.uboat_net.http_client.time.sleep")
@patch("app.services.scraping.uboat_net.http_client.time.monotonic")
@patch("app.services.scraping.uboat_net.http_client.requests.Session.get")
def test_does_not_sleep_when_elapsed_already_exceeds_delay(mock_get, mock_monotonic, mock_sleep):
    mock_get.return_value = Mock(text="hello", raise_for_status=Mock())
    mock_monotonic.side_effect = [100.0, 115.0, 115.0]
    client = PoliteHttpClient(delay_seconds=10, user_agent="test-agent")

    client.get_text("https://uboat.net/x")
    client.get_text("https://uboat.net/y")

    mock_sleep.assert_not_called()


@patch("app.services.scraping.uboat_net.http_client.time.monotonic")
@patch("app.services.scraping.uboat_net.http_client.requests.Session.get")
def test_get_text_raises_on_http_error(mock_get, mock_monotonic):
    mock_monotonic.return_value = 100.0
    response = Mock(text="", raise_for_status=Mock(side_effect=RuntimeError("404")))
    mock_get.return_value = response
    client = PoliteHttpClient(delay_seconds=10, user_agent="test-agent")

    try:
        client.get_text("https://uboat.net/missing")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


@patch("app.services.scraping.uboat_net.http_client.requests.Session.get")
def test_get_text_passes_a_connect_and_read_timeout(mock_get):
    mock_get.return_value = Mock(text="hello", raise_for_status=Mock())
    client = PoliteHttpClient(delay_seconds=0, user_agent="test-agent")

    client.get_text("https://uboat.net/x")

    assert mock_get.call_args.kwargs["timeout"] == (10, 60)


@patch("app.services.scraping.uboat_net.http_client.time.sleep")
@patch("app.services.scraping.uboat_net.http_client.time.monotonic")
@patch("app.services.scraping.uboat_net.http_client.requests.Session.get")
def test_a_failed_request_still_counts_for_the_delay(mock_get, mock_monotonic, mock_sleep):
    mock_get.side_effect = [RuntimeError("connection reset"), Mock(text="hello", raise_for_status=Mock())]
    mock_monotonic.side_effect = [100.0, 101.0, 101.0]
    client = PoliteHttpClient(delay_seconds=10, user_agent="test-agent")

    try:
        client.get_text("https://uboat.net/x")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
    client.get_text("https://uboat.net/y")

    mock_sleep.assert_called_once_with(9.0)
