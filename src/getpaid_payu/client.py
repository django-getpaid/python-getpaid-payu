"""Async HTTP client for PayU REST API."""

import json
import time
from collections.abc import Callable
from copy import deepcopy
from decimal import Decimal
from functools import wraps
from typing import ClassVar
from urllib.parse import urljoin

import httpx
from getpaid_core.exceptions import ChargeFailure
from getpaid_core.exceptions import CommunicationError
from getpaid_core.exceptions import CredentialsError
from getpaid_core.exceptions import GetPaidException
from getpaid_core.exceptions import LockFailure
from getpaid_core.exceptions import RefundFailure

from .types import BuyerData
from .types import CancellationResponse
from .types import ChargeResponse
from .types import Currency
from .types import PaymentMethodsResponse
from .types import PaymentResponse
from .types import PayoutResponse
from .types import ProductData
from .types import RefundDetailRecord
from .types import RefundResponse
from .types import RetrieveOrderInfoResponse
from .types import ShopInfoResponse
from .types import TransactionResponse


def ensure_auth(func: Callable) -> Callable:
    """Decorator ensuring the client is authenticated before API calls."""

    @wraps(func)
    async def _f(self: "PayUClient", *args, **kwargs):
        if self._token is None or time.monotonic() > self._token_expires_at - 5:
            await self._authorize()
        return await func(self, *args, **kwargs)

    return _f


class PayUClient:
    """Async client for PayU REST API.

    Uses ``httpx.AsyncClient`` for all HTTP communication.
    OAuth2 token is lazily obtained on the first API call via the
    ``ensure_auth`` decorator.

    Can be used as an async context manager for connection reuse::

        async with PayUClient(...) as client:
            await client.new_order(...)
            await client.refund(...)
    """

    last_response: httpx.Response | None = None
    _convertables: ClassVar[set[str]] = {
        "amount",
        "total",
        "available",
        "unitPrice",
        "totalAmount",
    }

    def __init__(
        self,
        api_url: str,
        pos_id: int,
        second_key: str,
        oauth_id: int,
        oauth_secret: str,
    ) -> None:
        self.api_url = api_url
        self.pos_id = pos_id
        self.second_key = second_key
        self.oauth_id = oauth_id
        self.oauth_secret = oauth_secret
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._client: httpx.AsyncClient | None = None
        self._owns_client: bool = False

    async def __aenter__(self) -> "PayUClient":
        self._client = httpx.AsyncClient()
        self._owns_client = True
        return self

    async def __aexit__(self, *exc) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
            self._owns_client = False

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Return the shared client or create a one-shot client."""
        if self._client is not None:
            return self._client
        # Fallback: create a new client per request (no reuse)
        return httpx.AsyncClient()

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        content: str | None = None,
        follow_redirects: bool = True,
    ) -> httpx.Response:
        """Execute an HTTP request, handling client lifecycle."""
        if self._client is not None:
            return await self._client.request(
                method,
                url,
                headers=headers,
                content=content,
                follow_redirects=follow_redirects,
            )
        # No shared client — create and close one for this request
        async with httpx.AsyncClient() as client:
            return await client.request(
                method,
                url,
                headers=headers,
                content=content,
                follow_redirects=follow_redirects,
            )

    async def _authorize(self) -> None:
        """Obtain OAuth2 access token from PayU."""
        url = urljoin(self.api_url, "/pl/standard/user/oauth/authorize")
        # Auth uses form data, not JSON — use a dedicated client call
        if self._client is not None:
            self.last_response = await self._client.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.oauth_id,
                    "client_secret": self.oauth_secret,
                },
            )
        else:
            async with httpx.AsyncClient() as client:
                self.last_response = await client.post(
                    url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.oauth_id,
                        "client_secret": self.oauth_secret,
                    },
                )
        if self.last_response.status_code == 200:
            data = self.last_response.json()
            self._token = (
                f"{data['token_type'].capitalize()} {data['access_token']}"
            )
            self._token_expires_at = time.monotonic() + int(data["expires_in"])
        else:
            raise CredentialsError(
                "Cannot authenticate.",
                context={"raw_response": self.last_response},
            )

    def _headers(self) -> dict[str, str]:
        """Build request headers with authorization."""
        return {
            "Authorization": self._token or "",
            "Content-Type": "application/json",
        }

    @classmethod
    def _centify(
        cls,
        data: dict | list | Decimal | int | float | str,
    ) -> dict | list | str | Decimal | int | float:
        """Convert amount values to PayU's centified string format.

        Traverses the data structure recursively and multiplies
        values of convertable keys by 100, returning them as strings.
        None values in convertable keys are passed through unchanged.
        """
        data = deepcopy(data)
        if hasattr(data, "items"):
            return {
                k: (
                    str(int(v * 100))
                    if k in cls._convertables and v is not None
                    else cls._centify(v)
                )
                for k, v in data.items()  # type: ignore[union-attr]
            }
        elif isinstance(data, list):
            return [cls._centify(v) for v in data]
        return data

    @classmethod
    def _normalize(
        cls,
        data: dict | list | Decimal | int | float | str,
    ) -> dict | list | Decimal | int | float | str:
        """Convert PayU's centified values back to normal Decimals.

        Traverses the data structure recursively and divides
        values of convertable keys by 100, returning Decimals.
        None values in convertable keys are passed through unchanged.
        """
        data = deepcopy(data)
        if hasattr(data, "items"):
            return {
                k: (
                    Decimal(v) / 100
                    if k in cls._convertables and v is not None
                    else cls._normalize(v)
                )
                for k, v in data.items()  # type: ignore[union-attr]
            }
        elif isinstance(data, list):
            return [cls._normalize(v) for v in data]
        return data

    @ensure_auth
    async def new_order(
        self,
        amount: Decimal | float,
        currency: Currency,
        order_id: str | int,
        description: str | None = None,
        customer_ip: str | None = None,
        buyer: BuyerData | None = None,
        products: list[ProductData] | None = None,
        notify_url: str | None = None,
        continue_url: str | None = None,
        validity_time: str | int | None = None,
        additional_description: str | None = None,
        visible_description: str | None = None,
        statement_description: str | None = None,
        card_on_file: str | None = None,
        recurring: str | None = None,
        pay_methods: dict | None = None,
        three_ds_authentication: dict | None = None,
        risk_data: dict | None = None,
        device_fingerprint: str | None = None,
        shopping_carts: list[dict] | None = None,
        submerchant: dict | None = None,
        credit: dict | None = None,
        mcp_data: dict | None = None,
        settings: dict | None = None,
        donation: dict | None = None,
        **kwargs,
    ) -> PaymentResponse:
        """Register a new order within PayU API.

        :param amount: Payment amount.
        :param currency: ISO 4217 currency code.
        :param order_id: External order identifier.
        :param description: Short description of the order.
        :param customer_ip: Customer's IP address (defaults to "127.0.0.1").
        :param buyer: Buyer data dictionary.
        :param products: List of product data dictionaries.
        :param notify_url: Callback URL for notifications.
        :param continue_url: URL to redirect the customer after payment.
        :param validity_time: Order validity time in seconds.
        :param additional_description: Additional order description.
        :param visible_description: Description visible to the buyer.
        :param statement_description: Description for bank statement.
        :param card_on_file: Card-on-file indicator (e.g. "FIRST", "STANDARD").
        :param recurring: Recurring payment indicator
            (e.g. "FIRST", "STANDARD").
        :param pay_methods: Payment methods configuration.
        :param three_ds_authentication: 3DS authentication data.
        :param risk_data: Risk assessment data.
        :param device_fingerprint: Device fingerprint string.
        :param shopping_carts: List of shopping cart entries.
        :param submerchant: Submerchant (marketplace) data.
        :param credit: Credit/installment data.
        :param mcp_data: Multi-currency pricing data.
        :param settings: Order settings (e.g. invoice disabled).
        :param donation: Donation data.
        :param kwargs: Extra params passed to order data
            for forward compatibility.
        :return: Normalized JSON response from API.
        """
        url = urljoin(self.api_url, "/api/v2_1/orders")
        data = self._centify(
            {
                "extOrderId": order_id,
                "customerIp": customer_ip if customer_ip else "127.0.0.1",
                "merchantPosId": str(self.pos_id),
                "description": description if description else "Payment order",
                "currencyCode": currency.upper(),
                "totalAmount": amount,
                "products": products
                if products
                else [
                    {
                        "name": "Total order",
                        "unitPrice": amount,
                        "quantity": 1,
                    }
                ],
            }
        )
        optional_fields = {
            "notifyUrl": notify_url,
            "continueUrl": continue_url,
            "validityTime": validity_time,
            "additionalDescription": additional_description,
            "visibleDescription": visible_description,
            "statementDescription": statement_description,
            "cardOnFile": card_on_file,
            "recurring": recurring,
            "payMethods": pay_methods,
            "threeDsAuthentication": three_ds_authentication,
            "riskData": risk_data,
            "deviceFingerprint": device_fingerprint,
            "shoppingCarts": shopping_carts,
            "submerchant": submerchant,
            "credit": credit,
            "mcpData": mcp_data,
            "settings": settings,
            "donation": donation,
        }
        for key, value in optional_fields.items():
            if value is not None:
                data[key] = value  # type: ignore[index]
        if buyer:
            data["buyer"] = buyer  # type: ignore[index]
        data.update(kwargs)  # type: ignore[union-attr]
        encoded = json.dumps(data, default=str)
        self.last_response = await self._request(
            "POST",
            url,
            headers=self._headers(),
            content=encoded,
            follow_redirects=False,
        )
        if self.last_response.status_code in [200, 201, 302]:
            return self._normalize(self.last_response.json())  # type: ignore[return-value]
        raise LockFailure(
            "Error creating order",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def refund(
        self,
        order_id: str,
        amount: Decimal | float | None = None,
        description: str | None = None,
        ext_refund_id: str | None = None,
        currency_code: str | None = None,
        bank_description: str | None = None,
        refund_type: str | None = None,
    ) -> RefundResponse:
        """Request a refund for an existing order.

        :param order_id: PayU order identifier.
        :param amount: Optional partial refund amount.
        :param description: Refund description.
        :param ext_refund_id: External refund identifier.
        :param currency_code: ISO 4217 currency code.
        :param bank_description: Bank operation description.
        :param refund_type: Refund type ("REFUND_PAYMENT_STANDARD" or "FAST").
        :return: Normalized JSON response from API.
        """
        url = urljoin(self.api_url, f"/api/v2_1/orders/{order_id}/refunds")
        refund_data: dict = {
            "description": description if description else "Refund",
        }
        if amount is not None:
            refund_data["amount"] = amount
        if ext_refund_id is not None:
            refund_data["extRefundId"] = ext_refund_id
        if currency_code is not None:
            refund_data["currencyCode"] = currency_code
        if bank_description is not None:
            refund_data["bankDescription"] = bank_description
        if refund_type is not None:
            refund_data["type"] = refund_type
        encoded = json.dumps(
            {"refund": self._centify(refund_data)},
            default=str,
        )
        self.last_response = await self._request(
            "POST",
            url,
            headers=self._headers(),
            content=encoded,
        )
        if self.last_response.status_code == 200:
            return self._normalize(self.last_response.json())  # type: ignore[return-value]
        raise RefundFailure(
            "Error creating refund",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def cancel_order(self, order_id: str) -> CancellationResponse:
        """Cancel an existing order.

        :param order_id: PayU order identifier.
        :return: Normalized JSON response from API.
        """
        url = urljoin(self.api_url, f"/api/v2_1/orders/{order_id}")
        self.last_response = await self._request(
            "DELETE",
            url,
            headers=self._headers(),
        )
        if self.last_response.status_code == 200:
            return self._normalize(self.last_response.json())  # type: ignore[return-value]
        raise GetPaidException(
            "Error cancelling order",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def capture(self, order_id: str) -> ChargeResponse:
        """Capture (charge) a previously authorized order.

        Uses the new POST /captures endpoint (the PUT /status
        endpoint is deprecated).

        :param order_id: PayU order identifier.
        :return: Normalized JSON response from API.
        """
        url = urljoin(self.api_url, f"/api/v2_1/orders/{order_id}/captures")
        self.last_response = await self._request(
            "POST",
            url,
            headers=self._headers(),
        )
        if self.last_response.status_code == 200:
            return self._normalize(self.last_response.json())  # type: ignore[return-value]
        raise ChargeFailure(
            "Error charging locked payment",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def get_order_info(self, order_id: str) -> RetrieveOrderInfoResponse:
        """Retrieve order details from PayU.

        :param order_id: PayU order identifier.
        :return: Normalized JSON response from API.
        """
        url = urljoin(self.api_url, f"/api/v2_1/orders/{order_id}")
        self.last_response = await self._request(
            "GET",
            url,
            headers=self._headers(),
        )
        if self.last_response.status_code == 200:
            return self._normalize(self.last_response.json())  # type: ignore[return-value]
        raise CommunicationError(
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def get_shop_info(self, shop_id: str) -> ShopInfoResponse:
        """Retrieve shop information from PayU.

        :param shop_id: Public shop identifier.
        :return: Normalized JSON response from API.
        """
        url = urljoin(self.api_url, f"/api/v2_1/shops/{shop_id}")
        self.last_response = await self._request(
            "GET",
            url,
            headers=self._headers(),
        )
        if self.last_response.status_code == 200:
            return self._normalize(self.last_response.json())  # type: ignore[return-value]
        raise CommunicationError(
            "Error getting shop info",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def get_payment_methods(
        self, lang: str | None = None
    ) -> PaymentMethodsResponse:
        """Retrieve all available payment methods.

        :param lang: ISO 639-1 language code for method names.
        :return: Payment methods response.
        """
        url = urljoin(self.api_url, "/api/v2_1/paymethods")
        if lang:
            url = f"{url}?lang={lang}"
        self.last_response = await self._request(
            "GET",
            url,
            headers=self._headers(),
        )
        if self.last_response.status_code == 200:
            return self.last_response.json()
        raise CommunicationError(
            "Error retrieving payment methods",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def get_transaction(self, order_id: str) -> TransactionResponse:
        """Retrieve transaction details for an order.

        :param order_id: PayU order identifier.
        :return: Transaction response.
        """
        url = urljoin(self.api_url, f"/api/v2_1/orders/{order_id}/transactions")
        self.last_response = await self._request(
            "GET",
            url,
            headers=self._headers(),
        )
        if self.last_response.status_code == 200:
            return self.last_response.json()
        raise CommunicationError(
            "Error retrieving transaction",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def get_refunds(self, order_id: str) -> list[RefundDetailRecord]:
        """Retrieve all refunds for an order.

        :param order_id: PayU order identifier.
        :return: List of refund records.
        """
        url = urljoin(self.api_url, f"/api/v2_1/orders/{order_id}/refunds")
        self.last_response = await self._request(
            "GET",
            url,
            headers=self._headers(),
        )
        if self.last_response.status_code == 200:
            return self.last_response.json()
        raise CommunicationError(
            "Error retrieving refunds",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def get_refund(
        self, order_id: str, refund_id: str
    ) -> RefundDetailRecord:
        """Retrieve a specific refund for an order.

        :param order_id: PayU order identifier.
        :param refund_id: PayU refund identifier.
        :return: Refund detail record.
        """
        url = urljoin(
            self.api_url,
            f"/api/v2_1/orders/{order_id}/refunds/{refund_id}",
        )
        self.last_response = await self._request(
            "GET",
            url,
            headers=self._headers(),
        )
        if self.last_response.status_code == 200:
            return self.last_response.json()
        raise CommunicationError(
            "Error retrieving refund",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def create_payout(
        self,
        shop_id: str,
        amount: int | None = None,
        description: str | None = None,
        ext_payout_id: str | None = None,
    ) -> PayoutResponse:
        """Create a payout to withdraw funds from PayU account.

        :param shop_id: PayU shop identifier.
        :param amount: Payout amount in lowest currency unit.
            If None, full available balance.
        :param description: Payout description.
        :param ext_payout_id: External payout identifier.
        :return: Payout response.
        """
        url = urljoin(self.api_url, "/api/v2_1/payouts")
        payout_data: dict = {"shopId": shop_id}
        payout_obj: dict = {}
        if amount is not None:
            payout_obj["amount"] = amount
        if description is not None:
            payout_obj["description"] = description
        if ext_payout_id is not None:
            payout_obj["extPayoutId"] = ext_payout_id
        if payout_obj:
            payout_data["payout"] = payout_obj
        encoded = json.dumps(payout_data, default=str)
        self.last_response = await self._request(
            "POST",
            url,
            headers=self._headers(),
            content=encoded,
        )
        if self.last_response.status_code == 200:
            return self.last_response.json()
        raise GetPaidException(
            "Error creating payout",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def get_payout(self, payout_id: str) -> PayoutResponse:
        """Retrieve payout details.

        :param payout_id: PayU payout identifier.
        :return: Payout response.
        """
        url = urljoin(self.api_url, f"/api/v2_1/payouts/{payout_id}")
        self.last_response = await self._request(
            "GET",
            url,
            headers=self._headers(),
        )
        if self.last_response.status_code == 200:
            return self.last_response.json()
        raise CommunicationError(
            "Error retrieving payout",
            context={"raw_response": self.last_response},
        )

    @ensure_auth
    async def delete_token(self, token: str) -> None:
        """Delete a stored payment token.

        :param token: The token value to delete.
        """
        url = urljoin(self.api_url, f"/api/v2_1/tokens/{token}")
        self.last_response = await self._request(
            "DELETE",
            url,
            headers=self._headers(),
        )
        if self.last_response.status_code in [200, 204]:
            return
        raise GetPaidException(
            "Error deleting token",
            context={"raw_response": self.last_response},
        )
