"""Unit tests for XClient and CLI."""

import pathlib
from unittest.mock import MagicMock, patch

import pytest

from x_post.cli import main
from x_post.client import OAuth1Credentials, TweetResult, XClient

from helpers import DictConfigStore

_FAKE_OAUTH1 = OAuth1Credentials(
    api_key="k", api_key_secret="ks", access_token="at", access_token_secret="ats",
)


@pytest.fixture
def client() -> XClient:
    return XClient(access_token="fake-token")


@pytest.fixture
def oauth1_client() -> XClient:
    return XClient(access_token="fake-token", oauth1=_FAKE_OAUTH1)


def _base_config() -> DictConfigStore:
    """Config with client_id, client_secret, and access_token pre-filled."""
    return DictConfigStore({
        "client_id": "cid",
        "client_secret": "sec",
        "access_token": "tok",
    })


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


# --- XClient.upload_media ---


class TestUploadMedia:
    def test_returns_media_id(
        self, oauth1_client: XClient, tmp_path: pathlib.Path,
    ) -> None:
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8" + b"\x00" * 100)
        with patch("x_post.client.requests.post") as mock_post:
            mock_post.return_value = _ok_response({"media_id": 12345})
            result = oauth1_client.upload_media(img)
        assert result == "12345"
        mock_post.assert_called_once()

    def test_rejects_unsupported_format(
        self, oauth1_client: XClient, tmp_path: pathlib.Path,
    ) -> None:
        bmp = tmp_path / "image.bmp"
        bmp.write_bytes(b"\x00" * 100)
        with pytest.raises(ValueError, match="Unsupported image format"):
            oauth1_client.upload_media(bmp)

    def test_rejects_oversized_file(
        self, oauth1_client: XClient, tmp_path: pathlib.Path,
    ) -> None:
        big = tmp_path / "huge.png"
        big.write_bytes(b"\x00" * (5 * 1024 * 1024 + 1))
        with pytest.raises(ValueError, match="Image too large"):
            oauth1_client.upload_media(big)

    def test_raises_on_api_error(
        self, oauth1_client: XClient, tmp_path: pathlib.Path,
    ) -> None:
        img = tmp_path / "pic.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 100)
        with patch("x_post.client.requests.post") as mock_post:
            mock_post.return_value = _error_response(400)
            with pytest.raises(Exception):
                oauth1_client.upload_media(img)

    def test_raises_without_oauth1_credentials(
        self, client: XClient, tmp_path: pathlib.Path,
    ) -> None:
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8" + b"\x00" * 100)
        with pytest.raises(ValueError, match="OAuth 1.0a credentials are required"):
            client.upload_media(img)


class TestCreateTweetWithMedia:
    def test_sends_media_ids_in_body(self, client: XClient) -> None:
        with (
            patch.object(
                client._session, "get",
                return_value=_ok_response({"data": {"username": "bob"}}),
            ),
            patch.object(client._session, "post") as mock_post,
        ):
            mock_post.return_value = _tweet_response("456")
            client.create_tweet("With image", media_ids=["12345"])

            body = mock_post.call_args.kwargs["json"]
            assert body == {
                "text": "With image",
                "media": {"media_ids": ["12345"]},
            }


# --- CLI ---


class TestCLIOutput:
    @patch("x_post.cli.XClient")
    @patch("x_post.cli.is_token_valid", return_value=True)
    def test_prints_url_and_thread_hint(
        self, _valid: object, mock_client_cls: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.create_tweet.return_value = TweetResult(
            tweet_id="42", url="https://x.com/bob/status/42",
        )
        main(["Hello!"], _config=_base_config())
        out = capsys.readouterr().out
        assert "https://x.com/bob/status/42" in out
        assert "--reply-to 42" in out

    @patch("x_post.cli.XClient")
    @patch("x_post.cli.is_token_valid", return_value=True)
    def test_passes_reply_to(
        self, _valid: object, mock_client_cls: MagicMock,
    ) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.create_tweet.return_value = TweetResult(
            tweet_id="99", url="https://x.com/bob/status/99",
        )
        main(["--reply-to", "42", "Reply text"], _config=_base_config())
        mock_client.create_tweet.assert_called_once_with(
            "Reply text", reply_to_tweet_id="42", media_ids=None,
        )

    @patch("x_post.cli.XClient")
    @patch("x_post.cli.is_token_valid", return_value=True)
    def test_passes_image_media_id(
        self, _valid: object, mock_client_cls: MagicMock,
        tmp_path: pathlib.Path,
    ) -> None:
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8" + b"\x00" * 100)

        mock_client = mock_client_cls.return_value
        mock_client.upload_media.return_value = "77777"
        mock_client.create_tweet.return_value = TweetResult(
            tweet_id="55", url="https://x.com/bob/status/55",
        )
        config = DictConfigStore({
            "client_id": "cid",
            "client_secret": "sec",
            "access_token": "tok",
            "api_key": "k",
            "api_key_secret": "ks",
            "oauth1_access_token": "oat",
            "oauth1_access_token_secret": "oats",
        })
        main(["--image", str(img), "With pic"], _config=config)
        mock_client.upload_media.assert_called_once_with(img)
        mock_client.create_tweet.assert_called_once_with(
            "With pic", reply_to_tweet_id=None, media_ids=["77777"],
        )


class TestCLIValidation:
    @patch("x_post.cli.is_token_valid", return_value=True)
    def test_rejects_text_over_280_chars(self, *_: object) -> None:
        long_text = "a" * 281
        with pytest.raises(SystemExit):
            main([long_text], _config=_base_config())

    def test_rejects_empty_text(self) -> None:
        with pytest.raises(SystemExit), patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = ""
            main([], _config=_base_config())

    def test_rejects_missing_credentials(self) -> None:
        config = DictConfigStore()
        with pytest.raises(SystemExit), patch("builtins.input", return_value=""):
            main(["hello"], _config=config)

    def test_shows_setup_guide_when_credentials_missing(
        self, capsys: pytest.CaptureFixture[str],
    ) -> None:
        config = DictConfigStore()
        with pytest.raises(SystemExit), patch("builtins.input", return_value=""):
            main(["hello"], _config=config)
        out = capsys.readouterr().out
        assert "First-time setup" in out
        assert "developer.x.com" in out

    @patch("x_post.cli.XClient")
    @patch("x_post.cli.is_token_valid", return_value=True)
    def test_shows_oauth1_guide_when_image_keys_missing(
        self, _valid: object, mock_client_cls: MagicMock,
        tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8" + b"\x00" * 100)
        mock_client = mock_client_cls.return_value
        mock_client.upload_media.return_value = "123"
        mock_client.create_tweet.return_value = TweetResult(
            tweet_id="1", url="https://x.com/u/status/1",
        )
        config = DictConfigStore({
            "client_id": "cid", "client_secret": "sec", "access_token": "tok",
        })
        with patch("builtins.input", return_value="val"):
            main(["--image", str(img), "pic"], _config=config)
        out = capsys.readouterr().out
        assert "OAuth 1.0a" in out
        assert "Keys and Tokens" in out


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
