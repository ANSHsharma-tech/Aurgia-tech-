"""
Integration tests for CinePay Flask Web Application & REST APIs
"""

import unittest
import json
from app import app, show_manager


class TestCinePayAPI(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        show_manager.reset_inventory()

    def test_get_shows(self):
        res = self.client.get("/api/shows")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(len(data["shows"]), 3)

    def test_calculate_pricing_api(self):
        payload = {
            "show_id": "SHOW-101",
            "items": [
                {"tier": "Silver", "quantity": 2},
                {"tier": "Gold", "quantity": 1}
            ],
            "offers": {
                "enable_festival_discount": True,
                "festival_flat_discount": 50.00,
                "enable_member_discount": True,
                "member_discount_percent": 15.00,
                "member_discount_max_cap": 100.00,
                "member_id": "TEST-123"
            }
        }
        res = self.client.post(
            "/api/pricing/calculate",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        pricing = data["pricing"]

        # 2 Silver @ 180 + 1 Gold @ 280 = 360 + 280 = 640 gross
        self.assertEqual(pricing["gross_ticket_amount"], 640.00)
        self.assertEqual(pricing["festival_discount_applied"], 50.00)
        # Member 15% of 640 = 96.00 (under 100 cap)
        self.assertEqual(pricing["member_discount_applied"], 96.00)
        # Net tickets = 640 - 146 = 494.00
        self.assertEqual(pricing["net_ticket_amount"], 494.00)
        # Convenience fee: 3 tickets @ 30 = 90.00
        self.assertEqual(pricing["total_convenience_fee"], 90.00)
        # 18% GST on 494 = 88.92 (44.46 CGST + 44.46 SGST)
        self.assertEqual(pricing["cgst_tickets"], 44.46)
        self.assertEqual(pricing["sgst_tickets"], 44.46)
        # 18% GST on 90 = 16.20 (8.10 CGST + 8.10 SGST)
        self.assertEqual(pricing["cgst_fee"], 8.10)
        self.assertEqual(pricing["sgst_fee"], 8.10)
        # Grand total = 494 + 90 + 88.92 + 16.20 = 689.12
        self.assertEqual(pricing["grand_total"], 689.12)

    def test_create_booking_success(self):
        payload = {
            "show_id": "SHOW-101",
            "items": [{"tier": "Silver", "quantity": 2}],
            "offers": {"enable_festival_discount": False, "enable_member_discount": False},
            "customer_name": "Aarav Sharma",
            "customer_phone": "9998887776",
            "payment_mode": "UPI / QR"
        }
        res = self.client.post(
            "/api/bookings/create",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["booking_id"].startswith("CP-"))

        # Verify receipt page loads for this booking
        receipt_res = self.client.get(f"/receipt/{data['booking_id']}")
        self.assertEqual(receipt_res.status_code, 200)
        self.assertIn(b"Aarav Sharma", receipt_res.data)

    def test_create_booking_sold_out_rejection(self):
        # Recliner in SHOW-101 is already sold out (12/12 booked)
        payload = {
            "show_id": "SHOW-101",
            "items": [{"tier": "Recliner", "quantity": 1}],
            "offers": {}
        }
        res = self.client.post(
            "/api/bookings/create",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn("completely SOLD OUT", data["message"])

    def test_index_page(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"CinePay", res.data)


if __name__ == "__main__":
    unittest.main()
