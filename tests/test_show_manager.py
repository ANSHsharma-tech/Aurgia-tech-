"""
Unit Tests for CinePay Show and Inventory Manager
"""

import unittest
from decimal import Decimal
from inventory.show_manager import ShowManager
from pricing_engine.models import BookingItem


class TestShowManager(unittest.TestCase):

    def setUp(self):
        self.manager = ShowManager()

    def test_initial_catalog_and_sold_out_state(self):
        shows = self.manager.get_all_shows()
        self.assertEqual(len(shows), 3)

        # In SHOW-101, Recliner is seeded with 12/12 booked
        show_101 = self.manager.get_show("SHOW-101")
        self.assertIsNotNone(show_101)
        self.assertTrue(show_101.tiers["Recliner"].is_sold_out)
        self.assertEqual(show_101.tiers["Recliner"].available_seats, 0)

        # Silver has 50 - 46 = 4 available
        self.assertEqual(show_101.tiers["Silver"].available_seats, 4)

    def test_successful_reservation(self):
        # Book 2 Silver seats from SHOW-101 (initial available = 4)
        items = [BookingItem(tier="Silver", quantity=2, unit_price=Decimal("180.00"))]
        self.manager.validate_and_reserve_seats("SHOW-101", items)

        show = self.manager.get_show("SHOW-101")
        self.assertEqual(show.tiers["Silver"].available_seats, 2)
        self.assertEqual(show.tiers["Silver"].booked_seats, 48)

    def test_overbooking_rejection(self):
        # Silver has 4 seats left. Trying to book 5 should raise ValueError
        items = [BookingItem(tier="Silver", quantity=5, unit_price=Decimal("180.00"))]
        with self.assertRaises(ValueError) as ctx:
            self.manager.validate_and_reserve_seats("SHOW-101", items)
        self.assertIn("Only 4 seat(s) remaining", str(ctx.exception))

    def test_sold_out_rejection(self):
        # Recliner is sold out. Trying to book 1 should raise ValueError
        items = [BookingItem(tier="Recliner", quantity=1, unit_price=Decimal("480.00"))]
        with self.assertRaises(ValueError) as ctx:
            self.manager.validate_and_reserve_seats("SHOW-101", items)
        self.assertIn("completely SOLD OUT", str(ctx.exception))

    def test_record_and_retrieve_booking(self):
        booking_data = {
            "customer_name": "Rohan Gupta",
            "movie": "Dune: Part Two",
            "grand_total": 660.80
        }
        booking_id = self.manager.record_booking(booking_data)
        self.assertTrue(booking_id.startswith("CP-"))

        record = self.manager.get_booking(booking_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["customer_name"], "Rohan Gupta")


if __name__ == "__main__":
    unittest.main()
