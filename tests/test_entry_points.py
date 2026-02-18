"""Test entry_points discovery for PayU processor."""

from importlib.metadata import entry_points


def test_payu_entry_point_registered():
    """Verify PayU processor is discoverable via entry_points."""
    eps = [
        e for e in entry_points(group="getpaid.backends") if e.name == "payu"
    ]
    assert len(eps) == 1, "PayU entry_point not found"
    assert eps[0].value == "getpaid_payu.processor:PayUProcessor"
