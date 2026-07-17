import pytest

from tests.contracts.conftest import ProviderEnvironment


@pytest.mark.parametrize(
    "provider_environment",
    [ProviderEnvironment("product", "product", 3001)],
    indirect=True,
)
def test_product_contract(provider_environment):
    provider_environment.run_contract()
