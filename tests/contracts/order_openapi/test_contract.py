import pytest

from tests.contracts.conftest import ProviderEnvironment

@pytest.mark.parametrize(
    "provider_environment",
    [ProviderEnvironment("order_openapi", "order", 3002, needs_kafka=True)],
    indirect=True,
)
def test_order_openapi_contract(provider_environment):
    provider_environment.run_contract()
