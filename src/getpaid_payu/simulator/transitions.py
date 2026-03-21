"""PayU simulator state transitions."""

PAYU_TRANSITIONS: dict[str, set[str]] = {
    "NEW": {"PENDING"},
    "PENDING": {"WAITING_FOR_CONFIRMATION", "CANCELED"},
    "WAITING_FOR_CONFIRMATION": {"COMPLETED", "CANCELED"},
    "COMPLETED": set(),
    "CANCELED": set(),
}
