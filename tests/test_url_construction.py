"""Tests for URL construction with path prefixes (urljoin bug).

This test module verifies that PayUClient correctly preserves path prefixes
when constructing URLs with urljoin(). The bug manifests when using a base
URL like "http://localhost:9000/payu" — the leading "/" in paths like
"/api/v2_1/orders" causes urljoin to treat them as absolute paths, discarding
the "/payu" prefix.

Example of the bug:
  urljoin("http://localhost:9000/payu", "/api/v2_1/orders")
  Returns: "http://localhost:9000/api/v2_1/orders" (WRONG — lost /payu)
  Should return: "http://localhost:9000/payu/api/v2_1/orders"
"""

from decimal import Decimal

import pytest

from getpaid_payu.client import PayUClient


OAUTH_RESPONSE = {
    "access_token": "test-token-123",
    "token_type": "bearer",
    "expires_in": 43199,
    "grant_type": "client_credentials",
}

# Test cases: (api_url, expected_full_path)
# These represent all 14 urljoin calls in client.py
URL_TEST_CASES = [
    # Test with localhost + path prefix (no trailing slash)
    ("http://localhost:9000/payu", "http://localhost:9000/payu"),
    # Test with localhost + path prefix (with trailing slash)
    ("http://localhost:9000/payu/", "http://localhost:9000/payu"),
    # Test with production URL (standard case, should still work)
    ("https://secure.payu.com/", "https://secure.payu.com"),
]


@pytest.mark.parametrize("api_url,expected_base", URL_TEST_CASES)
class TestURLConstruction:
    """Parametrized tests for URL construction across all 14 endpoints."""

    async def test_authorize_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /pl/standard/user/oauth/authorize endpoint."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client._authorize()

        # Verify the request was made to the correct URL
        assert respx_mock.calls.last.request.url == auth_url

    async def test_new_order_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/orders endpoint (POST)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        orders_url = f"{expected_base}/api/v2_1/orders"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.post(orders_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "orderId": "ORDER123",
                "extOrderId": "ext-1",
                "redirectUri": "https://example.com/redirect",
            },
            status_code=200,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.new_order(
            amount=Decimal("100.00"),
            currency="PLN",
            order_id="ext-1",
        )

        # Verify the POST request was made to the correct URL
        assert respx_mock.calls.last.request.url == orders_url

    async def test_get_order_info_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/orders/{order_id} endpoint (GET)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        order_info_url = f"{expected_base}/api/v2_1/orders/ORDER123"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.get(order_info_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "orders": [{"orderId": "ORDER123", "status": "COMPLETED"}],
            },
            status_code=200,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.get_order_info("ORDER123")

        # Verify the GET request was made to the correct URL
        assert respx_mock.calls.last.request.url == order_info_url

    async def test_cancel_order_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/orders/{order_id} endpoint (DELETE)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        cancel_url = f"{expected_base}/api/v2_1/orders/ORDER123"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.delete(cancel_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
            },
            status_code=200,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.cancel_order("ORDER123")

        # Verify the DELETE request was made to the correct URL
        assert respx_mock.calls.last.request.url == cancel_url

    async def test_capture_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/orders/{order_id}/captures endpoint (POST)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        capture_url = f"{expected_base}/api/v2_1/orders/ORDER123/captures"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.post(capture_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "orderId": "ORDER123",
            },
            status_code=201,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.capture("ORDER123", Decimal("100.00"))

        # Verify the POST request was made to the correct URL
        assert respx_mock.calls.last.request.url == capture_url

    async def test_refund_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/orders/{order_id}/refunds endpoint (POST)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        refund_url = f"{expected_base}/api/v2_1/orders/ORDER123/refunds"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.post(refund_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "orderId": "ORDER123",
            },
            status_code=201,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.refund("ORDER123", Decimal("50.00"))

        # Verify the POST request was made to the correct URL
        assert respx_mock.calls.last.request.url == refund_url

    async def test_get_refunds_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/orders/{order_id}/refunds endpoint (GET)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        refunds_url = f"{expected_base}/api/v2_1/orders/ORDER123/refunds"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.get(refunds_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "refunds": [],
            },
            status_code=200,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.get_refunds("ORDER123")

        # Verify the GET request was made to the correct URL
        assert respx_mock.calls.last.request.url == refunds_url

    async def test_get_payment_methods_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/paymethods endpoint (GET)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        paymethods_url = f"{expected_base}/api/v2_1/paymethods"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.get(paymethods_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "payMethods": {"payMethod": []},
            },
            status_code=200,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.get_payment_methods()

        # Verify the GET request was made to the correct URL
        assert respx_mock.calls.last.request.url == paymethods_url

    async def test_get_transactions_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/orders/{order_id}/transactions endpoint (GET)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        transactions_url = (
            f"{expected_base}/api/v2_1/orders/ORDER123/transactions"
        )

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.get(transactions_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "transactions": [],
            },
            status_code=200,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.get_transaction("ORDER123")

        # Verify the GET request was made to the correct URL
        assert respx_mock.calls.last.request.url == transactions_url

    async def test_get_shop_info_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/shops/{shop_id} endpoint (GET)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        shop_url = f"{expected_base}/api/v2_1/shops/SHOP123"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.get(shop_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "shops": [{"shopId": "SHOP123", "name": "Test Shop"}],
            },
            status_code=200,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.get_shop_info("SHOP123")

        # Verify the GET request was made to the correct URL
        assert respx_mock.calls.last.request.url == shop_url

    async def test_create_payout_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/payouts endpoint (POST)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        payout_url = f"{expected_base}/api/v2_1/payouts"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.post(payout_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "payoutId": "PAYOUT123",
            },
            status_code=201,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.create_payout(
            shop_id="SHOP123",
            amount=10000,
            description="Test payout",
        )

        # Verify the POST request was made to the correct URL
        assert respx_mock.calls.last.request.url == payout_url

    async def test_get_payout_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/payouts/{payout_id} endpoint (GET)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        get_payout_url = f"{expected_base}/api/v2_1/payouts/PAYOUT123"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.get(get_payout_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
                "payout": {"payoutId": "PAYOUT123", "status": "COMPLETED"},
            },
            status_code=200,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.get_payout("PAYOUT123")

        # Verify the GET request was made to the correct URL
        assert respx_mock.calls.last.request.url == get_payout_url

    async def test_delete_token_url_construction(
        self, api_url, expected_base, respx_mock
    ):
        """Test /api/v2_1/tokens/{token} endpoint (DELETE)."""
        auth_url = f"{expected_base}/pl/standard/user/oauth/authorize"
        delete_token_url = f"{expected_base}/api/v2_1/tokens/TOKEN123"

        respx_mock.post(auth_url).respond(json=OAUTH_RESPONSE)
        respx_mock.delete(delete_token_url).respond(
            json={
                "status": {
                    "statusCode": "SUCCESS",
                    "statusDesc": "Request processed",
                },
            },
            status_code=200,
        )

        client = PayUClient(
            api_url=api_url,
            pos_id=300746,
            second_key="b6ca15b0d1020e8094d9b5f8d163db54",
            oauth_id=300746,
            oauth_secret="2ee86a66e5d97e3fadc400c9f19b065d",
        )
        await client.delete_token("TOKEN123")

        # Verify the DELETE request was made to the correct URL
        assert respx_mock.calls.last.request.url == delete_token_url
