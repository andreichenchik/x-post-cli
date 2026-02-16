"""Unit tests for XClient and CLI."""

from unittest.mock import MagicMock, patch

import pytest

from x.cli import main
from x.client import TweetResult, XClient


@pytest.fixture
def client() -> XClient:
    return XClient(access_token="fake-token")


# --- XClient.get_username ---


class TestGetUsername:
    def test_returns_username(self, client: XClient) -> None:
        with patch.object(client._session, "get") as mock_get:
            mock_get.return_value = _ok_response({"data": {"username": "alice"}})
            assert client.get_username() == "alice"

    def test_caches_username(self, client: XClient) -> None:
        with patch.object(client._session, "get") as mock_get:
            mock_get.return_value = _ok_response({"data": {"username": "alice"}})
            client.get_username()
            client.get_username()
            mock_get.assert_called_once()

    def test_raises_on_401(self, client: XClient) -> None:
        with patch.object(client._session, "get") as mock_get:
            mock_get.return_value = _error_response(401)
            with pytest.raises(Exception):
                client.get_username()


# --- XClient.create_tweet ---


class TestCreateTweet:
    def test_sends_correct_body(self, client: XClient) -> None:
        with (
            patch.object(
                client._session, "get",
                return_value=_ok_response({"data": {"username": "bob"}}),
            ),
            patch.object(client._session, "post") as mock_post,
        ):
            mock_post.return_value = _tweet_response("123456")
            client.create_tweet("Hello!")

            body = mock_post.call_args.kwargs["json"]
            assert body == {"text": "Hello!"}
            assert "reply" not in body

    def test_sends_reply_body(self, client: XClient) -> None:
        with (
            patch.object(
                client._session, "get",
                return_value=_ok_response({"data": {"username": "bob"}}),
            ),
            patch.object(client._session, "post") as mock_post,
        ):
            mock_post.return_value = _tweet_response("999")
            client.create_tweet("Reply!", reply_to_tweet_id="123")

            body = mock_post.call_args.kwargs["json"]
            assert body == {
                "text": "Reply!",
                "reply": {"in_reply_to_tweet_id": "123"},
            }

    def test_returns_tweet_result(self, client: XClient) -> None:
        with (
            patch.object(
                client._session, "get",
                return_value=_ok_response({"data": {"username": "bob"}}),
            ),
            patch.object(client._session, "post") as mock_post,
        ):
            mock_post.return_value = _tweet_response("789")
            result = client.create_tweet("test")
            assert isinstance(result, TweetResult)
            assert result.tweet_id == "789"
            assert result.url == "https://x.com/bob/status/789"

    def test_raises_on_403(self, client: XClient) -> None:
        with (
            patch.object(
                client._session, "get",
                return_value=_ok_response({"data": {"username": "bob"}}),
            ),
            patch.object(client._session, "post") as mock_post,
        ):
            mock_post.return_value = _error_response(403)
            with pytest.raises(Exception):
                client.create_tweet("nope")

    def test_raises_on_429(self, client: XClient) -> None:
        with (
            patch.object(
                client._session, "get",
                return_value=_ok_response({"data": {"username": "bob"}}),
            ),
            patch.object(client._session, "post") as mock_post,
        ):
            mock_post.return_value = _error_response(429)
            with pytest.raises(Exception):
                client.create_tweet("rate limited")


# --- CLI ---


class TestCLIOutput:
    @patch("x.cli.XClient")
    @patch("x.cli.is_token_valid", return_value=True)
    @patch("x.cli.dotenv.load_dotenv")
    @patch.dict("os.environ", {
        "CLIENT_ID": "cid", "CLIENT_SECRET": "sec", "ACCESS_TOKEN": "tok",
    })
    def test_prints_url_and_thread_hint(
        self, _load: object, _valid: object, mock_client_cls: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.create_tweet.return_value = TweetResult(
            tweet_id="42", url="https://x.com/bob/status/42",
        )
        main(["Hello!"])
        out = capsys.readouterr().out
        assert "https://x.com/bob/status/42" in out
        assert "--reply-to 42" in out

    @patch("x.cli.XClient")
    @patch("x.cli.is_token_valid", return_value=True)
    @patch("x.cli.dotenv.load_dotenv")
    @patch.dict("os.environ", {
        "CLIENT_ID": "cid", "CLIENT_SECRET": "sec", "ACCESS_TOKEN": "tok",
    })
    def test_passes_reply_to(
        self, _load: object, _valid: object, mock_client_cls: MagicMock,
    ) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.create_tweet.return_value = TweetResult(
            tweet_id="99", url="https://x.com/bob/status/99",
        )
        main(["--reply-to", "42", "Reply text"])
        mock_client.create_tweet.assert_called_once_with(
            "Reply text", reply_to_tweet_id="42",
        )


class TestCLIValidation:
    @patch("x.cli.is_token_valid", return_value=True)
    @patch("x.cli.dotenv.load_dotenv")
    @patch.dict("os.environ", {"CLIENT_ID": "cid", "CLIENT_SECRET": "sec", "ACCESS_TOKEN": "tok"})
    def test_rejects_text_over_280_chars(self, *_: object) -> None:
        long_text = "a" * 281
        with pytest.raises(SystemExit):
            main([long_text])

    @patch("x.cli.dotenv.load_dotenv")
    @patch.dict("os.environ", {"CLIENT_ID": "cid", "CLIENT_SECRET": "sec", "ACCESS_TOKEN": "tok"})
    def test_rejects_empty_text(self, *_: object) -> None:
        with pytest.raises(SystemExit), patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = ""
            main([])

    @patch("x.cli.dotenv.load_dotenv")
    @patch.dict("os.environ", {"CLIENT_ID": "", "CLIENT_SECRET": ""})
    def test_rejects_missing_credentials(self, *_: object) -> None:
        with pytest.raises(SystemExit):
            main(["hello"])


# --- helpers ---


def _ok_response(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _tweet_response(tweet_id: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 201
    resp.ok = True
    resp.json.return_value = {"data": {"id": tweet_id}}
    resp.raise_for_status.return_value = None
    return resp


def _error_response(status_code: int) -> MagicMock:
    from requests.exceptions import HTTPError

    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = False
    resp.text = "error"
    resp.raise_for_status.side_effect = HTTPError(response=resp)
    return resp
