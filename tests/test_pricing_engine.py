"""
Unit Tests for CinePay Pricing Engine
Verifies exact paisa arithmetic, offer layering, convenience fee, and GST calculations.
"""

import unittest
from decimal import Decimal
from pricing_engine.models import (
    BookingItem,
    OfferConfig,
    FeeAndTaxConfig,
    SeatTier,
)
from pricing_engine.engine import PricingEngine, to_paisa


class TestPricingEngine(unittest.TestCase):

    def setUp(self):
        self.engine = PricingEngine()

    def test_zero_tickets(self):
        """Zero tickets should yield zero amounts and no crash."""
        breakdown = self.engine.calculate([])
        self.assertEqual(breakdown.total_tickets, 0)
        self.assertEqual(breakdown.gross_ticket_amount, Decimal("0.00"))
        self.assertEqual(breakdown.grand_total, Decimal("0.00"))

    def test_single_tier_plain_booking(self):
        """Plain booking: 2 Gold tickets @ 250 each. No offers."""
        items = [BookingItem(tier="Gold", quantity=2, unit_price=Decimal("250.00"))]
        breakdown = self.engine.calculate(items)

        # 2 x 250 = 500 gross
        self.assertEqual(breakdown.total_tickets, 2)
        self.assertEqual(breakdown.gross_ticket_amount, Decimal("500.00"))
        self.assertEqual(breakdown.net_ticket_amount, Decimal("500.00"))

        # Convenience fee: 2 x 30 = 60
        self.assertEqual(breakdown.total_convenience_fee, Decimal("60.00"))

        # GST on tickets: 18% of 500 = 90 (CGST 45, SGST 45)
        self.assertEqual(breakdown.cgst_tickets, Decimal("45.00"))
        self.assertEqual(breakdown.sgst_tickets, Decimal("45.00"))

        # GST on convenience fee: 18% of 60 = 10.80 (CGST 5.40, SGST 5.40)
        self.assertEqual(breakdown.cgst_fee, Decimal("5.40"))
        self.assertEqual(breakdown.sgst_fee, Decimal("5.40"))

        # Total taxes: 90 + 10.80 = 100.80
        self.assertEqual(breakdown.total_tax, Decimal("100.80"))

        # Grand total: 500 + 60 + 100.80 = 660.80
        self.assertEqual(breakdown.grand_total, Decimal("660.80"))

    def test_multi_tier_booking(self):
        """Multi-tier booking: 1 Silver (150), 2 Gold (250), 1 Recliner (450)."""
        items = [
            BookingItem(tier="Silver", quantity=1, unit_price=Decimal("150.00")),
            BookingItem(tier="Gold", quantity=2, unit_price=Decimal("250.00")),
            BookingItem(tier="Recliner", quantity=1, unit_price=Decimal("450.00")),
        ]
        breakdown = self.engine.calculate(items)

        self.assertEqual(breakdown.total_tickets, 4)
        # Gross = 150 + 500 + 450 = 1100.00
        self.assertEqual(breakdown.gross_ticket_amount, Decimal("1100.00"))

        # Convenience fee: 4 x 30 = 120.00
        self.assertEqual(breakdown.total_convenience_fee, Decimal("120.00"))

        # CGST (9%) on 1100 = 99.00, SGST (9%) = 99.00
        self.assertEqual(breakdown.cgst_tickets, Decimal("99.00"))
        self.assertEqual(breakdown.sgst_tickets, Decimal("99.00"))

        # CGST (9%) on 120 = 10.80, SGST (9%) = 10.80
        self.assertEqual(breakdown.cgst_fee, Decimal("10.80"))
        self.assertEqual(breakdown.sgst_fee, Decimal("10.80"))

        # Grand total = 1100 + 120 + 198 + 21.60 = 1439.60
        self.assertEqual(breakdown.grand_total, Decimal("1439.60"))

    def test_festival_flat_discount(self):
        """Festival discount of flat 50 off."""
        items = [BookingItem(tier="Gold", quantity=2, unit_price=Decimal("250.00"))]
        offers = OfferConfig(enable_festival_discount=True, festival_flat_discount=Decimal("50.00"))
        breakdown = self.engine.calculate(items, offers=offers)

        # Gross 500, Festival Disc 50 -> Net 450
        self.assertEqual(breakdown.festival_discount_applied, Decimal("50.00"))
        self.assertEqual(breakdown.net_ticket_amount, Decimal("450.00"))

        # GST on tickets applies to net 450: 9% CGST = 40.50, 9% SGST = 40.50 -> 81.00
        self.assertEqual(breakdown.cgst_tickets, Decimal("40.50"))
        self.assertEqual(breakdown.sgst_tickets, Decimal("40.50"))

        # Fee: 60.00 + GST 10.80
        # Grand total: 450 + 60 + 81 + 10.80 = 601.80
        self.assertEqual(breakdown.grand_total, Decimal("601.80"))

    def test_member_percentage_discount_uncapped(self):
        """Member 15% discount when below cap (Gross 500 * 15% = 75 <= 100 cap)."""
        items = [BookingItem(tier="Gold", quantity=2, unit_price=Decimal("250.00"))]
        offers = OfferConfig(
            enable_member_discount=True,
            member_discount_percent=Decimal("15.00"),
            member_discount_max_cap=Decimal("100.00"),
            member_id="MEMB-998"
        )
        breakdown = self.engine.calculate(items, offers=offers)

        self.assertEqual(breakdown.member_discount_applied, Decimal("75.00"))
        self.assertEqual(breakdown.net_ticket_amount, Decimal("425.00"))

        # CGST (9% of 425 = 38.25), SGST = 38.25 -> 76.50
        self.assertEqual(breakdown.cgst_tickets, Decimal("38.25"))
        self.assertEqual(breakdown.sgst_tickets, Decimal("38.25"))

        # Grand total: 425 + 60 + 76.50 + 10.80 = 572.30
        self.assertEqual(breakdown.grand_total, Decimal("572.30"))

    def test_member_percentage_discount_capped(self):
        """Member 15% discount exceeding cap: Gross 1000 * 15% = 150 -> Capped at 100."""
        items = [BookingItem(tier="Gold", quantity=4, unit_price=Decimal("250.00"))]
        offers = OfferConfig(
            enable_member_discount=True,
            member_discount_percent=Decimal("15.00"),
            member_discount_max_cap=Decimal("100.00"),
            member_id="MEMB-101"
        )
        breakdown = self.engine.calculate(items, offers=offers)

        self.assertEqual(breakdown.gross_ticket_amount, Decimal("1000.00"))
        self.assertEqual(breakdown.member_discount_applied, Decimal("100.00"))
        self.assertEqual(breakdown.net_ticket_amount, Decimal("900.00"))

        # CGST (9% of 900) = 81.00, SGST = 81.00
        self.assertEqual(breakdown.cgst_tickets, Decimal("81.00"))
        self.assertEqual(breakdown.sgst_tickets, Decimal("81.00"))

        # 4 tickets fee = 120, CGST fee = 10.80, SGST fee = 10.80
        # Grand total = 900 + 120 + 162 + 21.60 = 1203.60
        self.assertEqual(breakdown.grand_total, Decimal("1203.60"))

    def test_stacked_festival_and_member_offers(self):
        """Combined offers: Gross 1000, Festival flat 50, Member 15% (cap 100 -> 100)."""
        items = [BookingItem(tier="Gold", quantity=4, unit_price=Decimal("250.00"))]
        offers = OfferConfig(
            enable_festival_discount=True,
            festival_flat_discount=Decimal("50.00"),
            enable_member_discount=True,
            member_discount_percent=Decimal("15.00"),
            member_discount_max_cap=Decimal("100.00"),
            member_id="VIP-77"
        )
        breakdown = self.engine.calculate(items, offers=offers)

        self.assertEqual(breakdown.gross_ticket_amount, Decimal("1000.00"))
        self.assertEqual(breakdown.festival_discount_applied, Decimal("50.00"))
        self.assertEqual(breakdown.member_discount_applied, Decimal("100.00"))
        self.assertEqual(breakdown.total_discount_applied, Decimal("150.00"))
        self.assertEqual(breakdown.net_ticket_amount, Decimal("850.00"))

        # Tax on 850: 9% CGST = 76.50, 9% SGST = 76.50
        self.assertEqual(breakdown.cgst_tickets, Decimal("76.50"))
        self.assertEqual(breakdown.sgst_tickets, Decimal("76.50"))

        # Fee: 120 + 21.60 tax
        # Total = 850 + 120 + 153 + 21.60 = 1144.60
        self.assertEqual(breakdown.grand_total, Decimal("1144.60"))

    def test_discount_cannot_exceed_ticket_gross(self):
        """Safety check: Discount should never exceed gross ticket total (no negative bills)."""
        items = [BookingItem(tier="Silver", quantity=1, unit_price=Decimal("30.00"))]
        offers = OfferConfig(
            enable_festival_discount=True,
            festival_flat_discount=Decimal("50.00"),
            enable_member_discount=True,
            member_discount_percent=Decimal("50.00"),
            member_discount_max_cap=Decimal("100.00")
        )
        breakdown = self.engine.calculate(items, offers=offers)

        # Gross is 30. Festival consumes all 30. Member discount applied is 0.
        self.assertEqual(breakdown.gross_ticket_amount, Decimal("30.00"))
        self.assertEqual(breakdown.festival_discount_applied, Decimal("30.00"))
        self.assertEqual(breakdown.member_discount_applied, Decimal("0.00"))
        self.assertEqual(breakdown.net_ticket_amount, Decimal("0.00"))
        self.assertEqual(breakdown.cgst_tickets, Decimal("0.00"))
        self.assertEqual(breakdown.sgst_tickets, Decimal("0.00"))

        # Customer still pays convenience fee + tax on fee:
        # Fee: 1 ticket x 30 = 30.00, Tax on fee = 2.70 CGST + 2.70 SGST = 5.40
        # Grand total = 35.40
        self.assertEqual(breakdown.grand_total, Decimal("35.40"))

    def test_exact_paisa_fraction_rounding(self):
        """Tests fractional amounts that require exact half-up paisa rounding."""
        # 3 tickets @ 133.33 = 399.99
        items = [BookingItem(tier="Silver", quantity=3, unit_price=Decimal("133.33"))]
        breakdown = self.engine.calculate(items)

        self.assertEqual(breakdown.gross_ticket_amount, Decimal("399.99"))
        # 9% of 399.99 = 35.9991 -> quantize half-up to 36.00
        self.assertEqual(breakdown.cgst_tickets, Decimal("36.00"))
        self.assertEqual(breakdown.sgst_tickets, Decimal("36.00"))

        # Line item integrity
        line_items_sum = sum(
            item.amount for item in breakdown.items
            if item.category in ("TICKET", "DISCOUNT", "FEE", "TAX")
        )
        self.assertEqual(line_items_sum, breakdown.grand_total)


if __name__ == "__main__":
    unittest.main()
