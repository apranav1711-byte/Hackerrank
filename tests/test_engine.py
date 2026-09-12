from datetime import date, timedelta
from decimal import Decimal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "code"))
from main import money, payment_string, safe_amount, simulate


def test_money_and_payment_formatting():
    assert money(Decimal("10.500")) == "10.5"
    assert payment_string([(date(2026, 1, 2), Decimal("20.00")), (date(2026, 1, 1), Decimal("10"))]) == "2026-01-01:10|2026-01-02:20"


def test_simulator_rejects_minimum_balance_breach():
    start = date(2026, 1, 1)
    flows = {start + timedelta(days=2): Decimal("-50")}
    assert not simulate(Decimal("100"), flows, start, [(start, Decimal("30"))], Decimal("30"))
    assert simulate(Decimal("100"), flows, start, [(start, Decimal("10"))], Decimal("30"))


def test_safe_amount_accounts_for_future_obligation():
    start = date(2026, 1, 1)
    flows = {start + timedelta(days=1): Decimal("-40")}
    assert safe_amount(Decimal("100"), flows, start, Decimal("100"), Decimal("30"), []) == Decimal("30.00")


def test_simulator_applies_credit_and_debit_in_date_order():
    start = date(2026, 1, 1)
    flows = {start + timedelta(days=1): Decimal("100"), start + timedelta(days=2): Decimal("-180")}
    assert not simulate(Decimal("100"), flows, start, [], Decimal("30"))
    assert not simulate(Decimal("100"), flows, start, [(start, Decimal("1"))], Decimal("30"))
