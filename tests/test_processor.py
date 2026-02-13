"""Tests for PayUProcessor: prepare, fetch, charge, release, refund."""

from decimal import Decimal

import pytest
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
    """Create a PayUProcessor with defaults."""
    if payment is None:
        payment = make_mock_payment()
    if config is None:
        config = PAYU_CONFIG.copy()
    return PayUProcessor(payment=payment, config=config)


class TestPrepareTransaction:
    """Tests for prepare_transaction."""

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

        processor = _make_processor()
        result = await processor.prepare_transaction()

        assert result["redirect_url"] == "https://payu.com/pay/123"
        assert result["method"] == "GET"
        assert result["form_data"] is None
        assert processor.payment.external_id == "PAYU-ORDER-123"

    async def test_rest_flow_failure_raises_lock_failure(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.post(ORDERS_URL).respond(
            json={"error": "Internal error"},
            status_code=500,
        )

        processor = _make_processor()
        with pytest.raises(LockFailure):
            await processor.prepare_transaction()

    async def test_notify_url_resolved(self, respx_mock):
        """notify_url template is resolved with payment_id."""
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

        processor = _make_processor()
        await processor.prepare_transaction()

        request = route.calls[0].request
        import json

        body = json.loads(request.content)
        assert (
            body["notifyUrl"]
            == "https://shop.example.com/payments/callback/test-payment-123"
        )

    async def test_custom_customer_ip(self, respx_mock):
        """customer_ip kwarg is passed through."""
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

        processor = _make_processor()
        await processor.prepare_transaction(customer_ip="192.168.1.1")

        request = route.calls[0].request
        import json

        body = json.loads(request.content)
        assert body["customerIp"] == "192.168.1.1"


class TestFetchPaymentStatus:
    """Tests for fetch_payment_status."""

    @pytest.mark.parametrize(
        ("payu_status", "expected_callback"),
        [
            (OrderStatus.NEW, "confirm_prepared"),
            (OrderStatus.PENDING, "confirm_prepared"),
            (OrderStatus.CANCELED, "fail"),
            (OrderStatus.COMPLETED, "confirm_payment"),
            (
                OrderStatus.WAITING_FOR_CONFIRMATION,
                "confirm_lock",
            ),
        ],
    )
    async def test_status_mapping(
        self,
        respx_mock,
        payu_status,
        expected_callback,
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
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "OK",
                },
            },
            status_code=200,
        )

        payment = make_mock_payment(external_id="EXT-123")
        processor = _make_processor(payment=payment)
        result = await processor.fetch_payment_status()

        assert result["status"] == expected_callback


class TestCharge:
    """Tests for charge method."""

    async def test_charge_success(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.put(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123/status"
        ).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "OK",
                },
            },
            status_code=200,
        )

        payment = make_mock_payment(external_id="EXT-123")
        payment.amount_locked = Decimal("100.00")
        processor = _make_processor(payment=payment)
        result = await processor.charge()

        assert result["success"] is True
        assert result["amount_charged"] == Decimal("100.00")
        assert result["async_call"] is False

    async def test_charge_with_explicit_amount(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.put(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123/status"
        ).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "OK",
                },
            },
            status_code=200,
        )

        payment = make_mock_payment(external_id="EXT-123")
        payment.amount_locked = Decimal("100.00")
        processor = _make_processor(payment=payment)
        result = await processor.charge(amount=Decimal("50.00"))

        assert result["amount_charged"] == Decimal("50.00")

    async def test_charge_failure_raises(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.put(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123/status"
        ).respond(
            json={"error": "Bad request"},
            status_code=400,
        )

        payment = make_mock_payment(external_id="EXT-123")
        processor = _make_processor(payment=payment)
        with pytest.raises(ChargeFailure):
            await processor.charge()


class TestReleaseLock:
    """Tests for release_lock method."""

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
        processor = _make_processor(payment=payment)
        result = await processor.release_lock()

        assert result == Decimal("100.00")

    async def test_release_lock_non_success_returns_zero(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.delete(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123"
        ).respond(
            json={
                "orderId": "EXT-123",
                "extOrderId": "test-payment-123",
                "status": {"statusCode": "ERROR"},
            },
            status_code=200,
        )

        payment = make_mock_payment(external_id="EXT-123")
        payment.amount_locked = Decimal("100.00")
        processor = _make_processor(payment=payment)
        result = await processor.release_lock()

        assert result == Decimal("0")


class TestStartRefund:
    """Tests for start_refund method."""

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
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "OK",
                },
            },
            status_code=200,
        )

        payment = make_mock_payment(external_id="EXT-123")
        payment.amount_paid = Decimal("100.00")
        processor = _make_processor(payment=payment)
        result = await processor.start_refund(amount=Decimal("50.00"))

        assert result == Decimal("50.00")

    async def test_start_refund_full_amount(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        respx_mock.post(
            "https://secure.snd.payu.com/api/v2_1/orders/EXT-123/refunds"
        ).respond(
            json={
                "orderId": "EXT-123",
                "refund": {
                    "refundId": "R1",
                    "amount": 10000,
                    "currencyCode": "PLN",
                    "description": "Refund",
                    "creationDateTime": "2024-01-01T00:00:00",
                    "status": "PENDING",
                    "statusDateTime": "2024-01-01T00:00:00",
                },
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "OK",
                },
            },
            status_code=200,
        )

        payment = make_mock_payment(external_id="EXT-123")
        payment.amount_paid = Decimal("100.00")
        processor = _make_processor(payment=payment)
        result = await processor.start_refund()

        assert result == Decimal("100.00")


class TestBuildPaywallContext:
    """Tests for _build_paywall_context helper."""

    def test_builds_correct_structure(self):
        processor = _make_processor()
        context = processor._build_paywall_context()

        assert context["order_id"] == "test-payment-123"
        assert context["customer_ip"] == "127.0.0.1"
        assert context["description"] == "Test order"
        assert context["currency"] == "PLN"
        assert context["amount"] == Decimal("100.00")
        assert len(context["products"]) == 1
        assert context["products"][0]["name"] == "Product 1"
        assert context["buyer"]["email"] == "john@example.com"
        assert context["buyer"]["firstName"] == "John"
        assert context["buyer"]["lastName"] == "Doe"

    def test_notify_url_resolved(self):
        processor = _make_processor()
        context = processor._build_paywall_context()

        assert context["notify_url"] == (
            "https://shop.example.com/payments/callback/test-payment-123"
        )

    def test_continue_url_resolved(self):
        processor = _make_processor()
        context = processor._build_paywall_context()

        assert context["continue_url"] == (
            "https://shop.example.com/payments/success/test-payment-123"
        )

    def test_no_notify_url_if_not_configured(self):
        config = PAYU_CONFIG.copy()
        del config["notify_url"]
        processor = _make_processor(config=config)
        context = processor._build_paywall_context()

        assert "notify_url" not in context

    def test_custom_customer_ip(self):
        processor = _make_processor()
        context = processor._build_paywall_context(customer_ip="10.0.0.1")

        assert context["customer_ip"] == "10.0.0.1"


class TestGetClient:
    """Tests for _get_client helper."""

    def test_creates_client_with_sandbox_url(self):
        processor = _make_processor()
        client = processor._get_client()

        assert client.api_url == "https://secure.snd.payu.com/"
        assert client.pos_id == 300746

    def test_creates_client_with_production_url(self):
        config = PAYU_CONFIG.copy()
        config["sandbox"] = False
        processor = _make_processor(config=config)
        client = processor._get_client()

        assert client.api_url == "https://secure.payu.com/"
