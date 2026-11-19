from unittest.mock import MagicMock

import pytest
from requests.exceptions import ConnectionError

from pragma_sdk.onchain.constants import RPC_URLS
from pragma_sdk.onchain.utils import pick_rpc

URLS = ["https://a.example/rpc", "https://b.example/rpc", "https://c.example/rpc"]


def _post(answers: dict):
    def post(url, **_):
        answer = answers[url]
        if isinstance(answer, Exception):
            raise answer
        status, body = answer
        response = MagicMock(status_code=status)
        response.json.side_effect = body if isinstance(body, Exception) else None
        response.json.return_value = body
        return response

    return post


def test_first_healthy_rpc_is_preferred(monkeypatch):
    calls = []
    post = _post({u: (200, {"result": "0.10.3"}) for u in URLS})
    monkeypatch.setattr(
        "pragma_sdk.onchain.utils.requests.post",
        lambda url, **kw: calls.append(url) or post(url, **kw),
    )
    assert pick_rpc("mainnet", URLS) == URLS[0]
    assert calls == [URLS[0]]


def test_unhealthy_rpcs_are_skipped_in_order(monkeypatch):
    monkeypatch.setattr(
        "pragma_sdk.onchain.utils.requests.post",
        _post(
            {
                URLS[0]: ConnectionError("down"),
                URLS[1]: (502, ValueError("html error page")),
                URLS[2]: (200, {"result": "0.10.3"}),
            }
        ),
    )
    assert pick_rpc("mainnet", URLS) == URLS[2]


def test_no_healthy_rpc_raises(monkeypatch):
    monkeypatch.setattr(
        "pragma_sdk.onchain.utils.requests.post",
        _post({u: (200, {"error": {"code": -32603}}) for u in URLS}),
    )
    with pytest.raises(ValueError, match="No working RPC"):
        pick_rpc("mainnet", URLS)


def test_snf_node_is_the_preferred_mainnet_rpc():
    assert RPC_URLS["mainnet"][0] == "https://mainnet.nodes.starknet.org/rpc/v0_10"
