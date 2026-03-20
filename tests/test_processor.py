"""Tests for PayUProcessor prepare, polling, charge, and refunds."""

import json
from decimal import Decimal

import pytest
from getpaid_core.enums import BackendMethod
from getpaid_core.enums import PaymentEvent
from getpaid_core.exceptions import ChargeFailure
from getpaid_core.exceptions import LockFailure

from getpaid_payu.processor import PayUProcessor
from getpaid_payu.types import OrderStatus

from .conftest import PAYU_CONFIG
from .conftest import make_mock_payment


SANDBOX_URL = "https://secure.snd.payu.com/"
AUTH_URL = "https://secure.snd.payu.com/pl/standard/user/oauth/authorize"
ORDERS_URL = "https://secure.snd.payu.com/api/v2_1/orders"
OAUTH_RESPONSE = {
    "access_token": "test-token-123",
    "token_type": "bearer",
    "expires_in": 43199,
    "grant_type": "client_credentials",
}


def _make_processor(payment=None, config=None):
    if payment is None:
        payment = make_mock_payment()
    if config is None:
        config = PAYU_CONFIG.copy()
    return PayUProcessor(payment=payment, config=config)


class TestPrepareTransaction:
    async def test_rest_flow_success(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.post(ORDERS_URL).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "orderId": "PAYU-ORDER-123",
                "extOrderId": "test-payment-123",
                "redirectUri": "https://payu.com/pay/123",
            },
            status_code=302,
        )

        result = await _make_processor().prepare_transaction()

        assert result.redirect_url == "https://payu.com/pay/123"
        assert result.method is BackendMethod.GET
        assert result.external_id == "PAYU-ORDER-123"

    async def test_rest_flow_failure_raises_lock_failure(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.post(ORDERS_URL).respond(
            json={"error": "Internal error"},
            status_code=500,
        )

        with pytest.raises(LockFailure):
            await _make_processor().prepare_transaction()

    async def test_notify_url_resolved(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        route = respx_mock.post(ORDERS_URL).respond(
            json={
                "status": {"statusCode": "SUCCESS"},
                "orderId": "O1",
                "extOrderId": "test-payment-123",
                "redirectUri": "https://payu.com/pay",
            },
            status_code=200,
        )

        await _make_processor().prepare_transaction()

        body = json.loads(route.calls[0].request.content)
        assert body["notifyUrl"] == (
            "https://shop.example.com/payments/callback/test-payment-123"
        )


class TestFetchPaymentStatus:
    @pytest.mark.parametrize(
        ("payu_status", "expected_event"),
        [
            (OrderStatus.CANCELED, PaymentEvent.FAILED),
            (OrderStatus.COMPLETED, PaymentEvent.PAYMENT_CAPTURED),
            (OrderStatus.WAITING_FOR_CONFIRMATION, PaymentEvent.LOCKED),
        ],
    )
    async def test_status_mapping(
        self, respx_mock, payu_status, expected_event
    ):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.get(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123"
        ).respond(
            json={
                "orders": [
                    {
                        "orderId": "EXT-123",
                        "extOrderId": "test-payment-123",
                        "totalAmount": 10000,
                        "currencyCode": "PLN",
                        "description": "Test",
                        "customerIp": "127.0.0.1",
                        "merchantPosId": "300746",
                        "status": payu_status,
                        "products": [],
                        "buyer": {},
                    }
                ],
                "status": {"statusCode": "SUCCESS", "statusDesc": "OK"},
            },
            status_code=200,
        )

        payment = make_mock_payment(external_id="EXT-123")
        result = await _make_processor(payment=payment).fetch_payment_status()

        assert result is not None
        assert result.payment_event is expected_event

    async def test_pending_status_returns_none(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.get(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123"
        ).respond(
            json={
                "orders": [
                    {"orderId": "EXT-123", "status": OrderStatus.PENDING}
                ],
                "status": {"statusCode": "SUCCESS", "statusDesc": "OK"},
            },
            status_code=200,
        )

        payment = make_mock_payment(external_id="EXT-123")
        result = await _make_processor(payment=payment).fetch_payment_status()

        assert result is None


class TestCharge:
    async def test_charge_success(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.post(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123/captures"
        ).respond(
            json={"status": {"statusCode": "SUCCESS", "statusDesc": "OK"}},
            status_code=200,
        )
        payment = make_mock_payment(external_id="EXT-123")
        payment.amount_locked = Decimal("100.00")

        result = await _make_processor(payment=payment).charge()

        assert result.success is True
        assert result.amount_charged == Decimal("100.00")
        assert result.async_call is False

    async def test_charge_failure_raises(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.post(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123/captures"
        ).respond(json={"error": "Bad request"}, status_code=400)

        with pytest.raises(ChargeFailure):
            await _make_processor(
                payment=make_mock_payment(external_id="EXT-123")
            ).charge()


class TestReleaseLock:
    async def test_release_lock_success(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.delete(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123"
        ).respond(
            json={
                "orderId": "EXT-123",
                "extOrderId": "test-payment-123",
                "status": {"statusCode": "SUCCESS"},
            },
            status_code=200,
        )
        payment = make_mock_payment(external_id="EXT-123")
        payment.amount_locked = Decimal("100.00")

        result = await _make_processor(payment=payment).release_lock()

        assert result == Decimal("100.00")


class TestStartRefund:
    async def test_start_refund_with_amount(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.post(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123/refunds"
        ).respond(
            json={
                "orderId": "EXT-123",
                "refund": {
                    "refundId": "R1",
                    "amount": 5000,
                    "currencyCode": "PLN",
                    "description": "Refund",
                    "creationDateTime": "2024-01-01T00:00:00",
                    "status": "PENDING",
                    "statusDateTime": "2024-01-01T00:00:00",
                },
                "status": {"statusCode": "SUCCESS", "statusDesc": "OK"},
            },
            status_code=200,
        )
        payment = make_mock_payment(external_id="EXT-123")
        payment.amount_paid = Decimal("100.00")

        result = await _make_processor(payment=payment).start_refund(
            amount=Decimal("50.00")
        )

        assert result.amount == Decimal("50.00")
        assert result.provider_data["refund_id"] == "R1"
