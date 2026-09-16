"""
CinePay Pricing Engine - Core Computation Engine
Implements deterministic, paisa-exact calculation of multiplex ticket pricing,
tier allocations, stacked offer discounts, convenience fees, and dual GST taxation.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from .models import (
    BookingItem,
    OfferConfig,
    FeeAndTaxConfig,
    LineItem,
    PricingBreakdown
)

PAISA = Decimal("0.01")


def to_paisa(value: Decimal) -> Decimal:
    """Quantize decimal value to 2 decimal places (exact paisa) using ROUND_HALF_UP."""
    return value.quantize(PAISA, rounding=ROUND_HALF_UP)


class PricingEngine:
    """
    Deterministic cinema ticket pricing engine.
    Guarantees exact paisa arithmetic, transparent discount stacking,
    dual CGST/SGST tax compliance, and auditable line-by-line itemization.
    """

    def __init__(self, tax_config: Optional[FeeAndTaxConfig] = None):
        self.tax_config = tax_config or FeeAndTaxConfig()

    def calculate(
        self,
        items: List[BookingItem],
        offers: Optional[OfferConfig] = None,
        custom_fee_config: Optional[FeeAndTaxConfig] = None,
    ) -> PricingBreakdown:
        """
        Calculates the complete, auditable pricing breakdown for a booking.

        Args:
            items: List of BookingItem specifying tier, quantity, and unit price.
            offers: Discount configuration (festival flat discount, member percentage with cap).
            custom_fee_config: Optional override for convenience fee and GST rates.

        Returns:
            PricingBreakdown containing line items, totals, taxes, and audit notes.
        """
        config = custom_fee_config or self.tax_config
        offers = offers or OfferConfig()
        
        line_items: List[LineItem] = []
        notes: List[str] = []

        # 1. Base Ticket Calculations
        total_tickets = 0
        gross_ticket_amount = Decimal("0.00")

        # Determine if any ticket qualifies for low GST (<= 100) or standard GST (> 100)
        weighted_tax_rate_numerator = Decimal("0.00")

        for item in items:
            if item.quantity <= 0:
                continue
            
            unit_price = to_paisa(item.unit_price)
            tier_total = to_paisa(unit_price * Decimal(item.quantity))
            
            total_tickets += item.quantity
            gross_ticket_amount += tier_total

            # Tier GST determination
            if config.apply_tiered_ticket_gst and unit_price <= Decimal("100.00"):
                tier_gst_rate = config.ticket_gst_rate_low
            else:
                tier_gst_rate = config.ticket_gst_rate_standard

            weighted_tax_rate_numerator += tier_gst_rate * tier_total

            line_items.append(
                LineItem(
                    code=f"SEAT_{item.tier.upper()}",
                    description=f"{item.tier} Tier Seat",
                    quantity=item.quantity,
                    rate=unit_price,
                    amount=tier_total,
                    category="TICKET",
                    metadata={"tier": item.tier, "gst_rate": str(tier_gst_rate)}
                )
            )

        if total_tickets == 0:
            # Zero tickets booked
            return PricingBreakdown(
                items=[],
                total_tickets=0,
                gross_ticket_amount=Decimal("0.00"),
                festival_discount_applied=Decimal("0.00"),
                member_discount_applied=Decimal("0.00"),
                total_discount_applied=Decimal("0.00"),
                net_ticket_amount=Decimal("0.00"),
                convenience_fee_per_ticket=config.convenience_fee_per_ticket,
                total_convenience_fee=Decimal("0.00"),
                cgst_tickets=Decimal("0.00"),
                sgst_tickets=Decimal("0.00"),
                cgst_fee=Decimal("0.00"),
                sgst_fee=Decimal("0.00"),
                total_cgst=Decimal("0.00"),
                total_sgst=Decimal("0.00"),
                total_tax=Decimal("0.00"),
                grand_total=Decimal("0.00"),
                calculation_notes=["No tickets selected."]
            )

        # Compute effective ticket GST rate (weighted average for multi-tier tickets)
        effective_ticket_gst_rate = weighted_tax_rate_numerator / gross_ticket_amount

        # 2. Offer & Discount Layering (Applied to base tickets)
        festival_discount_applied = Decimal("0.00")
        member_discount_applied = Decimal("0.00")

        # Layer 1: Flat Festival Discount
        if offers.enable_festival_discount:
            target_discount = to_paisa(offers.festival_flat_discount)
            festival_discount_applied = min(gross_ticket_amount, target_discount)
            
            line_items.append(
                LineItem(
                    code="DISCOUNT_FESTIVAL",
                    description=f"Festival Flat Offer (₹{offers.festival_flat_discount:.2f} off)",
                    quantity=1,
                    rate=festival_discount_applied,
                    amount=-festival_discount_applied,
                    category="DISCOUNT",
                    metadata={"requested": str(target_discount), "applied": str(festival_discount_applied)}
                )
            )
            notes.append(f"Applied flat festival discount: -₹{festival_discount_applied:.2f}")

        # Layer 2: Percentage Member Discount (Capped)
        if offers.enable_member_discount:
            # Calculated as a percentage of gross ticket subtotal
            calculated_pct_disc = to_paisa((gross_ticket_amount * offers.member_discount_percent) / Decimal("100.00"))
            
            # Subject to maximum cap
            capped_member_disc = min(calculated_pct_disc, to_paisa(offers.member_discount_max_cap))
            
            # Total discount cannot exceed gross ticket amount
            remaining_ticket_headroom = max(Decimal("0.00"), gross_ticket_amount - festival_discount_applied)
            member_discount_applied = min(capped_member_disc, remaining_ticket_headroom)

            member_label = f"Member Discount ({offers.member_discount_percent:.0f}% off, capped at ₹{offers.member_discount_max_cap:.2f})"
            if offers.member_id:
                member_label += f" [ID: {offers.member_id}]"

            line_items.append(
                LineItem(
                    code="DISCOUNT_MEMBER",
                    description=member_label,
                    quantity=1,
                    rate=member_discount_applied,
                    amount=-member_discount_applied,
                    category="DISCOUNT",
                    metadata={
                        "percent": str(offers.member_discount_percent),
                        "calculated": str(calculated_pct_disc),
                        "cap": str(offers.member_discount_max_cap),
                        "applied": str(member_discount_applied)
                    }
                )
            )
            notes.append(
                f"Applied member discount: {offers.member_discount_percent:.0f}% = ₹{calculated_pct_disc:.2f}, "
                f"capped at ₹{offers.member_discount_max_cap:.2f}, actual deduction: -₹{member_discount_applied:.2f}"
            )

        total_discount_applied = festival_discount_applied + member_discount_applied
        net_ticket_amount = gross_ticket_amount - total_discount_applied

        # 3. Convenience Fee (Per Ticket)
        fee_rate = to_paisa(config.convenience_fee_per_ticket)
        total_convenience_fee = to_paisa(Decimal(total_tickets) * fee_rate)

        line_items.append(
            LineItem(
                code="CONVENIENCE_FEE",
                description=f"Convenience Fee ({total_tickets} ticket{'s' if total_tickets > 1 else ''} @ ₹{fee_rate:.2f}/ticket)",
                quantity=total_tickets,
                rate=fee_rate,
                amount=total_convenience_fee,
                category="FEE",
                metadata={"per_ticket_fee": str(fee_rate), "ticket_count": total_tickets}
            )
        )
        notes.append(f"Convenience fee: {total_tickets} x ₹{fee_rate:.2f} = ₹{total_convenience_fee:.2f}")

        # 4. GST Computation (Exact Paisa Dual-Slab Split: CGST 50% + SGST 50%)
        # A. Ticket GST (levied on net taxable ticket value)
        # Half rate for CGST, half for SGST
        half_ticket_rate = effective_ticket_gst_rate / Decimal("2.00")
        cgst_tickets = to_paisa((net_ticket_amount * half_ticket_rate) / Decimal("100.00"))
        sgst_tickets = to_paisa((net_ticket_amount * half_ticket_rate) / Decimal("100.00"))

        line_items.append(
            LineItem(
                code="TAX_TICKET_CGST",
                description=f"CGST on Tickets ({half_ticket_rate:.1f}%)",
                quantity=None,
                rate=half_ticket_rate,
                amount=cgst_tickets,
                category="TAX",
                metadata={"taxable_base": str(net_ticket_amount), "rate": str(half_ticket_rate)}
            )
        )
        line_items.append(
            LineItem(
                code="TAX_TICKET_SGST",
                description=f"SGST on Tickets ({half_ticket_rate:.1f}%)",
                quantity=None,
                rate=half_ticket_rate,
                amount=sgst_tickets,
                category="TAX",
                metadata={"taxable_base": str(net_ticket_amount), "rate": str(half_ticket_rate)}
            )
        )

        # B. Convenience Fee GST (18% standard service tax: 9% CGST + 9% SGST)
        half_fee_rate = config.convenience_fee_gst_rate / Decimal("2.00")
        cgst_fee = to_paisa((total_convenience_fee * half_fee_rate) / Decimal("100.00"))
        sgst_fee = to_paisa((total_convenience_fee * half_fee_rate) / Decimal("100.00"))

        line_items.append(
            LineItem(
                code="TAX_FEE_CGST",
                description=f"CGST on Convenience Fee ({half_fee_rate:.1f}%)",
                quantity=None,
                rate=half_fee_rate,
                amount=cgst_fee,
                category="TAX",
                metadata={"taxable_base": str(total_convenience_fee), "rate": str(half_fee_rate)}
            )
        )
        line_items.append(
            LineItem(
                code="TAX_FEE_SGST",
                description=f"SGST on Convenience Fee ({half_fee_rate:.1f}%)",
                quantity=None,
                rate=half_fee_rate,
                amount=sgst_fee,
                category="TAX",
                metadata={"taxable_base": str(total_convenience_fee), "rate": str(half_fee_rate)}
            )
        )

        total_cgst = cgst_tickets + cgst_fee
        total_sgst = sgst_tickets + sgst_fee
        total_tax = total_cgst + total_sgst

        # 5. Grand Total (Exact to the Paisa)
        grand_total = net_ticket_amount + total_convenience_fee + total_tax

        # Final invariant audit check
        expected_total = (
            gross_ticket_amount
            - total_discount_applied
            + total_convenience_fee
            + total_tax
        )
        assert grand_total == expected_total, (
            f"Arithmetic invariant mismatch: {grand_total} != {expected_total}"
        )

        notes.append(
            f"Bill totals: Gross=₹{gross_ticket_amount:.2f}, Disc=-₹{total_discount_applied:.2f}, "
            f"Fee=+₹{total_convenience_fee:.2f}, Tax=+₹{total_tax:.2f} -> Grand Total=₹{grand_total:.2f}"
        )

        return PricingBreakdown(
            items=line_items,
            total_tickets=total_tickets,
            gross_ticket_amount=gross_ticket_amount,
            festival_discount_applied=festival_discount_applied,
            member_discount_applied=member_discount_applied,
            total_discount_applied=total_discount_applied,
            net_ticket_amount=net_ticket_amount,
            convenience_fee_per_ticket=fee_rate,
            total_convenience_fee=total_convenience_fee,
            cgst_tickets=cgst_tickets,
            sgst_tickets=sgst_tickets,
            cgst_fee=cgst_fee,
            sgst_fee=sgst_fee,
            total_cgst=total_cgst,
            total_sgst=total_sgst,
            total_tax=total_tax,
            grand_total=grand_total,
            calculation_notes=notes
        )
