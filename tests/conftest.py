"""Shared test fixtures for python-getpaid-payu."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from getpaid_core.enums import PaymentStatus
from getpaid_core.fsm import create_payment_machine


def make_mock_payment(
    *,
    payment_id: str = "test-payment-123",
    external_id: str = "",
    amount: Decimal = Decimal("100.00"),
    currency: str = "PLN",
    status: str = PaymentStatus.NEW,
) -> MagicMock:
    """Create a mock payment satisfying the Payment protocol."""
    order = MagicMock()
    order.get_total_amount.return_value = amount
    order.get_buyer_info.return_value = {
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
    }
    order.get_description.return_value = "Test order"
    order.get_currency.return_value = currency
    order.get_items.return_value = [
        {"name": "Product 1", "quantity": 1, "unit_price": amount}
    ]
    order.get_return_url.return_value = "https://shop.example.com/success"

    payment = MagicMock()
    payment.id = payment_id
    payment.order = order
    payment.amount_required = amount
    payment.currency = currency
    payment.status = status
    payment.backend = "payu"
    payment.external_id = external_id
    payment.description = "Test order"
    payment.amount_paid = Decimal("0")
    payment.amount_locked = Decimal("0")
    payment.amount_refunded = Decimal("0")
    payment.fraud_status = "unknown"
    payment.fraud_message = ""

    # These are needed by FSM guards
    payment.is_fully_paid.return_value = True
    payment.is_fully_refunded.return_value = False

    return payment


class FakePayment:
    """A real object for FSM tests.

    MagicMock cannot be used with ``transitions`` because it
    responds to ``hasattr`` for every attribute, causing the
    library to skip binding trigger methods.
    """

    def __init__(
        self,
        *,
        payment_id: str = "test-payment-123",
        external_id: str = "",
        amount: Decimal = Decimal("100.00"),
        currency: str = "PLN",
        status: str = PaymentStatus.NEW,
        is_fully_paid: bool = True,
        is_fully_refunded: bool = False,
    ) -> None:
        self.id = payment_id
        self.order = MagicMock()
        self.order.get_total_amount.return_value = amount
        self.order.get_buyer_info.return_value = {
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
        }
        self.order.get_description.return_value = "Test order"
        self.order.get_currency.return_value = currency
        self.order.get_items.return_value = [
            {
                "name": "Product 1",
                "quantity": 1,
                "unit_price": amount,
            }
        ]
        self.order.get_return_url.return_value = (
            "https://shop.example.com/success"
        )
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
        self._is_fully_paid = is_fully_paid
        self._is_fully_refunded = is_fully_refunded

    def is_fully_paid(self) -> bool:
        return self._is_fully_paid

    def is_fully_refunded(self) -> bool:
        return self._is_fully_refunded


@pytest.fixture
def mock_payment():
    """Fresh mock payment in NEW status."""
    return make_mock_payment()


@pytest.fixture
def mock_payment_with_fsm():
    """Mock payment with FSM attached (has trigger methods)."""
    payment = FakePayment()
    create_payment_machine(payment)
    return payment


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
def payu_config():
    return PAYU_CONFIG.copy()
