# Configuration

## Configuration Keys

All configuration is provided as a dictionary, either directly to
`PayUProcessor` via the framework adapter or to `PayUClient` constructor
arguments.

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `pos_id` | `int` | Yes | — | PayU POS (point of sale) identifier. Found in the PayU merchant panel. |
| `second_key` | `str` | Yes | — | Second key (MD5) from the PayU panel. Used for signature verification of callbacks. |
| `oauth_id` | `int` | Yes | — | OAuth2 client ID from the PayU panel. Used for API authentication. |
| `oauth_secret` | `str` | Yes | — | OAuth2 client secret from the PayU panel. Used for API authentication. |
| `sandbox` | `bool` | No | `True` | Whether to use the sandbox environment. When `True`, connects to `secure.snd.payu.com`; when `False`, connects to `secure.payu.com`. |
| `notify_url` | `str` | No | `None` | URL template for PayU PUSH notifications. Supports `{payment_id}` placeholder. |
| `continue_url` | `str` | No | `None` | URL template for buyer redirect after payment. Supports `{payment_id}` placeholder. |

## Example Configuration

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

## URL Templates

The `notify_url` and `continue_url` settings support the `{payment_id}`
placeholder, which is replaced at runtime with the actual payment identifier.
This allows you to route callbacks and redirects to the correct payment.

For example, if `notify_url` is set to:

```
https://example.com/payments/{payment_id}/notify
```

and the payment ID is `abc-123`, the URL sent to PayU will be:

```
https://example.com/payments/abc-123/notify
```

The `{order_id}` placeholder is also supported as an alias for `{payment_id}`.

## Sandbox vs Production URLs

| Environment | API Base URL |
|-------------|-------------|
| Sandbox | `https://secure.snd.payu.com/` |
| Production | `https://secure.payu.com/` |

The sandbox environment is a fully functional test environment provided by
PayU. It uses separate credentials from production and does not process real
payments.

:::{warning}
The `sandbox` setting defaults to `True`. You must explicitly set it to
`False` for production use. Never use production credentials in sandbox mode
or vice versa.
:::

## Direct PayUClient Usage

When using `PayUClient` standalone (without a framework adapter), pass the
configuration values directly to the constructor:

```python
from getpaid_payu.client import PayUClient

client = PayUClient(
    api_url="https://secure.snd.payu.com/",  # sandbox
    pos_id=300746,
    second_key="b6ca15b0d1020e8094f2b...",
    oauth_id=300746,
    oauth_secret="2ee86a66e5d97e3fadc4...",
)
```

The `api_url` corresponds to the sandbox/production URL choice. When using
`PayUProcessor`, this is handled automatically based on the `sandbox` setting.
