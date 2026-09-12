import unittest
from datetime import date, timedelta
from decimal import Decimal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "code"))
from main import money, payment_string, safe_amount, simulate, convert, normalize_events, message_salary_info


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

    def test_missing_exchange_rate_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "Missing exchange rate"):
            convert(Decimal("10"), "USD", "EUR", date(2026, 1, 1), {})

    def test_linked_events_choose_settled_record_over_pending_record(self):
        rows = [
            {
                "event_id": "event_pending", "linked_event_id": "event_root",
                "status": "pending", "direction": "debit", "amount": "100",
                "currency": "USD", "event_date": "2026-01-01", "settlement_date": "",
            },
            {
                "event_id": "event_settled", "linked_event_id": "event_root",
                "status": "settled", "direction": "debit", "amount": "120",
                "currency": "USD", "event_date": "2026-01-02", "settlement_date": "2026-01-03",
            },
        ]
        normalized = normalize_events(rows, "USD", {}, {})
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["event_id"], "event_settled")
        self.assertEqual(normalized[0]["cash_date"], date(2026, 1, 3))

    def test_blank_amount_without_evidence_fails_explicitly(self):
        rows = [{
            "event_id": "event_unknown", "linked_event_id": "", "status": "settled",
            "direction": "debit", "amount": "", "currency": "USD",
            "event_date": "2026-01-01", "settlement_date": "",
        }]
        with self.assertRaisesRegex(ValueError, "Blank amount has no image evidence"):
            normalize_events(rows, "USD", {}, {})

    def test_salary_message_uses_stated_settlement_date_for_conversion(self):
        messages = [{
            "sent_at": "2025-04-23T09:30:00Z",
            "source_type": "employer",
            "message_text": "Confirmed salary is USD 696 for 15 May 2025.",
        }]
        rates = {("2025-05-15", "USD", "IDR"): {"rate": "15833.33"}}
        salary, terminated = message_salary_info(messages, "IDR", rates, date(2025, 5, 3))
        self.assertEqual(salary, Decimal("11019997.68"))
        self.assertFalse(terminated)


if __name__ == "__main__":
    unittest.main()
