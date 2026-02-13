"""Comprehensive tests for PayUClient."""

from decimal import Decimal

import pytest
from getpaid_core.exceptions import ChargeFailure
from getpaid_core.exceptions import CommunicationError
from getpaid_core.exceptions import CredentialsError
from getpaid_core.exceptions import GetPaidException
from getpaid_core.exceptions import LockFailure
from getpaid_core.exceptions import RefundFailure

from getpaid_payu.client import PayUClient


API_URL = "https://secure.payu.com/"
AUTH_URL = "https://secure.payu.com/pl/standard/user/oauth/authorize"
OAUTH_RESPONSE = {
    "access_token": "test-token-123",
    "token_type": "bearer",
    "expires_in": 43199,
    "grant_type": "client_credentials",
}


class TestCentify:
    """Tests for PayUClient._centify class method."""

    def test_simple_amount(self):
        result = PayUClient._centify({"amount": 10})
        assert result == {"amount": "1000"}

    def test_decimal_amount(self):
        result = PayUClient._centify({"amount": Decimal("19.99")})
        assert result == {"amount": "1999"}

    def test_nested_dict(self):
        result = PayUClient._centify(
            {"order": {"totalAmount": Decimal("50.00")}}
        )
        assert result == {"order": {"totalAmount": "5000"}}

    def test_list_of_dicts(self):
        result = PayUClient._centify([{"unitPrice": 10}, {"unitPrice": 20}])
        assert result == [{"unitPrice": "1000"}, {"unitPrice": "2000"}]

    def test_nested_list(self):
        result = PayUClient._centify(
            {"products": [{"unitPrice": Decimal("5.50")}]}
        )
        assert result == {"products": [{"unitPrice": "550"}]}

    def test_deep_nested(self):
        result = PayUClient._centify({"level1": {"level2": {"amount": 100}}})
        assert result == {"level1": {"level2": {"amount": "10000"}}}

    def test_non_convertable_key(self):
        result = PayUClient._centify({"name": "Test Product", "unitPrice": 10})
        assert result == {"name": "Test Product", "unitPrice": "1000"}

    def test_does_not_mutate_original(self):
        original = {"amount": Decimal("10.00")}
        PayUClient._centify(original)
        assert original == {"amount": Decimal("10.00")}

    def test_all_convertable_keys(self):
        data = {
            "amount": 1,
            "total": 2,
            "available": 3,
            "unitPrice": 4,
            "totalAmount": 5,
        }
        result = PayUClient._centify(data)
        assert result == {
            "amount": "100",
            "total": "200",
            "available": "300",
            "unitPrice": "400",
            "totalAmount": "500",
        }

    def test_plain_value(self):
        assert PayUClient._centify("hello") == "hello"
        assert PayUClient._centify(42) == 42

    def test_none_value_in_convertable_key(self):
        """None values in convertable keys are passed through unchanged."""
        result = PayUClient._centify({"amount": None, "name": "Test"})
        assert result == {"amount": None, "name": "Test"}


class TestNormalize:
    """Tests for PayUClient._normalize class method."""

    def test_simple_amount(self):
        result = PayUClient._normalize({"amount": 1000})
        assert result == {"amount": Decimal("10")}

    def test_string_amount(self):
        result = PayUClient._normalize({"amount": "1999"})
        assert result == {"amount": Decimal("19.99")}

    def test_nested_dict(self):
        result = PayUClient._normalize({"order": {"totalAmount": 5000}})
        assert result == {"order": {"totalAmount": Decimal("50")}}

    def test_list_of_dicts(self):
        result = PayUClient._normalize(
            [{"unitPrice": 1000}, {"unitPrice": 2000}]
        )
        assert result == [
            {"unitPrice": Decimal("10")},
            {"unitPrice": Decimal("20")},
        ]

    def test_nested_list(self):
        result = PayUClient._normalize({"products": [{"unitPrice": 550}]})
        assert result == {"products": [{"unitPrice": Decimal("5.50")}]}

    def test_deep_nested(self):
        result = PayUClient._normalize(
            {"level1": {"level2": {"amount": 10000}}}
        )
        assert result == {"level1": {"level2": {"amount": Decimal("100")}}}

    def test_non_convertable_key(self):
        result = PayUClient._normalize(
            {"name": "Test Product", "unitPrice": 1000}
        )
        assert result == {
            "name": "Test Product",
            "unitPrice": Decimal("10"),
        }

    def test_does_not_mutate_original(self):
        original = {"amount": 1000}
        PayUClient._normalize(original)
        assert original == {"amount": 1000}

    def test_all_convertable_keys(self):
        data = {
            "amount": 100,
            "total": 200,
            "available": 300,
            "unitPrice": 400,
            "totalAmount": 500,
        }
        result = PayUClient._normalize(data)
        assert result == {
            "amount": Decimal("1"),
            "total": Decimal("2"),
            "available": Decimal("3"),
            "unitPrice": Decimal("4"),
            "totalAmount": Decimal("5"),
        }

    def test_plain_value(self):
        assert PayUClient._normalize("hello") == "hello"
        assert PayUClient._normalize(42) == 42

    def test_none_value_in_convertable_key(self):
        """None values in convertable keys are passed through unchanged."""
        result = PayUClient._normalize({"amount": None, "name": "Test"})
        assert result == {"amount": None, "name": "Test"}


@pytest.fixture()
async def payu_client(respx_mock):
    """Create a PayUClient with a mocked OAuth endpoint."""
    respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
    client = PayUClient(
        api_url=API_URL,
        pos_id=300746,
        second_key="b6ca15b0d1020e8094d9b5f8d163db54",
        oauth_id=300746,
        oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
    )
    await client._authorize()
    return client


class TestAuth:
    """Tests for OAuth2 authorization."""

    async def test_authorize_success(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        client = PayUClient(
            api_url=API_URL,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client._authorize()
        assert client._token == "Bearer test-token-123"
        assert client._token_expires_at > 0

    async def test_authorize_failure(self, respx_mock):
        respx_mock.post(AUTH_URL).respond(status_code=401)
        client = PayUClient(
            api_url=API_URL,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        with pytest.raises(CredentialsError, match="Cannot authenticate"):
            await client._authorize()

    async def test_ensure_auth_lazy_authorization(self, respx_mock):
        """Token is obtained lazily on first API call."""
        auth_route = respx_mock.post(AUTH_URL).respond(json=OAUTH_RESPONSE)
        order_response = {
            "status": {
                "statusCode": "SUCCESS",
                "statusDesc": "Request processed",
            },
            "orderId": "ORDER123",
            "extOrderId": "ext-1",
            "redirectUri": "https://example.com/redirect",
        }
        respx_mock.post("https://secure.payu.com/api/v2_1/orders").respond(
            json=order_response, status_code=200
        )

        client = PayUClient(
            api_url=API_URL,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        assert client._token is None
        await client.new_order(
            amount=Decimal("100.00"),
            currency="PLN",
            order_id="ext-1",
        )
        assert client._token == "Bearer test-token-123"
        assert auth_route.call_count == 1


class TestNewOrder:
    """Tests for new_order API method."""

    @pytest.mark.parametrize("status_code", [200, 201, 302])
    async def test_new_order_success(
        self, payu_client, respx_mock, status_code
    ):
        order_response = {
            "status": {
                "statusCode": "SUCCESS",
                "statusDesc": "Request processed",
            },
            "orderId": "ORDER123",
            "extOrderId": "ext-1",
            "redirectUri": "https://example.com/redirect",
        }
        respx_mock.post("https://secure.payu.com/api/v2_1/orders").respond(
            json=order_response, status_code=status_code
        )

        result = await payu_client.new_order(
            amount=Decimal("100.00"),
            currency="PLN",
            order_id="ext-1",
            description="Test order",
        )
        assert result["orderId"] == "ORDER123"
        assert result["extOrderId"] == "ext-1"

    @pytest.mark.parametrize("status_code", [400, 401, 403, 500])
    async def test_new_order_failure(
        self, payu_client, respx_mock, status_code
    ):
        respx_mock.post("https://secure.payu.com/api/v2_1/orders").respond(
            json={"error": "Bad request"},
            status_code=status_code,
        )
        with pytest.raises(LockFailure, match="Error creating order"):
            await payu_client.new_order(
                amount=Decimal("100.00"),
                currency="PLN",
                order_id="ext-1",
            )


class TestRefund:
    """Tests for refund API method."""

    async def test_refund_success(self, payu_client, respx_mock):
        refund_response = {
            "orderId": "ORDER123",
            "refund": {
                "refundId": "REF1",
                "amount": 5000,
                "currencyCode": "PLN",
                "description": "Refund",
                "creationDateTime": "2024-01-01T00:00:00",
                "status": "PENDING",
                "statusDateTime": "2024-01-01T00:00:00",
            },
            "status": {
                "statusCode": "SUCCESS",
                "statusDesc": "Refund queued",
            },
        }
        respx_mock.post(
            "https://secure.payu.com/api/v2_1/orders/ORDER123/refunds"
        ).respond(json=refund_response, status_code=200)

        result = await payu_client.refund(
            order_id="ORDER123",
            amount=Decimal("50.00"),
            description="Customer refund",
        )
        assert result["orderId"] == "ORDER123"
        assert result["refund"]["amount"] == Decimal("50")

    async def test_refund_failure(self, payu_client, respx_mock):
        respx_mock.post(
            "https://secure.payu.com/api/v2_1/orders/ORDER123/refunds"
        ).respond(
            json={"error": "Not found"},
            status_code=404,
        )
        with pytest.raises(RefundFailure, match="Error creating refund"):
            await payu_client.refund(order_id="ORDER123")


class TestCancelOrder:
    """Tests for cancel_order API method."""

    async def test_cancel_order_success(self, payu_client, respx_mock):
        cancel_response = {
            "orderId": "ORDER123",
            "extOrderId": "ext-1",
            "status": {"statusCode": "SUCCESS"},
        }
        respx_mock.delete(
            "https://secure.payu.com/api/v2_1/orders/ORDER123"
        ).respond(json=cancel_response, status_code=200)

        result = await payu_client.cancel_order(order_id="ORDER123")
        assert result["orderId"] == "ORDER123"

    async def test_cancel_order_failure(self, payu_client, respx_mock):
        respx_mock.delete(
            "https://secure.payu.com/api/v2_1/orders/ORDER123"
        ).respond(
            json={"error": "Not found"},
            status_code=404,
        )
        with pytest.raises(GetPaidException, match="Error cancelling order"):
            await payu_client.cancel_order(order_id="ORDER123")


class TestCapture:
    """Tests for capture API method."""

    async def test_capture_success(self, payu_client, respx_mock):
        capture_response = {
            "status": {
                "statusCode": "SUCCESS",
                "statusDesc": "Status was updated",
            },
        }
        respx_mock.post(
            "https://secure.payu.com/api/v2_1/orders/ORDER123/captures"
        ).respond(json=capture_response, status_code=200)

        result = await payu_client.capture(order_id="ORDER123")
        assert result["status"]["statusCode"] == "SUCCESS"

    async def test_capture_failure(self, payu_client, respx_mock):
        respx_mock.post(
            "https://secure.payu.com/api/v2_1/orders/ORDER123/captures"
        ).respond(
            json={"error": "Bad request"},
            status_code=400,
        )
        with pytest.raises(
            ChargeFailure, match="Error charging locked payment"
        ):
            await payu_client.capture(order_id="ORDER123")


class TestGetOrderInfo:
    """Tests for get_order_info API method."""

    async def test_get_order_info_success(self, payu_client, respx_mock):
        order_info_response = {
            "orders": [
                {
                    "orderId": "ORDER123",
                    "extOrderId": "ext-1",
                    "totalAmount": 10000,
                    "currencyCode": "PLN",
                    "description": "Test",
                    "customerIp": "127.0.0.1",
                    "merchantPosId": "300746",
                    "status": "COMPLETED",
                    "products": [],
                    "buyer": {},
                }
            ],
            "status": {
                "statusCode": "SUCCESS",
                "statusDesc": "Request processed",
            },
        }
        respx_mock.get(
            "https://secure.payu.com/api/v2_1/orders/ORDER123"
        ).respond(json=order_info_response, status_code=200)

        result = await payu_client.get_order_info(order_id="ORDER123")
        assert result["orders"][0]["orderId"] == "ORDER123"
        assert result["orders"][0]["totalAmount"] == Decimal("100")

    async def test_get_order_info_failure(self, payu_client, respx_mock):
        respx_mock.get(
            "https://secure.payu.com/api/v2_1/orders/ORDER123"
        ).respond(
            json={"error": "Not found"},
            status_code=404,
        )
        with pytest.raises(CommunicationError):
            await payu_client.get_order_info(order_id="ORDER123")


class TestGetShopInfo:
    """Tests for get_shop_info API method."""

    async def test_get_shop_info_success(self, payu_client, respx_mock):
        shop_response = {
            "shopId": "SHOP1",
            "name": "Test Shop",
            "currencyCode": "PLN",
        }
        respx_mock.get("https://secure.payu.com/api/v2_1/shops/SHOP1").respond(
            json=shop_response, status_code=200
        )

        result = await payu_client.get_shop_info(shop_id="SHOP1")
        assert result["shopId"] == "SHOP1"
        assert result["name"] == "Test Shop"

    async def test_get_shop_info_failure(self, payu_client, respx_mock):
        respx_mock.get("https://secure.payu.com/api/v2_1/shops/SHOP1").respond(
            json={"error": "Unauthorized"},
            status_code=401,
        )
        with pytest.raises(CommunicationError, match="Error getting shop info"):
            await payu_client.get_shop_info(shop_id="SHOP1")
