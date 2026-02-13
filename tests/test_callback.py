"""Tests for PayUProcessor verify_callback and handle_callback."""

import hashlib
from decimal import Decimal

import pytest
from getpaid_core.enums import PaymentStatus
from getpaid_core.exceptions import InvalidCallbackError
from getpaid_core.fsm import create_payment_machine

from getpaid_payu.processor import PayUProcessor
from getpaid_payu.types import OrderStatus
from getpaid_payu.types import RefundStatus

from .conftest import PAYU_CONFIG
from .conftest import FakePayment
from .conftest import make_mock_payment


SECOND_KEY = str(PAYU_CONFIG["second_key"])


def _make_processor(payment=None, config=None):
    """Create a PayUProcessor with defaults."""
    if payment is None:
        payment = make_mock_payment()
    if config is None:
        config = PAYU_CONFIG.copy()
    return PayUProcessor(payment=payment, config=config)


def _sign(body: str, key: str = SECOND_KEY, algo: str = "MD5"):
    """Compute signature for a body string."""
    hasher = getattr(hashlib, algo.replace("-", "").lower())
    return hasher(f"{body}{key}".encode()).hexdigest()


class TestVerifyCallback:
    """Tests for verify_callback signature verification."""

    async def test_valid_md5_signature(self):
        body = '{"order":{"status":"COMPLETED"}}'
        sig = _sign(body, algo="MD5")
        headers = {
            "openpayu-signature": (
                f"signature={sig};algorithm=MD5;sender=300746"
            ),
        }
        data = {"_raw_body": body}

        processor = _make_processor()
        # Should not raise
        await processor.verify_callback(data=data, headers=headers)

    async def test_valid_sha256_signature(self):
        body = '{"order":{"status":"COMPLETED"}}'
        sig = _sign(body, algo="SHA-256")
        headers = {
            "openpayu-signature": (
                f"signature={sig};algorithm=SHA-256;sender=300746"
            ),
        }
        data = {"_raw_body": body}

        processor = _make_processor()
        await processor.verify_callback(data=data, headers=headers)

    async def test_missing_signature_raises(self):
        processor = _make_processor()
        with pytest.raises(InvalidCallbackError, match="NO SIGNATURE"):
            await processor.verify_callback(data={"_raw_body": ""}, headers={})

    async def test_bad_signature_raises(self):
        body = '{"order":{"status":"COMPLETED"}}'
        headers = {
            "openpayu-signature": ("signature=bad_signature;algorithm=MD5"),
        }
        data = {"_raw_body": body}

        processor = _make_processor()
        with pytest.raises(InvalidCallbackError, match="BAD SIGNATURE"):
            await processor.verify_callback(data=data, headers=headers)

    async def test_x_openpayu_signature_header(self):
        """Alternate header name works."""
        body = '{"order":{"status":"COMPLETED"}}'
        sig = _sign(body)
        headers = {
            "x-openpayu-signature": (
                f"signature={sig};algorithm=MD5;sender=300746"
            ),
        }
        data = {"_raw_body": body}

        processor = _make_processor()
        await processor.verify_callback(data=data, headers=headers)

    async def test_empty_signature_header_raises(self):
        processor = _make_processor()
        with pytest.raises(InvalidCallbackError, match="NO SIGNATURE"):
            await processor.verify_callback(
                data={"_raw_body": ""},
                headers={"openpayu-signature": ""},
            )

    async def test_missing_raw_body_raises(self):
        """Missing _raw_body key raises clear error."""
        processor = _make_processor()
        with pytest.raises(InvalidCallbackError, match="Missing _raw_body"):
            await processor.verify_callback(
                data={},
                headers={"openpayu-signature": "signature=abc;algorithm=MD5"},
            )

    async def test_unsupported_algorithm_raises(self):
        """Unsupported hash algorithm raises clear error."""
        body = '{"order":{"status":"COMPLETED"}}'
        headers = {
            "openpayu-signature": (
                "signature=abc;algorithm=SHAKE-256;sender=300746"
            ),
        }
        data = {"_raw_body": body}

        processor = _make_processor()
        with pytest.raises(InvalidCallbackError, match="Unsupported hash"):
            await processor.verify_callback(data=data, headers=headers)


class TestHandleCallbackOrder:
    """Tests for handle_callback with order notifications."""

    async def test_order_completed_results_in_paid(self):
        payment = FakePayment(status=PaymentStatus.PREPARED)
        create_payment_machine(payment)

        processor = _make_processor(payment=payment)
        data = {
            "order": {"status": OrderStatus.COMPLETED},
        }
        await processor.handle_callback(data=data, headers={})

        assert payment.status == PaymentStatus.PAID

    async def test_order_canceled_results_in_failed(self):
        payment = FakePayment(status=PaymentStatus.PREPARED)
        create_payment_machine(payment)

        processor = _make_processor(payment=payment)
        data = {
            "order": {"status": OrderStatus.CANCELED},
        }
        await processor.handle_callback(data=data, headers={})

        assert payment.status == PaymentStatus.FAILED

    async def test_order_waiting_results_in_pre_auth(self):
        payment = FakePayment(status=PaymentStatus.PREPARED)
        create_payment_machine(payment)

        processor = _make_processor(payment=payment)
        data = {
            "order": {
                "status": OrderStatus.WAITING_FOR_CONFIRMATION,
            },
        }
        await processor.handle_callback(data=data, headers={})

        assert payment.status == PaymentStatus.PRE_AUTH

    async def test_order_new_no_state_change(self):
        """NEW status in callback should not change state."""
        payment = FakePayment(status=PaymentStatus.PREPARED)
        create_payment_machine(payment)

        processor = _make_processor(payment=payment)
        data = {
            "order": {"status": OrderStatus.NEW},
        }
        await processor.handle_callback(data=data, headers={})

        assert payment.status == PaymentStatus.PREPARED

    async def test_order_pending_no_state_change(self):
        """PENDING status in callback should not change state."""
        payment = FakePayment(status=PaymentStatus.PREPARED)
        create_payment_machine(payment)

        processor = _make_processor(payment=payment)
        data = {
            "order": {"status": OrderStatus.PENDING},
        }
        await processor.handle_callback(data=data, headers={})

        assert payment.status == PaymentStatus.PREPARED

    async def test_completed_when_already_paid_no_error(self):
        """Duplicate COMPLETED callback should not crash."""
        payment = FakePayment(status=PaymentStatus.PAID)
        create_payment_machine(payment)

        processor = _make_processor(payment=payment)
        data = {
            "order": {"status": OrderStatus.COMPLETED},
        }
        # may_trigger returns False, no crash
        await processor.handle_callback(data=data, headers={})

        assert payment.status == PaymentStatus.PAID

    async def test_waiting_when_already_pre_auth_no_error(self):
        """Duplicate WAITING_FOR_CONFIRMATION should not crash."""
        payment = FakePayment(status=PaymentStatus.PRE_AUTH)
        create_payment_machine(payment)

        processor = _make_processor(payment=payment)
        data = {
            "order": {
                "status": OrderStatus.WAITING_FOR_CONFIRMATION,
            },
        }
        await processor.handle_callback(data=data, headers={})

        assert payment.status == PaymentStatus.PRE_AUTH


class TestHandleCallbackRefund:
    """Tests for handle_callback with refund notifications."""

    async def test_refund_finalized(self):
        payment = FakePayment(
            status=PaymentStatus.REFUND_STARTED,
            is_fully_refunded=True,
        )
        create_payment_machine(payment)
        payment.amount_paid = Decimal("100.00")
        payment.amount_refunded = Decimal("0")

        processor = _make_processor(payment=payment)
        data = {
            "refund": {
                "status": RefundStatus.FINALIZED,
                "amount": 10000,  # centified
            },
        }
        await processor.handle_callback(data=data, headers={})

        assert payment.status == PaymentStatus.REFUNDED

    async def test_refund_finalized_partial(self):
        """Partial refund stays in PARTIAL status."""
        payment = FakePayment(
            status=PaymentStatus.REFUND_STARTED,
            is_fully_refunded=False,
        )
        create_payment_machine(payment)
        payment.amount_paid = Decimal("100.00")
        payment.amount_refunded = Decimal("0")

        processor = _make_processor(payment=payment)
        data = {
            "refund": {
                "status": RefundStatus.FINALIZED,
                "amount": 5000,  # centified: 50.00
            },
        }
        await processor.handle_callback(data=data, headers={})

        # confirm_refund → PARTIAL, but mark_as_refunded
        # guard fails (not fully refunded)
        assert payment.status == PaymentStatus.PARTIAL

    async def test_refund_canceled(self):
        payment = FakePayment(
            status=PaymentStatus.REFUND_STARTED,
            is_fully_paid=True,
        )
        create_payment_machine(payment)
        payment.amount_paid = Decimal("100.00")

        processor = _make_processor(payment=payment)
        data = {
            "refund": {
                "status": RefundStatus.CANCELED,
            },
        }
        await processor.handle_callback(data=data, headers={})

        # cancel_refund → PARTIAL, then mark_as_paid → PAID
        assert payment.status == PaymentStatus.PAID
