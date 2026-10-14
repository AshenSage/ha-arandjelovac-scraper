"""Real HA fixtures; kept separate from the historical coordinator doubles."""
import pytest

@pytest.fixture(autouse=True)
def enable_integration(enable_custom_integrations):
    yield
