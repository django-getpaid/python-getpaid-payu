"""PayU simulator routes."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from inspect import isawaitable
from typing import Any
from urllib.parse import parse_qsl

from litestar import Request
from litestar import delete
from litestar import get
from litestar import post
from litestar.enums import MediaType
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException
from litestar.exceptions import NotFoundException
from litestar.params import Body
from litestar.response import Redirect
from litestar.response import Response
from litestar.response import Template

from getpaid_payu.simulator.webhooks import trigger_payu_webhook


URL_ENCODED_BODY = Body(media_type=RequestEncodingType.URL_ENCODED)


def _provider_config(request: Request[Any, Any, Any]) -> dict[str, Any]:
    return dict(request.app.state.provider_configs["payu"])


def _unauthorized_response() -> Response[dict[str, dict[str, str]]]:
    return Response(
        content={
            "status": {
                "statusCode": "UNAUTHORIZED",
                "statusDesc": "Invalid or expired token",
            }
        },
        status_code=401,
        media_type=MediaType.JSON,
    )


def _not_found_response(order_id: str) -> Response[dict[str, dict[str, str]]]:
    return Response(
        content={
            "status": {
                "statusCode": "ERROR_ORDER_NOT_EXISTS",
                "statusDesc": f"Order {order_id} not found",
            }
        },
        status_code=404,
        media_type=MediaType.JSON,
    )


def _extract_bearer_token(request: Request[Any, Any, Any]) -> str | None:
    authorization_header = request.headers.get("authorization")
    if authorization_header is None:
        return None

    token_type, _, token_value = authorization_header.partition(" ")
    if token_type.lower() != "bearer" or not token_value:
        return None
    return token_value


def _is_authorized(request: Request[Any, Any, Any]) -> bool:
    token = _extract_bearer_token(request)
    if token is None:
        return False
    return request.app.state.storage.validate_token(token)


def _order_to_payu_order(
    order_id: str,
    order_data: dict[str, Any],
) -> dict[str, Any]:
    payu_order = dict(order_data)
    payu_order.pop("id", None)
    payu_order["orderId"] = order_id
    return payu_order


@post("/payu/pl/standard/user/oauth/authorize")
async def oauth_endpoint(
    request: Request[Any, Any, Any],
) -> Response[dict[str, Any]]:
    raw_body = await request.body()
    form_data = dict(parse_qsl(raw_body.decode()))
    client_id = form_data.get("client_id", "")
    token_data = request.app.state.storage.create_token(
        pos_id=client_id,
        expires_in=43199,
    )
    return Response(
        content={
            "access_token": token_data["access_token"],
            "token_type": "bearer",
            "expires_in": 43199,
            "grant_type": "client_credentials",
        },
        status_code=200,
        media_type=MediaType.JSON,
    )


@get("/payu/api/v2_1/test-protected")
async def test_protected_endpoint(
    request: Request[Any, Any, Any],
) -> Response[dict[str, Any]]:
    if not _is_authorized(request):
        return _unauthorized_response()

    return Response(
        content={"status": "ok"},
        status_code=200,
        media_type=MediaType.JSON,
    )


@post("/payu/api/v2_1/orders")
async def create_order(
    request: Request[Any, Any, Any],
) -> Response[dict[str, Any]]:
    if not _is_authorized(request):
        return _unauthorized_response()

    payload = await request.json()
    if not isinstance(payload, dict):
        payload = {}

    order_data = dict(payload)
    order_data["status"] = "NEW"
    order_id = request.app.state.storage.create_order(
        order_data,
        provider="payu",
    )
    request.app.state.state_machine.transition(order_id, "PENDING")

    host = request.headers.get("host", "localhost")
    redirect_uri = f"http://{host}/sim/payu/authorize/{order_id}"
    response_body = {
        "status": {"statusCode": "SUCCESS"},
        "orderId": order_id,
        "extOrderId": order_data.get("extOrderId"),
        "redirectUri": redirect_uri,
    }
    return Response(
        content=response_body,
        status_code=302,
        headers={"Location": redirect_uri},
        media_type=MediaType.JSON,
    )


@get("/payu/api/v2_1/orders/{order_id:str}")
async def get_order_info(
    request: Request[Any, Any, Any],
    order_id: str,
) -> Response[dict[str, Any]]:
    if not _is_authorized(request):
        return _unauthorized_response()

    order = request.app.state.storage.get_order(order_id)
    if order is None:
        return _not_found_response(order_id)

    return Response(
        content={
            "orders": [_order_to_payu_order(order_id, order)],
            "status": {"statusCode": "SUCCESS"},
        },
        status_code=200,
        media_type=MediaType.JSON,
    )


@delete("/payu/api/v2_1/orders/{order_id:str}", status_code=200)
async def cancel_order(
    request: Request[Any, Any, Any],
    order_id: str,
) -> Response[dict[str, Any]]:
    if not _is_authorized(request):
        return _unauthorized_response()

    order = request.app.state.storage.get_order(order_id)
    if order is None:
        return _not_found_response(order_id)

    try:
        request.app.state.state_machine.transition(order_id, "CANCELED")
    except request.app.state.invalid_transition_error as error:
        return Response(
            content=error.error_response,
            status_code=200,
            media_type=MediaType.JSON,
        )

    callback = trigger_payu_webhook(
        order_id,
        request.app.state.storage,
        _provider_config(request),
        request.app.state.webhook_transport,
    )
    if isawaitable(callback):
        await callback

    return Response(
        content={"status": {"statusCode": "SUCCESS"}, "orderId": order_id},
        status_code=200,
        media_type=MediaType.JSON,
    )


@post("/payu/api/v2_1/orders/{order_id:str}/captures")
async def capture_order(
    request: Request[Any, Any, Any],
    order_id: str,
) -> Response[dict[str, Any]]:
    if not _is_authorized(request):
        return _unauthorized_response()

    order = request.app.state.storage.get_order(order_id)
    if order is None:
        return _not_found_response(order_id)

    try:
        request.app.state.state_machine.transition(order_id, "COMPLETED")
    except request.app.state.invalid_transition_error as error:
        return Response(
            content=error.error_response,
            status_code=200,
            media_type=MediaType.JSON,
        )

    callback = trigger_payu_webhook(
        order_id,
        request.app.state.storage,
        _provider_config(request),
        request.app.state.webhook_transport,
    )
    if isawaitable(callback):
        await callback

    return Response(
        content={"status": {"statusCode": "SUCCESS"}, "orderId": order_id},
        status_code=200,
        media_type=MediaType.JSON,
    )


@post("/payu/api/v2_1/orders/{order_id:str}/refunds")
async def create_refund(
    request: Request[Any, Any, Any],
    order_id: str,
) -> Response[dict[str, Any]]:
    if not _is_authorized(request):
        return _unauthorized_response()

    order = request.app.state.storage.get_order(order_id)
    if order is None:
        return _not_found_response(order_id)

    payload = await request.json()
    if not isinstance(payload, dict):
        payload = {}

    refund_info = payload.get("refund", {})

    amount = refund_info.get("amount")
    if amount is None:
        amount = order.get("totalAmount", "0")

    description = refund_info.get("description", "Refund")
    ext_refund_id = refund_info.get("extRefundId")
    currency_code = refund_info.get(
        "currencyCode", order.get("currencyCode", "PLN")
    )

    now = datetime.now(UTC).isoformat()
    refund_data = {
        "amount": amount,
        "currencyCode": currency_code,
        "description": description,
        "status": "FINALIZED",
        "creationDateTime": now,
        "statusDateTime": now,
    }

    if ext_refund_id is not None:
        refund_data["extRefundId"] = ext_refund_id

    refund_id = request.app.state.storage.create_refund(order_id, refund_data)

    response_body = {
        "status": {"statusCode": "SUCCESS"},
        "orderId": order_id,
        "refund": {
            "refundId": refund_id,
            "extRefundId": ext_refund_id,
            "amount": amount,
            "currencyCode": currency_code,
            "description": description,
            "status": "FINALIZED",
            "statusDateTime": now,
        },
    }

    return Response(
        content=response_body,
        status_code=200,
        media_type=MediaType.JSON,
    )


@get("/sim/payu/authorize/{order_id:str}")
async def payu_authorize_get(
    order_id: str,
    request: Request[Any, Any, Any],
) -> Template:
    order = request.app.state.storage.get_order(order_id)
    if not order:
        raise NotFoundException("Payment not found")

    if order.get("status") in ("COMPLETED", "CANCELED"):
        raise HTTPException(status_code=400, detail="Payment already processed")

    amount_raw = order.get("totalAmount", 0)
    try:
        amount_value = float(amount_raw) / 100
        formatted_amount = (
            f"{amount_value:.2f} {order.get('currencyCode', 'PLN')}"
        )
    except (ValueError, TypeError):
        formatted_amount = str(amount_raw)

    return Template(
        template_name="authorize.html",
        context={
            "provider": "PayU",
            "payment": order,
            "order_id": order_id,
            "amount": formatted_amount,
            "status": order.get("status", "NEW"),
        },
    )


@post("/sim/payu/authorize/{order_id:str}")
async def payu_authorize_post(
    order_id: str,
    request: Request[Any, Any, Any],
    data: dict[str, str] = URL_ENCODED_BODY,
) -> Redirect:
    order = request.app.state.storage.get_order(order_id)
    if not order:
        raise NotFoundException("Payment not found")

    current_status = order.get("status", "NEW")
    if current_status in ("COMPLETED", "CANCELED"):
        raise HTTPException(status_code=400, detail="Payment already processed")

    action = data.get("action")
    if action == "approve":
        if current_status == "NEW":
            request.app.state.state_machine.transition(order_id, "PENDING")
            request.app.state.state_machine.transition(
                order_id, "WAITING_FOR_CONFIRMATION"
            )
        elif current_status == "PENDING":
            request.app.state.state_machine.transition(
                order_id, "WAITING_FOR_CONFIRMATION"
            )
        request.app.state.state_machine.transition(order_id, "COMPLETED")
    elif action == "reject":
        if current_status == "NEW":
            request.app.state.state_machine.transition(order_id, "PENDING")
        request.app.state.state_machine.transition(order_id, "CANCELED")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await trigger_payu_webhook(
        order_id,
        request.app.state.storage,
        _provider_config(request),
        request.app.state.webhook_transport,
    )

    continue_url = order.get("continueUrl", "/")
    return Redirect(path=str(continue_url))
