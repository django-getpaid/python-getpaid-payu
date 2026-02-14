# Getting Started

## Installation

Install getpaid-payu from PyPI (distributed as `python-getpaid-payu`):

```bash
pip install python-getpaid-payu
```

Or add it as a dependency with uv:

```bash
uv add python-getpaid-payu
```

## About This Plugin

getpaid-payu is a **payment gateway plugin** for the
[python-getpaid](https://github.com/django-getpaid) ecosystem. It is typically
used through a framework adapter such as
[django-getpaid](https://github.com/django-getpaid/django-getpaid), which
provides models, views, and admin integration. However, the `PayUClient` can
also be used standalone for direct PayU API access.

## Standalone Usage: PayUClient

You can use `PayUClient` directly as an async context manager to interact with
the PayU REST API:

```python
from decimal import Decimal
from getpaid_payu.client import PayUClient
from getpaid_payu.types import Currency

async with PayUClient(
    api_url="https://secure.snd.payu.com/",
    pos_id=300746,
    second_key="b6ca15b0d1020e8094f2b...",
    oauth_id=300746,
    oauth_secret="2ee86a66e5d97e3fadc4...",
) as client:
    # Create a new order
    response = await client.new_order(
        amount=Decimal("29.99"),
        currency=Currency.PLN,
        order_id="order-123",
        description="Test order",
        notify_url="https://example.com/notify",
        continue_url="https://example.com/thank-you",
    )

    # Redirect the buyer to PayU
    redirect_url = response["redirectUri"]
    payu_order_id = response["orderId"]

    # Later: check order status
    info = await client.get_order_info(payu_order_id)

    # Refund the order
    refund = await client.refund(
        order_id=payu_order_id,
        amount=Decimal("10.00"),
        description="Partial refund",
    )
```

## Usage with django-getpaid

When used through the django-getpaid framework adapter, the processor is
discovered automatically via Python entry points.

### 1. Register the entry point

In your plugin's `pyproject.toml`:

```toml
[project.entry-points."getpaid.backends"]
payu = "getpaid_payu.processor:PayUProcessor"
```

### 2. Configure the backend

In your Django settings (or the adapter's config dict):

```python
GETPAID_BACKENDS = {
    "payu": {
        "pos_id": 300746,
        "second_key": "b6ca15b0d1020e8094f2b...",
        "oauth_id": 300746,
        "oauth_secret": "2ee86a66e5d97e3fadc4...",
        "sandbox": True,
        "notify_url": "https://example.com/payments/{payment_id}/notify",
        "continue_url": "https://example.com/payments/{payment_id}/continue",
    }
}
```

The framework adapter takes care of creating the processor, attaching the
payment object, and calling the appropriate methods during the payment
lifecycle.

## Sandbox vs Production

By default, the processor uses **sandbox mode** (`sandbox: True`), which
connects to `https://secure.snd.payu.com/`. For production, set `sandbox` to
`False` to use `https://secure.payu.com/`.

You can obtain sandbox credentials from the
[PayU developer panel](https://developers.payu.com/).

:::{warning}
Never use production credentials in development or test environments.
:::
