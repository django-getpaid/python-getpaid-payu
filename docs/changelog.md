# Changelog

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
