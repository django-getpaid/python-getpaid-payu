"""Tests for PayUProcessor callback handling."""

import hashlib
from decimal import Decimal

import pytest
from getpaid_core.enums import PaymentEvent
from getpaid_core.exceptions import InvalidCallbackError

from getpaid_payu.processor import PayUProcessor
from getpaid_payu.types import OrderStatus
from getpaid_payu.types import RefundStatus

from .conftest import PAYU_CONFIG


SECOND_KEY = str(PAYU_CONFIG["second_key"])


def _make_processor(payment=None, config=None):
    from .conftest import make_mock_payment

    if payment is None:
        payment = make_mock_payment()
    if config is None:
        config = PAYU_CONFIG.copy()
    return PayUProcessor(payment=payment, config=config)


def _sign(body: str, key: str = SECOND_KEY, algo: str = "MD5"):
    hasher = getattr(hashlib, algo.replace("-", "").lower())
    return hasher(f"{body}{key}".encode()).hexdigest()


class TestVerifyCallback:
    async def test_valid_md5_signature(self):
        body = '{"order":{"status":"COMPLETED"}}'
        sig = _sign(body, algo="MD5")
        headers = {
            "openpayu-signature": (
                f"signature={sig};algorithm=MD5;sender=300746"
            )
        }
        config = {**PAYU_CONFIG, "allow_md5_callbacks": True}

        await _make_processor(config=config).verify_callback(
            data={},
            headers=headers,
            raw_body=body,
        )

    async def test_bad_signature_raises(self):
        body = '{"order":{"status":"COMPLETED"}}'
        headers = {
            "openpayu-signature": "signature=bad_signature;algorithm=SHA-256"
        }

        with pytest.raises(InvalidCallbackError, match="BAD SIGNATURE"):
            await _make_processor().verify_callback(
                data={"_raw_body": body},
                headers=headers,
            )

    async def test_bad_signature_does_not_leak_expected_digest(self, caplog):
        """The correct signature must never appear in errors or logs.

        Echoing the expected digest back turns the endpoint into a
        signature oracle: an attacker could forge callbacks by reading
        the valid signature out of the error response.
        """
        body = '{"order":{"status":"COMPLETED"}}'
        expected = _sign(body, algo="SHA-256")
        headers = {
            "openpayu-signature": "signature=bad_signature;algorithm=SHA-256"
        }

        with (
            caplog.at_level("DEBUG"),
            pytest.raises(InvalidCallbackError) as excinfo,
        ):
            await _make_processor().verify_callback(
                data={"_raw_body": body},
                headers=headers,
            )

        assert expected not in str(excinfo.value)
        for record in caplog.records:
            assert expected not in record.getMessage()


def _order_data(**overrides):
    """Valid callback order payload bound to the default mock payment."""
    order = {
        "orderId": "PAYU-ORDER-1",
        "extOrderId": "test-payment-123",
        "currencyCode": "PLN",
        "totalAmount": "10000",
        "status": OrderStatus.COMPLETED,
    }
    order.update(overrides)
    return order


class TestHandleCallbackOrder:
    async def test_order_completed_returns_capture_update(self):
        update = await _make_processor().handle_callback(
            data={"order": _order_data(status=OrderStatus.COMPLETED)},
            headers={},
        )

        assert update is not None
        assert update.payment_event is PaymentEvent.PAYMENT_CAPTURED
        assert update.paid_amount == Decimal("100.00")

    async def test_order_canceled_returns_failure_update(self):
        update = await _make_processor().handle_callback(
            data={"order": _order_data(status=OrderStatus.CANCELED)},
            headers={},
        )

        assert update is not None
        assert update.payment_event is PaymentEvent.FAILED

    async def test_order_waiting_returns_lock_update(self):
        update = await _make_processor().handle_callback(
            data={
                "order": _order_data(
                    status=OrderStatus.WAITING_FOR_CONFIRMATION,
                )
            },
            headers={},
        )

        assert update is not None
        assert update.payment_event is PaymentEvent.LOCKED
        assert update.locked_amount == Decimal("100.00")


class TestHandleCallbackBinding:
    """The callback must be cross-checked against the local payment."""

    async def test_mismatched_ext_order_id_rejected(self):
        with pytest.raises(InvalidCallbackError, match="extOrderId"):
            await _make_processor().handle_callback(
                data={"order": _order_data(extOrderId="someone-elses-order")},
                headers={},
            )

    async def test_missing_ext_order_id_rejected(self):
        order = _order_data()
        del order["extOrderId"]

        with pytest.raises(InvalidCallbackError, match="extOrderId"):
            await _make_processor().handle_callback(
                data={"order": order},
                headers={},
            )

    async def test_mismatched_currency_rejected(self):
        with pytest.raises(InvalidCallbackError, match="currency"):
            await _make_processor().handle_callback(
                data={"order": _order_data(currencyCode="EUR")},
                headers={},
            )

    async def test_missing_total_amount_rejected(self):
        order = _order_data()
        del order["totalAmount"]

        with pytest.raises(InvalidCallbackError, match="totalAmount"):
            await _make_processor().handle_callback(
                data={"order": order},
                headers={},
            )

    async def test_zero_total_amount_rejected(self):
        with pytest.raises(InvalidCallbackError, match="totalAmount"):
            await _make_processor().handle_callback(
                data={"order": _order_data(totalAmount="0")},
                headers={},
            )


class TestHandleCallbackRefund:
    async def test_refund_finalized_returns_refund_update(self):
        update = await _make_processor().handle_callback(
            data={
                "refund": {
                    "status": RefundStatus.FINALIZED,
                    "amount": 10000,
                }
            },
            headers={},
        )

        assert update is not None
        assert update.payment_event is PaymentEvent.REFUND_CONFIRMED
        assert update.refunded_amount == Decimal("100.00")

    async def test_refund_canceled_returns_cancel_update(self):
        update = await _make_processor().handle_callback(
            data={"refund": {"status": RefundStatus.CANCELED}},
            headers={},
        )

        assert update is not None
        assert update.payment_event is PaymentEvent.REFUND_CANCELLED
