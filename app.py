"""
CinePay Multiplex Counter POS & Pricing Service
Production-ready web application providing real-time pricing calculations,
seat tier inventory management, and printable thermal tax receipts.
"""

from decimal import Decimal
from typing import Dict, Any
from flask import Flask, request, jsonify, render_template

from pricing_engine.models import BookingItem, OfferConfig, FeeAndTaxConfig
from pricing_engine.engine import PricingEngine
from inventory.show_manager import ShowManager

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Singleton application services
pricing_engine = PricingEngine()
show_manager = ShowManager()


def serialize_breakdown(breakdown) -> Dict[str, Any]:
    """Converts PricingBreakdown to a JSON-serializable dictionary with currency strings."""
    return {
        "total_tickets": breakdown.total_tickets,
        "gross_ticket_amount": float(breakdown.gross_ticket_amount),
        "gross_ticket_amount_fmt": f"₹{breakdown.gross_ticket_amount:.2f}",
        "festival_discount_applied": float(breakdown.festival_discount_applied),
        "festival_discount_applied_fmt": f"₹{breakdown.festival_discount_applied:.2f}",
        "member_discount_applied": float(breakdown.member_discount_applied),
        "member_discount_applied_fmt": f"₹{breakdown.member_discount_applied:.2f}",
        "total_discount_applied": float(breakdown.total_discount_applied),
        "total_discount_applied_fmt": f"₹{breakdown.total_discount_applied:.2f}",
        "net_ticket_amount": float(breakdown.net_ticket_amount),
        "net_ticket_amount_fmt": f"₹{breakdown.net_ticket_amount:.2f}",
        "convenience_fee_per_ticket": float(breakdown.convenience_fee_per_ticket),
        "convenience_fee_per_ticket_fmt": f"₹{breakdown.convenience_fee_per_ticket:.2f}",
        "total_convenience_fee": float(breakdown.total_convenience_fee),
        "total_convenience_fee_fmt": f"₹{breakdown.total_convenience_fee:.2f}",
        "cgst_tickets": float(breakdown.cgst_tickets),
        "cgst_tickets_fmt": f"₹{breakdown.cgst_tickets:.2f}",
        "sgst_tickets": float(breakdown.sgst_tickets),
        "sgst_tickets_fmt": f"₹{breakdown.sgst_tickets:.2f}",
        "cgst_fee": float(breakdown.cgst_fee),
        "cgst_fee_fmt": f"₹{breakdown.cgst_fee:.2f}",
        "sgst_fee": float(breakdown.sgst_fee),
        "sgst_fee_fmt": f"₹{breakdown.sgst_fee:.2f}",
        "total_cgst": float(breakdown.total_cgst),
        "total_cgst_fmt": f"₹{breakdown.total_cgst:.2f}",
        "total_sgst": float(breakdown.total_sgst),
        "total_sgst_fmt": f"₹{breakdown.total_sgst:.2f}",
        "total_tax": float(breakdown.total_tax),
        "total_tax_fmt": f"₹{breakdown.total_tax:.2f}",
        "grand_total": float(breakdown.grand_total),
        "grand_total_fmt": f"₹{breakdown.grand_total:.2f}",
        "calculation_notes": breakdown.calculation_notes,
        "line_items": [
            {
                "code": item.code,
                "description": item.description,
                "quantity": item.quantity,
                "rate": float(item.rate) if item.rate is not None else None,
                "rate_fmt": f"₹{item.rate:.2f}" if item.rate is not None else "-",
                "amount": float(item.amount),
                "amount_fmt": f"{'-' if item.amount < 0 else ''}₹{abs(item.amount):.2f}",
                "category": item.category,
                "metadata": item.metadata,
            }
            for item in breakdown.items
        ]
    }


def parse_booking_items(items_data, show) -> list[BookingItem]:
    booking_items = []
    for raw in items_data:
        tier_name = raw.get("tier")
        qty = int(raw.get("quantity", 0))
        if qty <= 0:
            continue
        if tier_name not in show.tiers:
            raise ValueError(f"Unknown tier '{tier_name}' for this show.")
        unit_price = show.tiers[tier_name].base_price
        booking_items.append(BookingItem(tier=tier_name, quantity=qty, unit_price=unit_price))
    return booking_items


def parse_offers(raw_offers: dict) -> OfferConfig:
    if not raw_offers:
        return OfferConfig()
    
    return OfferConfig(
        enable_festival_discount=bool(raw_offers.get("enable_festival_discount", False)),
        festival_flat_discount=Decimal(str(raw_offers.get("festival_flat_discount", "50.00"))),
        enable_member_discount=bool(raw_offers.get("enable_member_discount", False)),
        member_discount_percent=Decimal(str(raw_offers.get("member_discount_percent", "15.00"))),
        member_discount_max_cap=Decimal(str(raw_offers.get("member_discount_max_cap", "100.00"))),
        member_id=raw_offers.get("member_id") or None
    )


# ===================== REST API ENDPOINTS =====================

@app.route("/api/shows", methods=["GET"])
def api_get_shows():
    """Returns list of movies, showtimes, screen details, tier pricing and live seat availability."""
    shows = show_manager.get_all_shows()
    return jsonify({"status": "success", "shows": shows})


@app.route("/api/pricing/calculate", methods=["POST"])
def api_calculate_pricing():
    """
    Live dry-run calculation for the POS counter.
    Receives show_id, requested seat quantities per tier, and active offers.
    Returns exact line-by-line breakdown without modifying inventory.
    """
    data = request.get_json() or {}
    show_id = data.get("show_id")
    show = show_manager.get_show(show_id)
    if not show:
        return jsonify({"status": "error", "message": f"Show '{show_id}' not found."}), 404

    try:
        booking_items = parse_booking_items(data.get("items", []), show)
        offers = parse_offers(data.get("offers", {}))
        breakdown = pricing_engine.calculate(booking_items, offers=offers)
        
        return jsonify({
            "status": "success",
            "show_id": show_id,
            "movie_title": show.movie_title,
            "screen_name": show.screen_name,
            "show_time": show.show_time,
            "pricing": serialize_breakdown(breakdown)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/bookings/create", methods=["POST"])
def api_create_booking():
    """
    Finalizes a ticket sale:
    - Atomically validates seat capacity & checks for sold-out tiers.
    - Locks seats and decrements inventory.
    - Computes exact final bill breakdown.
    - Saves audit transaction and returns printable receipt payload.
    """
    data = request.get_json() or {}
    show_id = data.get("show_id")
    show = show_manager.get_show(show_id)
    if not show:
        return jsonify({"status": "error", "message": f"Show '{show_id}' not found."}), 404

    try:
        booking_items = parse_booking_items(data.get("items", []), show)
        if not booking_items or sum(item.quantity for item in booking_items) == 0:
            return jsonify({"status": "error", "message": "At least 1 ticket must be selected."}), 400

        # Step 1: Atomic seat reservation (locks inventory or raises error)
        show_manager.validate_and_reserve_seats(show_id, booking_items)

        # Step 2: Exact Paisa Pricing computation
        offers = parse_offers(data.get("offers", {}))
        breakdown = pricing_engine.calculate(booking_items, offers=offers)

        # Step 3: Record transaction in audit ledger
        customer_name = data.get("customer_name") or "Counter Walk-in"
        customer_phone = data.get("customer_phone") or "N/A"
        payment_mode = data.get("payment_mode") or "UPI / QR"

        booking_payload = {
            "show_id": show_id,
            "movie_title": show.movie_title,
            "screen_name": show.screen_name,
            "show_time": show.show_time,
            "experience": show.experience,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "payment_mode": payment_mode,
            "items_booked": [
                {"tier": item.tier, "quantity": item.quantity, "unit_price": float(item.unit_price)}
                for item in booking_items
            ],
            "offers_used": {
                "festival_discount": offers.enable_festival_discount,
                "member_discount": offers.enable_member_discount,
                "member_id": offers.member_id
            },
            "pricing": serialize_breakdown(breakdown)
        }

        booking_id = show_manager.record_booking(booking_payload)
        booking_payload["booking_id"] = booking_id

        return jsonify({
            "status": "success",
            "message": "Booking successful! Seats reserved and tax receipt generated.",
            "booking_id": booking_id,
            "receipt": booking_payload,
            "updated_shows": show_manager.get_all_shows()
        })

    except ValueError as val_err:
        return jsonify({"status": "error", "message": str(val_err)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server processing error: {str(e)}"}), 500


@app.route("/api/bookings", methods=["GET"])
def api_get_bookings():
    """Returns past counter bookings for history log and reprints."""
    return jsonify({"status": "success", "bookings": show_manager.get_all_bookings()})


@app.route("/api/bookings/<booking_id>", methods=["GET"])
def api_get_booking_by_id(booking_id: str):
    """Retrieves specific booking data."""
    booking = show_manager.get_booking(booking_id)
    if not booking:
        return jsonify({"status": "error", "message": "Booking not found."}), 404
    return jsonify({"status": "success", "booking": booking})


@app.route("/api/inventory/reset", methods=["POST"])
def api_reset_inventory():
    """Resets seat inventory and booking history for demonstration purposes."""
    show_manager.reset_inventory()
    return jsonify({"status": "success", "message": "Inventory successfully reset."})


# ===================== FRONTEND VIEWS =====================

@app.route("/")
def index_view():
    """Renders CinePay Counter POS Terminal."""
    return render_template("index.html")


@app.route("/receipt/<booking_id>")
def receipt_view(booking_id: str):
    """Renders dedicated thermal receipt view."""
    booking = show_manager.get_booking(booking_id)
    return render_template("receipt.html", booking=booking)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
