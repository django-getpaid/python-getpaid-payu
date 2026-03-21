"""PayU webhook delivery for the simulator plugin."""

from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from getpaid_payu.simulator.signing import sign_payload


if TYPE_CHECKING:
    from getpaid_simulator.core.storage import SimulatorStorage
    from getpaid_simulator.core.webhooks import WebhookTransport


def build_order_notification(
    order_id: str,
    order: dict[str, Any],
) -> dict[str, Any]:
    """Build the PayU OrderNotification payload."""
    order_data: dict[str, Any] = {
        "orderId": order_id,
        "orderCreateDate": datetime.now(UTC).isoformat(),
        "extOrderId": order.get("extOrderId"),
        "notifyUrl": order.get("notifyUrl"),
        "customerIp": order.get("customerIp", "127.0.0.1"),
        "merchantPosId": order.get("merchantPosId"),
        "description": order.get("description"),
        "currencyCode": order.get("currencyCode"),
        "totalAmount": order.get("totalAmount"),
        "status": order.get("status"),
        "buyer": order.get("buyer", {}),
        "products": order.get("products", []),
    }
    return {
        "order": order_data,
        "localReceiptDateTime": datetime.now(UTC).isoformat(),
        "properties": None,
    }


async def trigger_payu_webhook(
    order_id: str,
    storage: SimulatorStorage,
    provider_config: dict[str, Any],
    transport: WebhookTransport,
) -> bool | None:
    """Send a PayU order notification to the merchant callback URL."""
    order = storage.get_order(order_id)
    if order is None:
        return None

    notify_url = order.get("notifyUrl")
    if not notify_url:
        return None

    payload = build_order_notification(order_id, order)
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "OpenPayU-Signature": sign_payload(
            body,
            str(provider_config["second_key"]),
        ),
    }

    result = await transport.deliver(
        url=str(notify_url), body=body, headers=headers
    )
    storage.update_order(
        order_id,
        webhook_status="success" if result else "failed",
    )
    return result
