"""Tests for the PayU simulator plugin."""

from __future__ import annotations

import json
from importlib.metadata import entry_points

import pytest
from getpaid_simulator.spi import SIMULATOR_PLUGIN_API_VERSION

from getpaid_payu.simulator import get_plugin
from getpaid_payu.simulator.plugin import load_provider_config
from getpaid_payu.simulator.signing import sign_payload
from getpaid_payu.simulator.webhooks import trigger_payu_webhook


def _handler_name(handler: object) -> str:
    return str(handler.fn.__name__)


class FakeStorage:
    def __init__(self, order: dict[str, object] | None) -> None:
        self.order = order
        self.updated: dict[str, object] = {}

    def get_order(self, order_id: str) -> dict[str, object] | None:
        if self.order is None or order_id != "order-1":
            return None
        return dict(self.order)

    def update_order(self, order_id: str, **updates: object) -> None:
        assert order_id == "order-1"
        self.updated = dict(updates)


class FakeTransport:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def deliver(
        self,
        *,
        url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> bool:
        self.calls.append({"url": url, "body": body, "headers": dict(headers)})
        return self.result


def test_payu_simulator_entry_point_registered() -> None:
    simulator_plugins = [
        entry_point
        for entry_point in entry_points(group="getpaid.simulator.providers")
        if entry_point.name == "payu"
    ]

    assert len(simulator_plugins) == 1
    assert simulator_plugins[0].value == "getpaid_payu.simulator:get_plugin"


def test_get_plugin_returns_payu_simulator_descriptor() -> None:
    plugin = get_plugin()

    assert plugin.api_version == SIMULATOR_PLUGIN_API_VERSION
    assert plugin.slug == "payu"
    assert plugin.display_name == "PayU"
    assert plugin.authorize_path_template == "/sim/payu/authorize/{entity_id}"
    assert (
        plugin.build_authorize_path("order-123")
        == "/sim/payu/authorize/order-123"
    )
    assert {_handler_name(handler) for handler in plugin.api_handlers} == {
        "oauth_endpoint",
        "test_protected_endpoint",
        "create_order",
        "get_order_info",
        "cancel_order",
        "capture_order",
        "create_refund",
    }
    assert {_handler_name(handler) for handler in plugin.ui_handlers} == {
        "payu_authorize_get",
        "payu_authorize_post",
    }


def test_load_provider_config_reads_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIMULATOR_PAYU_SECOND_KEY", "override-second-key")

    assert load_provider_config()["second_key"] == "override-second-key"


@pytest.mark.asyncio
async def test_trigger_payu_webhook_signs_and_delivers_payload() -> None:
    storage = FakeStorage(
        {
            "extOrderId": "ORDER-42",
            "notifyUrl": "https://merchant.example/payu/callback",
            "customerIp": "127.0.0.1",
            "merchantPosId": "145227",
            "description": "Test order",
            "currencyCode": "PLN",
            "totalAmount": "21000",
            "status": "COMPLETED",
            "buyer": {"email": "buyer@example.com"},
            "products": [{"name": "Test product", "quantity": "1"}],
        }
    )
    transport = FakeTransport()

    result = await trigger_payu_webhook(
        "order-1",
        storage,
        {"second_key": "secret-key"},
        transport,
    )

    assert result is True
    assert storage.updated == {"webhook_status": "success"}
    assert len(transport.calls) == 1

    request = transport.calls[0]
    assert request["url"] == "https://merchant.example/payu/callback"
    body = request["body"]
    assert isinstance(body, bytes)
    payload = json.loads(body)
    assert payload["order"]["orderId"] == "order-1"
    assert payload["order"]["extOrderId"] == "ORDER-42"
    assert payload["order"]["status"] == "COMPLETED"
    assert request["headers"] == {
        "Content-Type": "application/json",
        "OpenPayU-Signature": sign_payload(body, "secret-key"),
    }


@pytest.mark.asyncio
async def test_trigger_payu_webhook_returns_none_without_notify_url() -> None:
    storage = FakeStorage({"status": "COMPLETED"})
    transport = FakeTransport()

    result = await trigger_payu_webhook(
        "order-1",
        storage,
        {"second_key": "secret-key"},
        transport,
    )

    assert result is None
    assert transport.calls == []
