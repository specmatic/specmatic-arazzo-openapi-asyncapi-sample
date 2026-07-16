import pytest

from tests.contracts.conftest import ProviderEnvironment


@pytest.mark.parametrize(
    "provider_environment",
    [ProviderEnvironment("location", "location", 3000)],
    indirect=True,
)
def test_location_contract(provider_environment):
    provider_environment.run_contract()
