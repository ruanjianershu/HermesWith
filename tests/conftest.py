"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Override the default event loop fixture to use session scope."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
