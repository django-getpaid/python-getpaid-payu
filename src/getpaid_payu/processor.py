"""PayU payment processor."""

import contextlib
import hashlib
import hmac
import logging
from decimal import Decimal
from typing import Any
from typing import ClassVar

from getpaid_core.exceptions import InvalidCallbackError
from getpaid_core.processor import BaseProcessor
from getpaid_core.types import ChargeResponse as CoreChargeResponse
from getpaid_core.types import PaymentStatusResponse
from getpaid_core.types import TransactionResult
from transitions.core import MachineError

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
    accepted_currencies: ClassVar[list[str]] = [c.value for c in Currency]
    sandbox_url: ClassVar[str] = "https://secure.snd.payu.com/"
    production_url: ClassVar[str] = "https://secure.payu.com/"

    def _get_client(self) -> PayUClient:
        """Create a PayUClient from processor config."""
        return PayUClient(
            api_url=self.get_paywall_baseurl(),
            pos_id=self.get_setting("pos_id"),
            second_key=self.get_setting("second_key"),
            oauth_id=self.get_setting("oauth_id"),
            oauth_secret=self.get_setting("oauth_secret"),
        )

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
        self.payment.external_id = response.get("orderId", "")
        return TransactionResult(
            redirect_url=response.get("redirectUri"),
            form_data=None,
            method="GET",
            headers={},
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
        if isinstance(raw_body, (bytes, bytearray)):
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

        if not hmac.compare_digest(expected, signature):
            logger.error(
                "Received bad signature for payment %s! "
                "Got '%s', expected '%s'",
                self.payment.id,
                signature,
                expected,
            )
            raise InvalidCallbackError(
                f"BAD SIGNATURE: got '{signature}', expected '{expected}'"
            )

    async def handle_callback(
        self, data: dict, headers: dict, **kwargs
    ) -> None:
        """Handle PayU PUSH callback (order or refund).

        Uses payment.may_trigger() to check if transitions are
        valid before firing them. FSM must be attached to
        self.payment before this method is called.
        """
        if "order" in data:
            order_data = data["order"]
            status = order_data.get("status")
            if status == OrderStatus.COMPLETED:
                if self.payment.may_trigger("confirm_payment"):  # type: ignore[union-attr]
                    self.payment.confirm_payment()  # type: ignore[union-attr]
                    with contextlib.suppress(MachineError):
                        self.payment.mark_as_paid()  # type: ignore[union-attr]
                else:
                    logger.debug(
                        "Cannot confirm payment",
                        extra={
                            "payment_id": self.payment.id,
                            "payment_status": self.payment.status,
                        },
                    )
            elif status == OrderStatus.CANCELED:
                self.payment.fail()  # type: ignore[union-attr]
            elif status == OrderStatus.WAITING_FOR_CONFIRMATION:
                if self.payment.may_trigger("confirm_lock"):  # type: ignore[union-attr]
                    self.payment.confirm_lock()  # type: ignore[union-attr]
                else:
                    logger.debug(
                        "Already locked",
                        extra={
                            "payment_id": self.payment.id,
                            "payment_status": self.payment.status,
                        },
                    )

        elif "refund" in data:
            refund_data = data["refund"]
            status = refund_data.get("status")
            if status == RefundStatus.FINALIZED:
                amount = Decimal(str(refund_data.get("amount", 0))) / 100
                self.payment.confirm_refund(amount=amount)  # type: ignore[union-attr]
                if self.payment.is_fully_refunded():
                    self.payment.mark_as_refunded()  # type: ignore[union-attr]
            elif status == RefundStatus.CANCELED:
                self.payment.cancel_refund()  # type: ignore[union-attr]
                if self.payment.is_fully_paid():
                    self.payment.mark_as_paid()  # type: ignore[union-attr]

    async def fetch_payment_status(self, **kwargs) -> PaymentStatusResponse:
        """PULL flow: fetch payment status from PayU API."""
        client = self._get_client()
        response = await client.get_order_info(self.payment.external_id)
        orders = response.get("orders") or []
        order_data = orders[0] if orders else None
        status = order_data.get("status") if order_data else None

        status_map = {
            OrderStatus.NEW: "confirm_prepared",
            OrderStatus.PENDING: "confirm_prepared",
            OrderStatus.CANCELED: "fail",
            OrderStatus.COMPLETED: "confirm_payment",
            OrderStatus.WAITING_FOR_CONFIRMATION: "confirm_lock",
        }

        return PaymentStatusResponse(
            status=status_map.get(status),
        )

    async def charge(
        self, amount: Decimal | None = None, **kwargs
    ) -> CoreChargeResponse:
        """Charge a pre-authorized (locked) payment."""
        client = self._get_client()
        response = await client.capture(self.payment.external_id)
        success = (
            response.get("status", {}).get("statusCode")
            == ResponseStatus.SUCCESS
        )
        return CoreChargeResponse(
            amount_charged=amount or self.payment.amount_locked,
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
    ) -> Decimal:
        """Start a refund via PayU API."""
        client = self._get_client()
        description = kwargs.get("description")
        await client.refund(
            order_id=self.payment.external_id,
            amount=amount,
            description=description,
        )
        return amount or self.payment.amount_paid
