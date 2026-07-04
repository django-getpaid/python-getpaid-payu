# Changelog

## v3.2.0 (2026-07-04)

### Fixed

- **Money bug**: `PayUProcessor.fetch_payment_status()` divided
  `totalAmount` by 100 a second time after `PayUClient.get_order_info()`
  had already normalized it to major units, so e.g. a paid 100.00 PLN was
  reported as `paid_amount=1`. The double division is removed.
- **Money bug**: `PayUClient._centify()` converted floats with
  `str(int(v * 100))`, truncating binary float artifacts (19.99 became
  `"1998"`). Amounts are now converted via
  `Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_UP)`.
- `charge(amount)` no longer misreports: PayU only supports capturing the
  full authorized amount, so requesting a partial capture now raises
  `ValueError` instead of silently capturing the full lock; the result
  always reports the actually captured (locked) amount.

### Security

- Callback signature verification no longer logs or embeds the *expected*
  signature in `InvalidCallbackError` messages or ERROR logs (it acted as
  a signature oracle for forging callbacks). Only the received signature
  may be logged.
- `handle_callback()` now cross-checks the callback against the local
  payment: `extOrderId` must match the payment id, `currencyCode` must
  match the payment currency, and a missing or zero `totalAmount` on
  COMPLETED / WAITING_FOR_CONFIRMATION callbacks is rejected with
  `InvalidCallbackError` instead of being replaced with the locally
  expected amount.

### Changed (BREAKING)

- `get_payment_methods()`, `get_transaction()`, `get_refunds()`,
  `get_refund()`, `create_payout()` and `get_payout()` now normalize
  amount fields in their responses (`amount`, `totalAmount`, `minAmount`,
  `maxAmount`, `total`, `available`, `unitPrice`) from PayU's minor units
  to `Decimal` major units, consistently with the other endpoints.
  Callers that previously compensated for raw minor-unit values must be
  updated.
- `new_order()` now centifies amount-bearing fields inside the named
  optional sections (`shoppingCarts`, `credit.shoppingCarts`,
  `payMethods`, `donation`, ...) exactly like top-level amounts. Extra
  `**kwargs` remain verbatim passthrough — amounts inside them must be
  given in minor units (documented loudly in the docstring).

### Reliability

- All HTTP requests now carry an explicit timeout, configurable via the
  processor settings `timeout` / `connect_timeout` (default
  `httpx.Timeout(10.0, connect=5.0)`). POST requests are deliberately not
  retried: PayU has no documented idempotency key, so retries could
  duplicate orders, captures, or refunds.
- `PayUProcessor` now caches one `PayUClient` per processor instance and
  reuses the OAuth token until expiry instead of performing a full OAuth
  round trip per operation. Token refresh is guarded by an
  `asyncio.Lock`, so concurrent coroutines no longer stampede the
  authorize endpoint. Clients are properly closed via
  `PayUProcessor.aclose()` / `async with` (same for `PayUClient`).

### CI

- The Release workflow now runs only after the CI workflow has completed
  successfully on `main` (`workflow_run` gating); the tag/version guard
  logic is unchanged.

### Housekeeping

- Raised the core dependency floor to `python-getpaid-core>=3.1.0` and
  refreshed `uv.lock` accordingly.
- Removed the dead `PayUClient._get_http_client()` helper.
- Removed `sandbox_keys.txt` (public sandbox credentials are documented
  in the README) and the committed `.sisyphus/` build cruft; `.sisyphus/`
  is now gitignored.
- `tests/test_public_api.py` compares `__version__` against the installed
  package metadata instead of a hardcoded string.

## v3.0.0 (2026-06-04)

Major stable release — PayU payment gateway integration for the python-getpaid ecosystem.

### Breaking Changes

- Complete rewrite as a framework-agnostic plugin for `python-getpaid-core` v3
- Requires Python 3.12+
- Now depends on `python-getpaid-core>=3.0.0` instead of standalone django-getpaid

### Features

- Full PayU REST API v2.1 coverage
- Async HTTP client (`PayUClient`) with OAuth2 token management
- Payment processor (`PayUProcessor`) implementing `BaseProcessor`
- All order operations: create, cancel, capture, retrieve
- Refund operations: create, retrieve single/all
- Payment methods retrieval
- Transaction details retrieval
- Shop info and payout operations
- Token deletion
- Automatic amount centification/normalization
- Signature verification (MD5 and SHA-256)
- PUSH callback handling with semantic payment updates
- PULL status polling
- Full pre-authorization support (lock, charge, release)

---

## v0.1.0 (2026-02-14)

Initial release.

### Features

- Full PayU REST API v2.1 coverage
- Async HTTP client (`PayUClient`) with OAuth2 token management
- Payment processor (`PayUProcessor`) implementing `BaseProcessor`
- All order operations: create, cancel, capture, retrieve
- Refund operations: create, retrieve single/all
- Payment methods retrieval
- Transaction details retrieval
- Shop info and payout operations
- Token deletion
- Automatic amount centification/normalization
- Signature verification (MD5 and SHA-256)
- PUSH callback handling with semantic payment updates
- PULL status polling
- Full pre-authorization support (lock, charge, release)
