import os

# Contract/UI tests run against the mock providers regardless of .env, so the
# suite never calls Google or depends on live traffic. Real routing has its
# own tests (tests/core/test_navigation.py) with Google stubbed out.
os.environ["USE_MOCKS"] = "true"

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests.helpers import DISPATCHER, RIDER_1, signed_in  # noqa: E402


@pytest.fixture
def dispatcher_client() -> TestClient:
    return signed_in(DISPATCHER)


@pytest.fixture
def rider_client() -> TestClient:
    return signed_in(RIDER_1)


@pytest.fixture
def dispatcher_token() -> str:
    from core.auth import authenticate, issue_token

    return issue_token(authenticate("dispatcher", DISPATCHER["identifier"], DISPATCHER["password"]))
