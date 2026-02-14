# getpaid-payu

[![PyPI](https://img.shields.io/pypi/v/python-getpaid-payu.svg)](https://pypi.org/project/python-getpaid-payu/)
[![Python Version](https://img.shields.io/pypi/pyversions/python-getpaid-payu)](https://pypi.org/project/python-getpaid-payu/)
[![License](https://img.shields.io/pypi/l/python-getpaid-payu)](https://github.com/django-getpaid/python-getpaid-payu/blob/main/LICENSE)

PayU payment gateway plugin for the
[python-getpaid](https://github.com/django-getpaid) ecosystem. Provides a
fully async HTTP client (`PayUClient`) and a payment processor
(`PayUProcessor`) implementing the
[getpaid-core](https://github.com/django-getpaid/python-getpaid-core)
`BaseProcessor` interface. Communicates with PayU via their REST API v2.1
using OAuth2 authentication.

## Architecture

getpaid-payu is composed of two main layers:

- **PayUClient** — a low-level async HTTP client (built on `httpx`) that wraps
  every PayU REST API v2.1 endpoint. OAuth2 tokens are obtained lazily and
  refreshed automatically. Can be used as an async context manager for
  connection reuse.
- **PayUProcessor** — a high-level processor that implements `BaseProcessor`
  from getpaid-core. Translates between the core payment protocol and PayU's
  API, handles signature verification, PUSH/PULL callbacks, and FSM
  transitions.

## Key Features

- Full PayU REST API v2.1 coverage
- Async HTTP client with automatic OAuth2 token management
- Create order, cancel, capture (charge), retrieve order info
- Refund operations: create, retrieve single, retrieve all
- Payment methods retrieval
- Transaction details retrieval
- Shop info and payout operations
- Token deletion (card-on-file)
- Automatic amount centification (amounts × 100) and normalization
- Signature verification (MD5 and SHA-256)
- PUSH callback handling with FSM integration
- PULL status polling
- Full pre-authorization support (lock, charge, release)

## Quick Usage

`PayUClient` can be used standalone as an async context manager:

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
    response = await client.new_order(
        amount=Decimal("29.99"),
        currency=Currency.PLN,
        order_id="order-123",
        description="Test order",
    )
    redirect_url = response["redirectUri"]
```

## Configuration

When used via a framework adapter (e.g. django-getpaid), configuration is
provided as a dictionary:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pos_id` | `int` | — | PayU POS (point of sale) identifier |
| `second_key` | `str` | — | Second key (MD5) from PayU panel, used for signature verification |
| `oauth_id` | `int` | — | OAuth client ID from PayU panel |
| `oauth_secret` | `str` | — | OAuth client secret from PayU panel |
| `sandbox` | `bool` | `True` | Use sandbox (`secure.snd.payu.com`) or production (`secure.payu.com`) |
| `notify_url` | `str` | `None` | Notification callback URL template, e.g. `https://example.com/payments/{payment_id}/notify` |
| `continue_url` | `str` | `None` | Redirect URL template after payment, e.g. `https://example.com/payments/{payment_id}/continue` |

Example configuration dict:

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

## Supported Currencies

BGN, CHF, CZK, DKK, EUR, GBP, HRK, HUF, NOK, PLN, RON, RUB, SEK, UAH, USD

## Requirements

- Python 3.12+
- `python-getpaid-core >= 0.1.0`
- `httpx >= 0.27.0`

## Related Projects

- [getpaid-core](https://github.com/django-getpaid/python-getpaid-core) —
  framework-agnostic payment processing library
- [django-getpaid](https://github.com/django-getpaid/django-getpaid) —
  Django framework adapter

## License

MIT

## Disclaimer

This project has nothing in common with the
[getpaid](http://code.google.com/p/getpaid/) plone project.

## Credits

Created by [Dominik Kozaczko](https://github.com/dekoza).
