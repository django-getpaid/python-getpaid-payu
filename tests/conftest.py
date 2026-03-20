"""Shared test fixtures for python-getpaid-payu."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from getpaid_core.enums import PaymentStatus
from getpaid_core.types import BuyerInfo
from getpaid_core.types import ItemInfo


@dataclass
class FakeOrder:
    amount: Decimal
    currency: str

    def get_total_amount(self) -> Decimal:
        return self.amount

    def get_buyer_info(self) -> BuyerInfo:
        return BuyerInfo(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
        )

    def get_description(self) -> str:
        return "Test order"

    def get_currency(self) -> str:
        return self.currency

    def get_items(self) -> list[ItemInfo]:
        return [
            ItemInfo(
                name="Product 1",
                quantity=1,
                unit_price=self.amount,
            )
        ]

    def get_return_url(self, success: bool | None = None) -> str:
        return "https://shop.example.com/success"


class FakePayment:
    def __init__(
        self,
        *,
        payment_id: str = "test-payment-123",
        external_id: str | None = None,
        amount: Decimal = Decimal("100.00"),
        currency: str = "PLN",
        status: str = PaymentStatus.NEW,
        provider_data: dict[str, Any] | None = None,
    ) -> None:
        self.id = payment_id
        self.order = FakeOrder(amount=amount, currency=currency)
        self.amount_required = amount
        self.currency = currency
        self.status = status
        self.backend = "payu"
        self.external_id = external_id
        self.description = "Test order"
        self.amount_paid = Decimal("0")
        self.amount_locked = Decimal("0")
        self.amount_refunded = Decimal("0")
        self.fraud_status = "unknown"
        self.fraud_message = ""
        self.provider_data = dict(provider_data or {})

    def is_fully_paid(self) -> bool:
        return self.amount_paid >= self.amount_required

    def is_fully_refunded(self) -> bool:
        return self.amount_refunded >= self.amount_paid


def make_mock_payment(
    *,
    payment_id: str = "test-payment-123",
    external_id: str | None = None,
    amount: Decimal = Decimal("100.00"),
    currency: str = "PLN",
    status: str = PaymentStatus.NEW,
    provider_data: dict[str, Any] | None = None,
) -> FakePayment:
    return FakePayment(
        payment_id=payment_id,
        external_id=external_id,
        amount=amount,
        currency=currency,
        status=status,
        provider_data=provider_data,
    )


@pytest.fixture
def mock_payment() -> FakePayment:
    return make_mock_payment()


PAYU_CONFIG = {
    "pos_id": 300746,
    "second_key": "b6ca15b0d1020e8094d9b5f8d163db54",
    "oauth_id": 300746,
    "oauth_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
    "sandbox": True,
    "notify_url": ("https://shop.example.com/payments/callback/{payment_id}"),
    "continue_url": ("https://shop.example.com/payments/success/{payment_id}"),
}


@pytest.fixture
def payu_config() -> dict[str, Any]:
    return PAYU_CONFIG.copy()
