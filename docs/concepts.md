# Concepts

## Payment Flow

The standard payment flow with PayU:

```
1. Create order          PayUProcessor.prepare_transaction()
                         └── PayUClient.new_order()
                              └── POST /api/v2_1/orders

2. Redirect buyer        → PayU hosted payment page (redirectUri)

3. Buyer pays            (on PayU's side)

4. PayU sends callback   POST to notify_url
                         └── PayUProcessor.verify_callback()
                              └── Signature verification
                         └── PayUProcessor.handle_callback()
                              └── FSM transitions:
                                  COMPLETED → confirm_payment → mark_as_paid
                                  CANCELED  → fail
```

### Step by Step

1. **Create order** — The framework adapter calls `prepare_transaction()`,
   which creates an order via the PayU API and returns a `TransactionResult`
   with a `redirect_url`.

2. **Redirect** — The buyer is redirected to the PayU hosted payment page
   where they choose a payment method and complete the transaction.

3. **Notification** — PayU sends a PUSH notification (HTTP POST) to the
   `notify_url` with the order status. The framework adapter passes this to
   `verify_callback()` (signature check) and then `handle_callback()` (FSM
   state transitions).

4. **Status update** — The payment status is updated via FSM transitions
   based on the PayU order status.

## Pre-authorization Flow

PayU supports pre-authorization (two-phase payments) where the amount is
locked on the buyer's account first, then charged or released later:

```
1. Create order          new_order() with settings for pre-auth
                         └── PayU returns WAITING_FOR_CONFIRMATION status

2. PayU callback         handle_callback()
                         └── WAITING_FOR_CONFIRMATION → confirm_lock

3a. Capture (charge)     PayUProcessor.charge()
                         └── PayUClient.capture()
                              └── POST /api/v2_1/orders/{id}/captures

3b. Release (cancel)     PayUProcessor.release_lock()
                         └── PayUClient.cancel_order()
                              └── DELETE /api/v2_1/orders/{id}
```

## Refund Flow

Refunds can be full or partial:

```
1. Start refund          PayUProcessor.start_refund()
                         └── PayUClient.refund()
                              └── POST /api/v2_1/orders/{id}/refunds

2. PayU processes        (asynchronous on PayU's side)

3. PayU callback         handle_callback()
                         └── refund.status == FINALIZED
                              → confirm_refund → mark_as_refunded
                         └── refund.status == CANCELED
                              → cancel_refund → mark_as_paid
```

## OAuth2 Authentication

All PayU API calls require OAuth2 bearer tokens. The `PayUClient` manages
this transparently:

- Tokens are obtained lazily on the first API call via the `ensure_auth`
  decorator.
- The token endpoint is `POST /pl/standard/user/oauth/authorize` with
  `grant_type=client_credentials`.
- Tokens are cached and automatically refreshed 5 seconds before expiry.
- If authentication fails, a `CredentialsError` is raised.

You do not need to manage tokens manually.

## Amount Handling (Centification)

PayU's API expects amounts in the smallest currency unit (e.g. grosze for PLN,
cents for EUR). The `PayUClient` handles this conversion automatically:

- **Outgoing** (`_centify`): Multiplies amount values by 100 and converts to
  strings before sending to PayU. For example, `Decimal("29.99")` becomes
  `"2999"`.
- **Incoming** (`_normalize`): Divides amount values by 100 and converts to
  `Decimal` when parsing PayU responses. For example, `"2999"` becomes
  `Decimal("29.99")`.

The following fields are automatically converted: `amount`, `total`,
`available`, `unitPrice`, `totalAmount`.

## Signature Verification

PayU signs callback notifications using the `second_key` from the merchant
panel. The `verify_callback` method validates these signatures:

1. Parse the `OpenPayu-Signature` header to extract the algorithm and
   signature value.
2. Concatenate the raw request body with the `second_key`.
3. Compute the hash using the specified algorithm (MD5 or SHA-256).
4. Compare with the provided signature using constant-time comparison.

If the signature is invalid, an `InvalidCallbackError` is raised.

:::{note}
The framework adapter must inject the raw HTTP body as `data["_raw_body"]`
for signature verification to work. Parsed JSON alone is not sufficient
because JSON serialization is not guaranteed to be stable.
:::

## Supported Operations

| Operation | Client Method | HTTP | Endpoint |
|-----------|--------------|------|----------|
| Create order | `new_order()` | `POST` | `/api/v2_1/orders` |
| Cancel order | `cancel_order()` | `DELETE` | `/api/v2_1/orders/{id}` |
| Capture (charge) | `capture()` | `POST` | `/api/v2_1/orders/{id}/captures` |
| Get order info | `get_order_info()` | `GET` | `/api/v2_1/orders/{id}` |
| Create refund | `refund()` | `POST` | `/api/v2_1/orders/{id}/refunds` |
| Get all refunds | `get_refunds()` | `GET` | `/api/v2_1/orders/{id}/refunds` |
| Get single refund | `get_refund()` | `GET` | `/api/v2_1/orders/{id}/refunds/{rid}` |
| Get payment methods | `get_payment_methods()` | `GET` | `/api/v2_1/paymethods` |
| Get transaction | `get_transaction()` | `GET` | `/api/v2_1/orders/{id}/transactions` |
| Get shop info | `get_shop_info()` | `GET` | `/api/v2_1/shops/{id}` |
| Create payout | `create_payout()` | `POST` | `/api/v2_1/payouts` |
| Get payout | `get_payout()` | `GET` | `/api/v2_1/payouts/{id}` |
| Delete token | `delete_token()` | `DELETE` | `/api/v2_1/tokens/{token}` |

## PayU REST API Documentation

For the full PayU REST API v2.1 specification, see the official documentation:
[https://developers.payu.com/en/restapi.html](https://developers.payu.com/en/restapi.html)
