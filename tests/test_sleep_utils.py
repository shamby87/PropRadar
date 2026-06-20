import json

import pytest

from src.sleeper.sleepUtils import SleeperApiError, parse_graphql_data, parse_json_body, response_snippet


def test_response_snippet_truncates_long_text():
    assert response_snippet("x" * 250, limit=200) == ("x" * 200) + "..."


def test_response_snippet_empty():
    assert response_snippet(None) == "<empty>"
    assert response_snippet(b"") == "<empty>"


def test_parse_json_body_valid():
    assert parse_json_body(b'{"ok": true}', "ctx") == {"ok": True}


def test_parse_json_body_invalid():
    with pytest.raises(SleeperApiError, match="invalid JSON"):
        parse_json_body(b"not-json", "ctx")


def test_parse_graphql_data_success():
    class Resp:
        status_code = 200
        reason = "OK"
        content = json.dumps({"data": {"create_parlay": {"parlay_id": "123"}}}).encode()

    data = parse_graphql_data(Resp(), "create_parlay")
    assert data["create_parlay"]["parlay_id"] == "123"


def test_parse_graphql_data_http_error():
    class Resp:
        status_code = 500
        reason = "Server Error"
        content = b"fail"

    with pytest.raises(SleeperApiError, match="HTTP 500"):
        parse_graphql_data(Resp(), "create_parlay")
