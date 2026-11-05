"""Shared test setup: API calls act as a logged-in user unless a test says otherwise.

Tests of the login check itself (test_auth.py) use the `real_auth` marker.
"""

from collections.abc import Iterator

import pytest

from api.auth import User, current_user
from api.main import app

TEST_USER = User(id="user-1", email="test@example.com", name="Test User")


@pytest.fixture(autouse=True)
def logged_in(request: pytest.FixtureRequest) -> Iterator[None]:
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    app.dependency_overrides[current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(current_user, None)
