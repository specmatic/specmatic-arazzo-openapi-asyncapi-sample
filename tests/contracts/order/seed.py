"""Seed the deterministic order state used by the order contract tests."""

from sqlmodel import Session

from common.database import Database
from common.models import Order


def main() -> None:
    orders = [
        Order(
            user_id=1,
            product_id=1,
            inventory=2,
            order_request_id="00000000-0000-4000-8000-000000000001",
        ),
        Order(
            user_id=1,
            product_id=1,
            inventory=2,
            order_request_id="00000000-0000-4000-8000-000000000002",
        ),
    ]

    with Session(Database().engine) as session:
        session.add_all(orders)
        session.commit()

    print("Seeded deterministic pending orders with IDs 1 and 2")

if __name__ == "__main__":
    main()
