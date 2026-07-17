import pytest

from tests.contracts.conftest import ProviderEnvironment

@pytest.mark.parametrize(
    "provider_environment",
    [ProviderEnvironment("order_asyncapi", "order", 3002, needs_kafka=True)],
    indirect=True,
)
def test_order_asyncapi_contract(provider_environment):
    provider_environment.run_contract()
