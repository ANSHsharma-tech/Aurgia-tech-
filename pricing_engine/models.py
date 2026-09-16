"""
CinePay Pricing Engine - Domain Data Models
Defines immutable/structured representations for cinema tiers, booking inputs,
discount rules, taxes, and line-by-line billing items.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Dict
from enum import Enum


class SeatTier(str, Enum):
    SILVER = "Silver"
    GOLD = "Gold"
    RECLINER = "Recliner"


@dataclass(frozen=True)
class TierPriceConfig:
    tier: str
    base_price: Decimal
    total_seats: int
    description: str = ""


@dataclass(frozen=True)
class BookingItem:
    tier: str
    quantity: int
    unit_price: Decimal


@dataclass(frozen=True)
class OfferConfig:
    enable_festival_discount: bool = False
    festival_flat_discount: Decimal = Decimal("50.00")
    
    enable_member_discount: bool = False
    member_discount_percent: Decimal = Decimal("15.00")  # e.g., 15%
    member_discount_max_cap: Decimal = Decimal("100.00")  # Max cap in INR
    member_id: Optional[str] = None


@dataclass(frozen=True)
class FeeAndTaxConfig:
    convenience_fee_per_ticket: Decimal = Decimal("30.00")
    
    # Cinema tickets GST rate (Standard Indian Multiplex: 18% split into 9% CGST + 9% SGST)
    # Alternatively, 12% if base price <= 100, 18% if > 100
    ticket_gst_rate_standard: Decimal = Decimal("18.00")
    ticket_gst_rate_low: Decimal = Decimal("12.00")  # For tickets <= 100 INR
    apply_tiered_ticket_gst: bool = True
    
    # Convenience fee GST rate (Standard Service Tax: 18% split into 9% CGST + 9% SGST)
    convenience_fee_gst_rate: Decimal = Decimal("18.00")


@dataclass
class LineItem:
    code: str
    description: str
    quantity: Optional[int]
    rate: Optional[Decimal]
    amount: Decimal  # Positive for charges, negative for discounts
    category: str    # "TICKET", "DISCOUNT", "FEE", "TAX", "TOTAL"
    metadata: Dict = field(default_factory=dict)


@dataclass
class PricingBreakdown:
    items: List[LineItem]
    
    # Ticket totals
    total_tickets: int
    gross_ticket_amount: Decimal
    
    # Discounts
    festival_discount_applied: Decimal
    member_discount_applied: Decimal
    total_discount_applied: Decimal
    net_ticket_amount: Decimal
    
    # Fees
    convenience_fee_per_ticket: Decimal
    total_convenience_fee: Decimal
    
    # Taxes (split into CGST and SGST for full transparency)
    cgst_tickets: Decimal
    sgst_tickets: Decimal
    cgst_fee: Decimal
    sgst_fee: Decimal
    total_cgst: Decimal
    total_sgst: Decimal
    total_tax: Decimal
    
    # Final exact amount payable
    grand_total: Decimal
    
    # Audit trail / notes for cashier or dispute resolution
    calculation_notes: List[str] = field(default_factory=list)
