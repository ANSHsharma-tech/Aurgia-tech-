# CinePay: Multiplex Counter Pricing Engine & POS System
### Round 2 — Hands-On "Builder" Solution: "Friday night at the multiplex" (Including The Twist)

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![Framework](https://img.shields.io/badge/Framework-Flask%203.1-black?logo=flask)
![Tests](https://img.shields.io/badge/Tests-27%2F27%20Passing-brightgreen)
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
- **The Twist (Messy Price List Importer & Cleaner)**: Built-in sanitizer (`pricing_engine/price_list_importer.py`) that ingests messy seat-class price lists with duplicate names in varying cases, inconsistent currency formats (`₹`, `Rs.`, `INR`, commas), blank values, and negative prices. Produces a complete audit report of what was **imported**, **de-duplicated**, and **rejected**.

---

## 2. Project Architecture

```
auriga it/
├── app.py                         # Flask web server & REST API service
├── sample_messy_price_list.csv    # The Twist: Sample messy input price list
├── pricing_engine/                # Pure, decoupled calculation engine (zero web dependency)
│   ├── __init__.py
│   ├── models.py                  # Domain dataclasses (BookingItem, OfferConfig, LineItem, etc.)
│   ├── engine.py                  # Deterministic Decimal calculation engine
│   └── price_list_importer.py     # The Twist: Messy price list sanitizer & audit reporter
├── inventory/                     # Live seating capacity & multi-show catalog
│   ├── __init__.py
│   └── show_manager.py            # Thread-safe inventory reservation & dynamic tier updater
├── templates/                     # Jinja2 HTML templates
│   ├── index.html                 # Cashier POS counter terminal UI (with Cleaner modal)
│   └── receipt.html               # 80mm thermal tax invoice print template
├── static/
│   ├── css/styles.css             # Counter UI theme and @media print styling
│   └── js/counter.js              # Reactive client-side calculation & POS controller
├── tests/                         # Comprehensive automated test suites (27 tests)
│   ├── test_pricing_engine.py     # Financial edge-cases & money invariants (9 tests)
│   ├── test_show_manager.py       # Seating capacity & sold-out lockout tests (5 tests)
│   ├── test_price_list_importer.py# The Twist: Sanitizer, deduplication & rejection tests (6 tests)
│   └── test_api_integration.py    # End-to-end REST API & booking flow tests (7 tests)
├── .devcontainer/
│   └── devcontainer.json          # 1-click GitHub Codespaces configuration
├── requirements.txt               # Python dependencies (Flask, etc.)
├── README.md                      # Setup, running, and debugging guide
├── REASONING.md                   # In-depth architectural & financial reasoning document
└── AI_LOGS.md                     # Complete, unedited AI conversation log
```

---

## 3. Quickstart & Installation

### Prerequisites
- Python 3.10+ (Tested with Python 3.13)
- `pip` package manager

### A. Local Setup
```bash
# 1. Clone repository
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>

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

Run the full automated test suite containing **27 test cases**:

```bash
# Run all unit and integration tests
python -m unittest discover tests -v
```

### Test Coverage Highlights:
- **Pricing Edge Cases**: Zero tickets, single tier, multi-tier mixed bookings, exact paisa fraction rounding.
- **Offer Stacking & Bounds**: Flat festival discounts, member percentage discounts under cap, member discounts hitting cap, combined offers, and non-negative subtotal guard.
- **Taxation Arithmetic**: CGST (9%) and SGST (9%) exact splits on net tickets and convenience fees.
- **Inventory Safety**: Sold-out tier rejection, overbooking prevention, and thread-safe reservation.
- **The Twist (Sanitizer & Cleaner)**:
  - Case normalization (`silver`, `SILVER`, `  Silver  ` $\rightarrow$ `Silver`).
  - Parsing currency noise (`₹180`, `Rs. 250`, `INR 450`, `1,250.00`).
  - Rejection of negative amounts (`-150.00`, `₹-200`) and zero prices.
  - Rejection of blank tiers, missing prices, and invalid strings (`FREE`, `TBD`).
  - De-duplication resolution and tracking.

---

## 5. The Twist: Messy Price List Importer

Multiplexes frequently receive price lists exported from legacy backends, spreadsheets, or third-party ticketing partners that contain dirty data.

### Supported Dirty Input Variations:
1. **Case Variations & Whitespace**: Normalizes `"silver"`, `"SILVER"`, `"  Silver  "` $\rightarrow$ `"Silver"`.
2. **Inconsistent Price Formats**: Strips prefixes and parses integers, decimals, and comma-formatted thousands (`₹180.00`, `Rs. 250`, `INR 480.00`, `1,250.00`).
3. **Blank & Missing Values**: Automatically detects and rejects empty rows, blank tier names, or missing price cells.
4. **Negative & Zero Prices**: Rejects negative prices (`-150`, `₹-200`) and non-commercial zero rates.
5. **De-duplication & Audit**: When multiple entries exist for the same tier name, merges them, retains the latest valid price, and outputs a complete categorized audit log:
   - **Imported**: Cleaned valid records.
   - **Deduplicated**: Merged rows showing previous vs updated price.
   - **Rejected**: Entries rejected with specific human-readable failure reasons.

### How to Test The Twist:
1. **Via the POS Terminal UI**:
   - Click the top navbar button: **"Clean & Import Prices [TWIST]"**.
   - Click **"Load Sample Messy Data"** (pre-fills the sample messy dataset).
   - Click **"Clean, De-duplicate & Audit"**.
   - Inspect the three real-time audit cards:
     - 🟢 **Cleaned & Imported**: View normalized tiers and parsed prices.
     - 🟡 **De-duplication Resolutions**: View which duplicates were merged.
     - 🔴 **Rejected Records**: View rejected negative prices and blank cells.
   - Leave *"Apply cleaned prices directly to active screen"* checked to instantly update the cinema counter!
2. **Via REST API**:
   ```bash
   curl -X POST http://localhost:5000/api/prices/import \
     -H "Content-Type: application/json" \
     -d "{\"csv_text\": \"silver,180.00\\nSILVER,₹195.00\\nGold,-250\\n,300\", \"apply_to_shows\": true}"
   ```

---

## 6. API Reference

### `GET /api/shows`
Returns available movies, showtimes, screen configurations, tier base prices, and live remaining capacities.

### `POST /api/pricing/calculate`
Performs a live dry-run calculation without deducting inventory. Used by the cashier POS to render instant line-by-line figures.

### `POST /api/bookings/create`
Atomically validates capacity, deducts seats, generates final audited tax invoice, and logs transaction.

### `POST /api/prices/import`
The Twist endpoint. Cleans and imports messy price lists, returning structured reports of imported, deduplicated, and rejected entries.

### `GET /api/prices/sample`
Returns the raw contents of `sample_messy_price_list.csv` for demonstration.

---

## 7. Submission Checklist
- [x] `README.md` (Setup, execution, Codespaces guide, and Twist instructions)
- [x] `REASONING.md` (Engineering thought process, financial models, Twist heuristics)
- [x] `AI_LOGS.md` (Complete, unedited candidate-AI conversation logs)
