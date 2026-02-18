# python-getpaid-payu

[![PyPI version](https://img.shields.io/pypi/v/python-getpaid-payu.svg)](https://pypi.org/project/python-getpaid-payu/)
[![Python versions](https://img.shields.io/pypi/pyversions/python-getpaid-payu.svg)](https://pypi.org/project/python-getpaid-payu/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

PayU payment processor plugin for the [python-getpaid](https://github.com/django-getpaid/python-getpaid-core) ecosystem.

Provides a fully async HTTP client (`PayUClient`) and a payment processor (`PayUProcessor`) implementing the [getpaid-core](https://github.com/django-getpaid/python-getpaid-core) `BaseProcessor` interface. Communicates with PayU via their REST API v2.1 using OAuth2 authentication.

## Features

- **Full Payment Lifecycle**: Supports prepared, locked, paid, failed, and refunded states.
- **Pre-authorization**: Reserve funds on customer's card (lock) and capture them later (charge).
- **Refunds**: Full and partial refund support via API.
- **Multiple Currencies**: Support for 15 currencies across Europe and beyond.
- **Asynchronous**: Built with `httpx` for non-blocking API communication.
- **Security**: Robust callback signature verification (SHA-256 and MD5).
- **Comprehensive API**: Wraps every PayU REST API v2.1 endpoint.

## Supported Currencies

The following 15 currencies are supported:
BGN, CHF, CZK, DKK, EUR, GBP, HRK, HUF, NOK, PLN, RON, RUB, SEK, UAH, USD.

## Installation

```bash
pip install python-getpaid-payu
```

## Configuration

To use the PayU backend, register it in your `getpaid` configuration and provide the following settings:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `pos_id` | `int` | — | PayU POS (point of sale) identifier |
| `second_key` | `str` | — | Second key (MD5) from PayU panel, used for signature verification |
| `oauth_id` | `int` | — | OAuth client ID from PayU panel |
| `oauth_secret` | `str` | — | OAuth client secret from PayU panel |
| `sandbox` | `bool` | `True` | Use sandbox (`secure.snd.payu.com`) or production (`secure.payu.com`) |
| `notify_url` | `str` | `None` | Notification callback URL template, e.g. `https://example.com/payments/{payment_id}/notify` |
| `continue_url` | `str` | `None` | Redirect URL template after payment, e.g. `https://example.com/payments/{payment_id}/continue` |

Example configuration:

```python
GETPAID_BACKENDS = {
    "payu": {
        "pos_id": "300746",
        "second_key": "b6ca15b0d1020e8094d9b5f8d163db54",
        "oauth_id": "300746",
        "oauth_secret": "2ee86a66e5d97e3fadc400c9f19b065d",
        "notify_url": "https://your-domain.com/payments/payu/callback/",
        "continue_url": "https://your-domain.com/payments/payu/success/",
        "sandbox": True,
    }
}
```

### Sandbox Mode

PayU provides a sandbox environment for testing. You can use the example keys provided above for testing in PLN.

## Ecosystem

`python-getpaid-payu` is part of the larger `python-getpaid` ecosystem. Use it with one of our web framework wrappers:

- [django-getpaid](https://github.com/django-getpaid/django-getpaid)
- [litestar-getpaid](https://github.com/django-getpaid/litestar-getpaid)
- [fastapi-getpaid](https://github.com/django-getpaid/fastapi-getpaid)

## Requirements

- Python 3.12+
- `python-getpaid-core >= 3.0.0a2`
- `httpx >= 0.27.0`

## License

MIT

## Credits

Created by [Dominik Kozaczko](https://github.com/dekoza).
