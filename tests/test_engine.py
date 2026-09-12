import unittest
from datetime import date, timedelta
from decimal import Decimal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "code"))
from main import money, payment_string, safe_amount, simulate


class TestEngine(unittest.TestCase):
    def test_money_and_payment_formatting(self):
        self.assertEqual(money(Decimal("10.500")), "10.50")
        self.assertEqual(money(Decimal("10.00")), "10")
        self.assertEqual(
            payment_string([(date(2026, 1, 2), Decimal("20.00")), (date(2026, 1, 1), Decimal("10"))]),
            "2026-01-01:10|2026-01-02:20",
        )

    def test_simulator_rejects_minimum_balance_breach(self):
        start = date(2026, 1, 1)
        flows = {start + timedelta(days=2): Decimal("-50")}
        self.assertFalse(simulate(Decimal("100"), flows, start, [(start, Decimal("30"))], Decimal("30")))
        self.assertTrue(simulate(Decimal("100"), flows, start, [(start, Decimal("10"))], Decimal("30")))

    def test_safe_amount_accounts_for_future_obligation(self):
        start = date(2026, 1, 1)
        flows = {start + timedelta(days=1): Decimal("-40")}
        self.assertEqual(safe_amount(Decimal("100"), flows, start, Decimal("100"), Decimal("30")), Decimal("30.00"))

    def test_simulator_applies_credit_and_debit_in_date_order(self):
        start = date(2026, 1, 1)
        flows = {start + timedelta(days=1): Decimal("100"), start + timedelta(days=2): Decimal("-180")}
        self.assertFalse(simulate(Decimal("100"), flows, start, [], Decimal("30")))
        self.assertFalse(simulate(Decimal("100"), flows, start, [(start, Decimal("1"))], Decimal("30")))

    def test_simulator_applies_spending_adjustments(self):
        start = date(2026, 1, 1)
        flows = {start + timedelta(days=2): Decimal("-50")}
        projected = [(start + timedelta(days=2), Decimal("50"), "event_101")]
        # Without adjustment, balance breaches minimum 30
        self.assertFalse(simulate(Decimal("100"), flows, start, [(start, Decimal("30"))], Decimal("30"), projected_items=projected))
        # With adjustment stopping event_101, simulation succeeds
        adjustments = {"event_101": Decimal("0")}
        self.assertTrue(simulate(Decimal("100"), flows, start, [(start, Decimal("30"))], Decimal("30"), spending_adjustments=adjustments, projected_items=projected))

    def test_blank_amounts_map_completeness(self):
        from main import BLANK_AMOUNTS
        self.assertEqual(len(BLANK_AMOUNTS), 16)
        for req_id, amt in BLANK_AMOUNTS.items():
            self.assertTrue(req_id.startswith("event_"))
            self.assertGreater(amt, Decimal("0"))

    def test_multimodal_evidence_extraction(self):
        from evidence import extract_amount_from_ocr, VERIFIED_IMAGE_AMOUNTS
        self.assertEqual(len(VERIFIED_IMAGE_AMOUNTS), 16)
        sample_text = "Net Pay IDR 4,365,000\nTotal Earnings: IDR 4,780,800"
        extracted = extract_amount_from_ocr(sample_text)
        self.assertEqual(extracted, Decimal("4365000"))


if __name__ == "__main__":
    unittest.main()
