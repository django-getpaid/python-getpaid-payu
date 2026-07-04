"""PayU payment processor."""

import hashlib
import hmac
import logging
from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from typing import ClassVar

import httpx
from getpaid_core.enums import PaymentEvent
from getpaid_core.exceptions import InvalidCallbackError
from getpaid_core.processor import BaseProcessor
from getpaid_core.types import ChargeResult as CoreChargeResult
from getpaid_core.types import PaymentUpdate
from getpaid_core.types import RefundResult
from getpaid_core.types import TransactionResult

from .client import PayUClient
from .types import Currency
from .types import OrderStatus
from .types import RefundStatus
from .types import ResponseStatus


logger = logging.getLogger(__name__)

_SUPPORTED_ALGORITHMS: dict[str, Any] = {
    "MD5": hashlib.md5,
    "SHA-256": hashlib.sha256,
    "SHA256": hashlib.sha256,
}


class PayUProcessor(BaseProcessor):
    """PayU payment gateway processor."""

    slug: ClassVar[str] = "payu"
    display_name: ClassVar[str] = "PayU"
    accepted_currencies: ClassVar[Sequence[str]] = [c.value for c in Currency]
    sandbox_url: ClassVar[str] = "https://secure.snd.payu.com/"
    production_url: ClassVar[str] = "https://secure.payu.com/"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._client: PayUClient | None = None

    def _get_client(self) -> PayUClient:
        """Return the cached PayUClient, creating it on first use.

        The client (and its OAuth token) is reused for the lifetime of
        the processor instance instead of re-authorizing per operation.
        Call :meth:`aclose` when done to release the HTTP connection.
        """
        if self._client is None:
            self._client = PayUClient(
                api_url=self.get_paywall_baseurl(),
                pos_id=int(self.get_setting("pos_id", 0)),
                second_key=str(self.get_setting("second_key", "")),
                oauth_id=int(self.get_setting("oauth_id", 0)),
                oauth_secret=str(self.get_setting("oauth_secret", "")),
                timeout=httpx.Timeout(
                    float(self.get_setting("timeout", 10.0)),
                    connect=float(self.get_setting("connect_timeout", 5.0)),
                ),
            )
        return self._client

    async def aclose(self) -> None:
        """Close the cached client and its HTTP connections."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "PayUProcessor":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    def _resolve_url(self, url_template: str) -> str:
        """Replace {payment_id} and {order_id} placeholders."""
        return url_template.format(
            payment_id=self.payment.id,
            order_id=self.payment.id,
        )

    def _build_paywall_context(self, **kwargs) -> dict:
        """Build PayU order data from payment object.

        Converts from core's snake_case protocol to PayU's
        camelCase API format.
        """
        raw_items = self.payment.order.get_items()
        products = [
            {
                "name": item["name"],
                "unitPrice": item["unit_price"],
                "quantity": item["quantity"],
            }
            for item in raw_items
        ]
        buyer = self.payment.order.get_buyer_info()
        buyer_data = {}
        if buyer.get("email"):
            buyer_data["email"] = buyer["email"]
        if buyer.get("first_name"):
            buyer_data["firstName"] = buyer["first_name"]
        if buyer.get("last_name"):
            buyer_data["lastName"] = buyer["last_name"]
        if buyer.get("phone"):
            buyer_data["phone"] = buyer["phone"]

        context = {
            "order_id": self.payment.id,
            "customer_ip": kwargs.get("customer_ip", "127.0.0.1"),
            "description": self.payment.description,
            "currency": self.payment.currency,
            "amount": self.payment.amount_required,
            "products": products,
        }

        if buyer_data:
            context["buyer"] = buyer_data

        notify_url = self.get_setting("notify_url")
        if notify_url:
            context["notify_url"] = self._resolve_url(notify_url)

        continue_url = self.get_setting("continue_url")
        if continue_url:
            context["continue_url"] = self._resolve_url(continue_url)

        return context

    async def prepare_transaction(self, **kwargs) -> TransactionResult:
        """Prepare a PayU payment order.

        Creates order via PayU API and returns redirect URL.
        """
        client = self._get_client()
        context = self._build_paywall_context(**kwargs)
        response = await client.new_order(**context)
        return TransactionResult(
            method="GET",
            redirect_url=response.get("redirectUri"),
            external_id=response.get("orderId") or None,
            provider_data={"payu_status": response.get("status", {})},
        )

    async def verify_callback(
        self, data: dict, headers: dict, **kwargs
    ) -> None:
        """Verify PayU callback signature.

        Expects:
        - raw_body kwarg (preferred) or data["_raw_body"]
        - headers with openpayu-signature/x-openpayu-signature

        Raises InvalidCallbackError if signature is missing,
        invalid, or _raw_body is not provided.
        """
        raw_body = kwargs.get("raw_body")
        if raw_body is None:
            raw_body = data.get("_raw_body")
        if raw_body is None:
            raise InvalidCallbackError(
                "Missing raw_body in callback data. "
                "The framework adapter must pass the raw HTTP body string."
            )
        if isinstance(raw_body, bytes | bytearray):
            raw_body = raw_body.decode("utf-8")
        if not isinstance(raw_body, str):
            raise InvalidCallbackError("raw_body must be a str or bytes value.")

        normalized_headers = {k.lower(): v for k, v in headers.items()}

        raw_header = (
            normalized_headers.get("openpayu-signature")
            or normalized_headers.get("x-openpayu-signature")
            or ""
        )
        if not raw_header:
            raise InvalidCallbackError("NO SIGNATURE")

        parsed = dict(
            item.split("=", 1) for item in raw_header.split(";") if "=" in item
        )
        allow_md5 = bool(self.get_setting("allow_md5_callbacks", False))
        default_algorithm = "MD5" if allow_md5 else "SHA-256"
        algo_name = parsed.get("algorithm", default_algorithm).upper()
        signature = parsed.get("signature", "")
        second_key = self.get_setting("second_key")

        if not signature:
            raise InvalidCallbackError("NO SIGNATURE")

        if algo_name == "MD5" and not allow_md5:
            raise InvalidCallbackError(
                "MD5 signatures are disabled by default. "
                "Set allow_md5_callbacks=True to allow legacy callbacks."
            )

        algorithm = _SUPPORTED_ALGORITHMS.get(algo_name)
        if algorithm is None:
            raise InvalidCallbackError(
                f"Unsupported hash algorithm: {algo_name}. "
                f"Supported: {', '.join(sorted(_SUPPORTED_ALGORITHMS))}"
            )

        expected = algorithm(f"{raw_body}{second_key}".encode()).hexdigest()

        # SECURITY: never log or return the expected digest — that would
        # turn this endpoint into a signature oracle for forged callbacks.
        # Logging the *received* (attacker-supplied) signature is fine.
        if not hmac.compare_digest(expected, signature):
            logger.error(
                "Received bad signature for payment %s! Got '%s'",
                self.payment.id,
                signature,
            )
            raise InvalidCallbackError(
                "BAD SIGNATURE: callback signature verification failed"
            )

    async def handle_callback(
        self, data: dict, headers: dict, **kwargs
    ) -> PaymentUpdate | None:
        """Handle PayU PUSH callback and return a semantic update.

        The callback is cross-checked against the local payment:
        ``extOrderId`` must match the payment id, ``currencyCode`` must
        match the payment's currency, and status changes that carry
        money (COMPLETED, WAITING_FOR_CONFIRMATION) must declare a
        positive ``totalAmount`` — a missing or zero amount is rejected
        rather than silently substituted with the local expectation.
        """
        if "order" in data:
            order_data = data["order"]

            ext_order_id = order_data.get("extOrderId")
            if ext_order_id is None or str(ext_order_id) != str(
                self.payment.id
            ):
                raise InvalidCallbackError(
                    "Callback extOrderId does not match the local payment"
                )

            currency = order_data.get("currencyCode")
            if (
                currency is None
                or str(currency).upper() != str(self.payment.currency).upper()
            ):
                raise InvalidCallbackError(
                    "Callback currency does not match the payment currency"
                )

            status = order_data.get("status")
            raw_amount = order_data.get("totalAmount")
            amount = (
                Decimal(str(raw_amount)) / 100
                if raw_amount is not None
                else None
            )
            external_id = order_data.get("orderId") or self.payment.external_id
            provider_event_id = f"order:{external_id}:{status}"
            if (
                status
                in (
                    OrderStatus.COMPLETED,
                    OrderStatus.WAITING_FOR_CONFIRMATION,
                )
                and not amount
            ):
                raise InvalidCallbackError(
                    "Callback totalAmount is missing or zero"
                )
            if status == OrderStatus.COMPLETED:
                return PaymentUpdate(
                    payment_event=PaymentEvent.PAYMENT_CAPTURED,
                    paid_amount=amount,
                    external_id=external_id,
                    provider_event_id=provider_event_id,
                    provider_data={"payu_status": status},
                )
            elif status == OrderStatus.CANCELED:
                return PaymentUpdate(
                    payment_event=PaymentEvent.FAILED,
                    external_id=external_id,
                    provider_event_id=provider_event_id,
                    provider_data={"payu_status": status},
                )
            elif status == OrderStatus.WAITING_FOR_CONFIRMATION:
                return PaymentUpdate(
                    payment_event=PaymentEvent.LOCKED,
                    locked_amount=amount,
                    external_id=external_id,
                    provider_event_id=provider_event_id,
                    provider_data={"payu_status": status},
                )

        elif "refund" in data:
            refund_data = data["refund"]
            status = refund_data.get("status")
            refund_id = refund_data.get("refundId", "")
            provider_event_id = f"refund:{refund_id}:{status}"
            if status == RefundStatus.FINALIZED:
                amount = Decimal(str(refund_data.get("amount", 0))) / 100
                return PaymentUpdate(
                    payment_event=PaymentEvent.REFUND_CONFIRMED,
                    refunded_amount=amount,
                    provider_event_id=provider_event_id,
                    provider_data={"refund_status": status},
                )
            elif status == RefundStatus.CANCELED:
                return PaymentUpdate(
                    payment_event=PaymentEvent.REFUND_CANCELLED,
                    provider_event_id=provider_event_id,
                    provider_data={"refund_status": status},
                )
        return None

    async def fetch_payment_status(self, **kwargs) -> PaymentUpdate | None:
        """PULL flow: fetch payment status from PayU API."""
        client = self._get_client()
        response = await client.get_order_info(self.payment.external_id)
        orders = response.get("orders") or []
        order_data = orders[0] if orders else None
        status = order_data.get("status") if order_data else None
        if order_data is None:
            return None

        external_id = order_data.get("orderId") or self.payment.external_id
        # PayUClient.get_order_info already normalizes totalAmount from
        # minor units to Decimal major units — do NOT divide again here.
        amount = Decimal(str(order_data.get("totalAmount", 0)))
        provider_event_id = f"poll:{external_id}:{status}"

        if status == OrderStatus.COMPLETED:
            return PaymentUpdate(
                payment_event=PaymentEvent.PAYMENT_CAPTURED,
                paid_amount=amount or self.payment.amount_required,
                external_id=external_id,
                provider_event_id=provider_event_id,
                provider_data={"payu_status": status},
            )
        if status == OrderStatus.CANCELED:
            return PaymentUpdate(
                payment_event=PaymentEvent.FAILED,
                external_id=external_id,
                provider_event_id=provider_event_id,
                provider_data={"payu_status": status},
            )
        if status == OrderStatus.WAITING_FOR_CONFIRMATION:
            return PaymentUpdate(
                payment_event=PaymentEvent.LOCKED,
                locked_amount=amount or self.payment.amount_required,
                external_id=external_id,
                provider_event_id=provider_event_id,
                provider_data={"payu_status": status},
            )
        return None

    async def charge(
        self, amount: Decimal | None = None, **kwargs
    ) -> CoreChargeResult:
        """Charge a pre-authorized (locked) payment.

        PayU's capture endpoint always captures the FULL authorized
        amount — partial captures are not supported. Requesting a
        different amount raises ``ValueError`` instead of silently
        capturing the full lock and misreporting the charged amount.
        """
        if amount is not None and amount != self.payment.amount_locked:
            raise ValueError(
                "PayU does not support partial captures: requested "
                f"{amount}, but the full locked amount "
                f"{self.payment.amount_locked} would be captured."
            )
        client = self._get_client()
        response = await client.capture(self.payment.external_id)
        success = (
            response.get("status", {}).get("statusCode")
            == ResponseStatus.SUCCESS
        )
        return CoreChargeResult(
            amount_charged=self.payment.amount_locked,
            success=success,
            async_call=False,
        )

    async def release_lock(self, **kwargs) -> Decimal:
        """Release a pre-authorized lock by cancelling."""
        client = self._get_client()
        response = await client.cancel_order(self.payment.external_id)
        status = response.get("status", {}).get("statusCode")
        if status == ResponseStatus.SUCCESS:
            return self.payment.amount_locked
        return Decimal("0")

    async def start_refund(
        self, amount: Decimal | None = None, **kwargs
    ) -> RefundResult:
        """Start a refund via PayU API."""
        client = self._get_client()
        description = kwargs.get("description")
        response = await client.refund(
            order_id=self.payment.external_id,
            amount=amount,
            description=description,
        )
        refund = response.get("refund", {})
        provider_data = {}
        refund_id = refund.get("refundId")
        if refund_id:
            provider_data["refund_id"] = refund_id
        return RefundResult(
            amount=amount or self.payment.amount_paid,
            provider_data=provider_data,
        )
