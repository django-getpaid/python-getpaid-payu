"""Tests for PayU-specific types and enums."""

from getpaid_payu.types import CardOnFile
from getpaid_payu.types import Currency
from getpaid_payu.types import Language
from getpaid_payu.types import OrderStatus
from getpaid_payu.types import PayMethodValue
from getpaid_payu.types import PayoutStatus
from getpaid_payu.types import RecurringType
from getpaid_payu.types import RefundStatus
from getpaid_payu.types import RefundType
from getpaid_payu.types import ResponseStatus
from getpaid_payu.types import TokenStatus


def test_currency_values():
    assert Currency.PLN == "PLN"
    assert Currency.EUR == "EUR"
    assert Currency.USD == "USD"
    assert len(Currency) == 15


def test_order_status_values():
    assert OrderStatus.NEW == "NEW"
    assert OrderStatus.PENDING == "PENDING"
    assert OrderStatus.CANCELED == "CANCELED"
    assert OrderStatus.COMPLETED == "COMPLETED"
    assert OrderStatus.WAITING_FOR_CONFIRMATION == "WAITING_FOR_CONFIRMATION"


def test_refund_status_values():
    assert RefundStatus.PENDING == "PENDING"
    assert RefundStatus.FINALIZED == "FINALIZED"
    assert RefundStatus.CANCELED == "CANCELED"


def test_response_status_values():
    assert ResponseStatus.SUCCESS == "SUCCESS"
    assert (
        ResponseStatus.WARNING_CONTINUE_REDIRECT == "WARNING_CONTINUE_REDIRECT"
    )


def test_pay_method_values():
    assert PayMethodValue.blik == "blik"
    assert PayMethodValue.c == "c"
    assert PayMethodValue.as_ == "as"


def test_language_values():
    assert Language.pl == "pl"
    assert Language.en == "en"
    assert len(Language) == 25


def test_card_on_file_values():
    assert CardOnFile.FIRST == "FIRST"
    assert CardOnFile.STANDARD_CARDHOLDER == "STANDARD_CARDHOLDER"
    assert CardOnFile.STANDARD_MERCHANT == "STANDARD_MERCHANT"


def test_recurring_type_values():
    assert RecurringType.FIRST == "FIRST"
    assert RecurringType.STANDARD == "STANDARD"


def test_refund_type_values():
    assert RefundType.REFUND_PAYMENT_STANDARD == "REFUND_PAYMENT_STANDARD"
    assert RefundType.FAST == "FAST"


def test_payout_status_values():
    assert PayoutStatus.PENDING == "PENDING"
    assert PayoutStatus.REALIZED == "REALIZED"


def test_token_status_values():
    assert TokenStatus.ACTIVE == "ACTIVE"
    assert TokenStatus.EXPIRED == "EXPIRED"
