import json
import os
from unittest.mock import Mock, patch

import pytest
from aioresponses import aioresponses


@pytest.fixture
def mock_herodotus_env(monkeypatch):
    env_vars = {
        "ACCOUNT_ADDRESSES": "0xf00,0xbar",
        "SECRET_NAME": "SecretString",
        "ORIGIN_CHAIN": "GOERLI",
        "DEST_CHAIN": "STARKNET_GOERLI",
        "RPC_URL": "https://test.chain/rpc",
        "API_URL": "https://api.herodotus.cloud/",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield


@pytest.fixture
def herodotus_request_payload():
    return {
        "originChain": "GOERLI",
        "destinationChain": "STARKNET_GOERLI",
        "blockNumber": 1,
        "type": "ACCOUNT_ACCESS",
        "requestedProperties": {
            "ACCOUNT_ACCESS": {
                "account": "0xf00",
                "properties": ["nonce", "balance", "codeHash", "storageHash"],
            }
        },
    }


@pytest.fixture
def herodotus_response(herodotus_request_payload):
    return {
        **herodotus_request_payload,
        "taskId": "some-id",
        "taskStatus": "SCHEDULED",
        "scheduledAt": 1,
        "currentGroupId": "groupId",
        "processingStepsTracker": {
            "type": "ACCOUNT_ACCESS",
            "actions_required": "SOME_INTERNAL_ACTION_TYPE",
            "isActionComplete": True,
            "currentActionIndex": 1,
        },
    }


@pytest.mark.herodotus
def test_herodotus_get_api_key(mock_herodotus_env, secrets):
    from stagecoach.jobs.herodotus import app

    assert app._get_api_key() == "mykey"


@pytest.mark.herodotus
@pytest.mark.asyncio
async def test_herodotus_handle_account(
    mock_herodotus_env, secrets, herodotus_response, herodotus_request_payload
):
    from stagecoach.jobs.herodotus import app

    with aioresponses() as mocker:
        mocker.post(
            f"{os.getenv('API_URL')}?apiKey=mykey",
            payload=herodotus_response,
        )
        await app._handle_account("0xf00", 1, "mykey")

        mocker.assert_called_once_with(
            f"{os.getenv('API_URL')}?apiKey=mykey",
            method="POST",
            data=json.dumps(herodotus_request_payload),
        )


@pytest.fixture
def mock_web3():
    web3 = Mock()
    web3.eth.block_number = 1
    yield web3


@pytest.mark.asyncio
async def test_herodotus_handler(
    mock_herodotus_env, secrets, mock_web3, herodotus_response
):
    with patch("stagecoach.jobs.herodotus.app.Web3", return_value=mock_web3):
        from stagecoach.jobs.herodotus import app

        with aioresponses() as mocker:
            mocker.post(
                f"{os.getenv('API_URL')}?apiKey=mykey",
                payload=herodotus_response,
            )
            mocker.post(
                f"{os.getenv('API_URL')}?apiKey=mykey",
                payload={
                    "taskId": "some-id",
                    "taskStatus": "SCHEDULED",
                    "scheduledAt": 1,
                    "currentGroupId": "groupId",
                    "processingStepsTracker": {
                        "type": "ACCOUNT_ACCESS",
                        "actions_required": "SOME_INTERNAL_ACTION_TYPE",
                        "isActionComplete": True,
                        "currentActionIndex": 1,
                    },
                    "originChain": "GOERLI",
                    "destinationChain": "STARKNET_GOERLI",
                    "blockNumber": 1,
                    "type": "ACCOUNT_ACCESS",
                    "requestedProperties": {
                        "ACCOUNT_ACCESS": {
                            "account": "0xbar",
                            "properties": [
                                "nonce",
                                "balance",
                                "codeHash",
                                "storageHash",
                            ],
                        }
                    },
                },
            )
            actual = await app.handler_async(None, None)
            assert actual == {"success": True}
