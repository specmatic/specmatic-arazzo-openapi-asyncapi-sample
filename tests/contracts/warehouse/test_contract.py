import pytest

from tests.contracts.conftest import ProviderEnvironment


@pytest.mark.parametrize(
    "provider_environment",
    [ProviderEnvironment("warehouse", "warehouse", 3003, dependency_mock="order")],
    indirect=True,
)
def test_warehouse_contract(provider_environment):
    provider_environment.run_contract()
