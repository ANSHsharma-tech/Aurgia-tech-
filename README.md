# CinePay: Multiplex Counter Pricing Engine & POS System
### Round 2 — Hands-On "Builder" Solution: "Friday night at the multiplex"

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![Framework](https://img.shields.io/badge/Framework-Flask%203.1-black?logo=flask)
![Tests](https://img.shields.io/badge/Tests-19%2F19%20Passing-brightgreen)
![Precision](https://img.shields.io/badge/Arithmetic-Paisa--Exact%20Decimal-orange)

---

## 1. Executive Summary

On a high-volume Friday night at a cinema multiplex, booking counters face angry queues due to mis-priced tickets, ambiguous billing calculations, sold-out tier overbookings, and discrepancies in tax rounding.

**CinePay** is an end-to-end pricing engine and cashier Point-Of-Sale (POS) terminal built to eliminate mis-pricing and restore queue trust. It handles real-world money rules with mathematical rigor:
- **Exact Paisa Precision**: Pure `decimal.Decimal` computation with `ROUND_HALF_UP` prevents IEEE-754 floating-point drift.
- **Dynamic Seating Tiers & Inventory**: Manages Silver, Gold, and Recliner tiers across multiple screens/shows with live capacity tracking and sold-out lockouts.
- **Stacked Offers & Discount Bounds**: Computes flat festival discounts and capped member percentage discounts without letting ticket totals dip below zero.
- **Per-Ticket Convenience Fee**: Automatically computed per ticket as an explicit service item.
- **Dual-Slab Indian GST Compliance**: Separates CGST (9%) and SGST (9%) on net ticket prices and convenience fees.
- **Auditable Line-by-Line Receipt**: Provides customers and cashiers with an indisputable breakdown and printable thermal tax invoice.

---

## 2. Project Architecture

```
auriga it/
├── app.py                     # Flask web server & REST API service
├── pricing_engine/            # Pure, decoupled calculation engine (zero web dependency)
│   ├── __init__.py
│   ├── models.py              # Domain dataclasses (BookingItem, OfferConfig, LineItem, etc.)
│   └── engine.py              # Deterministic Decimal calculation engine
├── inventory/                 # Live seating capacity & multi-show catalog
│   ├── __init__.py
│   └── show_manager.py        # Thread-safe inventory reservation & booking ledger
├── templates/                 # Jinja2 HTML templates
│   ├── index.html             # Cashier POS counter terminal UI
│   └── receipt.html           # 80mm thermal tax invoice print template
├── static/
│   ├── css/styles.css         # Counter UI theme and @media print styling
│   └── js/counter.js          # Reactive client-side calculation & POS controller
├── tests/                     # Comprehensive automated test suites
│   ├── test_pricing_engine.py # Financial edge-cases & money invariants (9 tests)
│   ├── test_show_manager.py   # Seating capacity & sold-out lockout tests (5 tests)
│   └── test_api_integration.py# End-to-end REST API & booking flow tests (5 tests)
├── requirements.txt           # Python dependencies (Flask, etc.)
├── README.md                  # Setup, running, and debugging guide
├── REASONING.md               # In-depth architectural & financial reasoning document
└── AI_LOGS.md                 # Complete, unedited AI conversation log
```

---

## 3. Quickstart & Installation

### Prerequisites
- Python 3.10+ (Tested with Python 3.13)
- `pip` package manager

### A. Local Setup
```bash
# 1. Clone repository
git clone https://github.com/<your-username>/cinepay-pricing-engine.git
cd cinepay-pricing-engine

# 2. (Optional) Create virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the application
python app.py
```
The POS terminal will be available at: **`http://localhost:5000`**

### B. Running in GitHub Codespaces
1. Open this repository in **GitHub Codespaces**.
2. Run in the Codespaces terminal:
   ```bash
   pip install -r requirements.txt
   python app.py
   ```
3. Click on the popup **"Open in Browser"** (Port 5000) or open the **Ports** tab to access the live POS terminal.

---

## 4. Running Automated Tests

Run the full automated test suite containing 19 test cases:

```bash
# Run all unit and integration tests
python -m unittest discover tests -v
```

### Test Coverage Highlights:
- **Pricing Edge Cases**: Zero tickets, single tier, multi-tier mixed bookings, exact paisa fraction rounding.
- **Offer Stacking & Bounds**: Flat festival discounts, member percentage discounts under cap, member discounts hitting cap, combined offers, and non-negative subtotal guard.
- **Taxation Arithmetic**: CGST (9%) and SGST (9%) exact splits on net tickets and convenience fees.
- **Inventory Safety**: Sold-out tier rejection, overbooking prevention, and thread-safe reservation.

---

## 5. API Reference

### `GET /api/shows`
Returns available movies, showtimes, screen configurations, tier base prices, and live remaining capacities.

### `POST /api/pricing/calculate`
Performs a live dry-run calculation without deducting inventory. Used by the cashier POS to render instant line-by-line figures.
```json
{
  "show_id": "SHOW-101",
  "items": [
    {"tier": "Silver", "quantity": 2},
    {"tier": "Gold", "quantity": 1}
  ],
  "offers": {
    "enable_festival_discount": true,
    "festival_flat_discount": 50.00,
    "enable_member_discount": true,
    "member_discount_percent": 15.00,
    "member_discount_max_cap": 100.00,
    "member_id": "VIP-9988"
  }
}
```

### `POST /api/bookings/create`
Atomically validates capacity, deducts seats, generates final audited tax invoice, and logs transaction.
```json
{
  "show_id": "SHOW-101",
  "items": [{"tier": "Silver", "quantity": 2}],
  "offers": {"enable_festival_discount": false, "enable_member_discount": false},
  "customer_name": "Rohan Gupta",
  "customer_phone": "9876543210",
  "payment_mode": "UPI / QR Code"
}
```

### `GET /api/bookings`
Returns transaction audit history for counter reconciliation.

### `POST /api/inventory/reset`
Resets show inventory back to initial demo state (useful for demonstrating sold-out lockouts).

---

## 6. Debugging & Verification Guide

1. **Simulate Sold-Out Tiers**:
   - In the POS interface, select **"Dune: Part Two"** (Audi 1). Notice the **Recliner** tier is marked **SOLD OUT** (12/12 booked) and disabled. Attempting to book it via API returns HTTP 400 with an explicit message.
2. **Verify Discount Cap Boundary**:
   - Select 4 Gold tickets in "Interstellar" (Gross = ₹1,400.00).
   - Enable **Club Membership** (15%). 15% of ₹1,400 is ₹210.00, but the bill enforces the ₹100.00 cap, deducting exactly ₹100.00.
3. **Paisa Precision Audit**:
   - Check the **"Customer Audit Note: View Exact Math Formula"** accordion at the bottom of the bill. It details every line calculation down to the exact paisa.
4. **Thermal Receipt Printing**:
   - Complete a booking and click **"Print Thermal Receipt"**. The receipt uses a specialized CSS print sheet sized for 80mm thermal receipt rolls with GSTIN and tax breakdowns.
