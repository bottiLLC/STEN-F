import os
import sys
import pytest
import asyncio

# Ensure 'v2/app' is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

from container import Container

@pytest.fixture(scope="function")
async def container():
    """Provides a Container instance for each test function."""
    return Container()
