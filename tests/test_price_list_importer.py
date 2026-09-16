"""
Unit Tests for CinePay Price List Importer & Data Sanitizer (The Twist)
"""

import unittest
from decimal import Decimal
from pricing_engine.price_list_importer import PriceListSanitizer


class TestPriceListSanitizer(unittest.TestCase):

    def setUp(self):
        self.sanitizer = PriceListSanitizer()

    def test_tier_name_normalization(self):
        self.assertEqual(self.sanitizer.normalize_tier_name("silver"), "Silver")
        self.assertEqual(self.sanitizer.normalize_tier_name("SILVER"), "Silver")
        self.assertEqual(self.sanitizer.normalize_tier_name("  gold tier  "), "Gold Tier")
        self.assertIsNone(self.sanitizer.normalize_tier_name(""))
        self.assertIsNone(self.sanitizer.normalize_tier_name("   "))
        self.assertIsNone(self.sanitizer.normalize_tier_name("N/A"))
        self.assertIsNone(self.sanitizer.normalize_tier_name(None))

    def test_price_parsing_inconsistent_formats(self):
        # Standard float/int
        p1, err1 = self.sanitizer.parse_price("180.00")
        self.assertEqual(p1, Decimal("180.00"))
        self.assertIsNone(err1)

        # Rupee symbol
        p2, err2 = self.sanitizer.parse_price("₹250.50")
        self.assertEqual(p2, Decimal("250.50"))

        # Rs. prefix
        p3, err3 = self.sanitizer.parse_price("Rs. 300")
        self.assertEqual(p3, Decimal("300.00"))

        # INR prefix
        p4, err4 = self.sanitizer.parse_price("INR 450.00")
        self.assertEqual(p4, Decimal("450.00"))

        # Commas in thousands
        p5, err5 = self.sanitizer.parse_price("1,250.00")
        self.assertEqual(p5, Decimal("1250.00"))

    def test_rejection_of_negative_and_zero_prices(self):
        # Negative prices
        p1, err1 = self.sanitizer.parse_price("-150.00")
        self.assertIsNone(p1)
        self.assertIn("Negative price", err1)

        p2, err2 = self.sanitizer.parse_price("₹ -200")
        self.assertIsNone(p2)
        self.assertIn("Negative price", err2)

        # Zero price
        p3, err3 = self.sanitizer.parse_price("0.00")
        self.assertIsNone(p3)
        self.assertIn("Zero price rejected", err3)

    def test_rejection_of_blank_and_invalid_formats(self):
        p1, err1 = self.sanitizer.parse_price("")
        self.assertIsNone(p1)
        self.assertIn("Blank", err1)

        p2, err2 = self.sanitizer.parse_price("FREE")
        self.assertIsNone(p2)
        self.assertIn("Blank or unassigned", err2)

        p3, err3 = self.sanitizer.parse_price("TBD")
        self.assertIsNone(p3)

        p4, err4 = self.sanitizer.parse_price("invalid_number_abc")
        self.assertIsNone(p4)
        self.assertIn("Unparseable", err4)

    def test_deduplication_and_audit_report(self):
        raw_list = [
            {"tier": "silver", "price": "180"},
            {"tier": "SILVER", "price": "₹190.00"},       # Duplicate: overwrites silver
            {"tier": "Gold", "price": "Rs. 250"},
            {"tier": "gold", "price": "₹280"},            # Duplicate: overwrites gold
            {"tier": "Recliner", "price": "-450"},        # Rejected: negative
            {"tier": "", "price": "300"},                 # Rejected: blank tier
            {"tier": "Balcony", "price": ""},             # Rejected: blank price
            {"tier": "Box Office", "price": "1,100.00"}   # Valid
        ]

        report = self.sanitizer.import_and_clean(raw_list)

        self.assertEqual(report.total_records_processed, 8)
        # Unique imported tiers: Silver, Gold, Box Office (3 tiers)
        self.assertEqual(report.imported_count, 3)
        # Deduplicated occurrences: 2 (Silver, Gold)
        self.assertEqual(report.deduplicated_count, 2)
        # Rejected occurrences: 3 (Recliner negative, blank tier, Balcony blank price)
        self.assertEqual(report.rejected_count, 3)

        # Check final values
        silver_entry = next(item for item in report.imported if item.tier == "Silver")
        self.assertEqual(silver_entry.price, Decimal("190.00"))

        gold_entry = next(item for item in report.imported if item.tier == "Gold")
        self.assertEqual(gold_entry.price, Decimal("280.00"))

    def test_csv_import_from_sample_file(self):
        with open("sample_messy_price_list.csv", "r", encoding="utf-8") as f:
            csv_text = f.read()

        report = self.sanitizer.import_from_csv_text(csv_text)
        self.assertGreater(report.imported_count, 0)
        self.assertGreater(report.deduplicated_count, 0)
        self.assertGreater(report.rejected_count, 0)


if __name__ == "__main__":
    unittest.main()
