"""
CinePay Messy Price List Importer & Data Sanitizer
Cleans messy seat-class price lists with:
- Case normalization (e.g., 'silver', 'SILVER', '  Silver  ' -> 'Silver')
- Inconsistent price parsing (e.g., '₹180', 'Rs. 250.00', 'INR 450', '1,250.50')
- Blank values handling
- Negative and zero price rejection
- De-duplication and comprehensive audit reporting
"""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class CleanedPriceEntry:
    tier: str
    price: Decimal
    price_formatted: str
    original_raw_tier: str
    original_raw_price: str


@dataclass
class DeduplicatedEntry:
    tier: str
    previous_price: Decimal
    new_price: Decimal
    resolution: str
    raw_row: Dict[str, Any]


@dataclass
class RejectedEntry:
    row_number: Optional[int]
    raw_tier: Any
    raw_price: Any
    reason: str


@dataclass
class PriceListImportReport:
    total_records_processed: int
    imported: List[CleanedPriceEntry] = field(default_factory=list)
    deduplicated: List[DeduplicatedEntry] = field(default_factory=list)
    rejected: List[RejectedEntry] = field(default_factory=list)

    @property
    def imported_count(self) -> int:
        return len(self.imported)

    @property
    def deduplicated_count(self) -> int:
        return len(self.deduplicated)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_processed": self.total_records_processed,
            "imported_count": self.imported_count,
            "deduplicated_count": self.deduplicated_count,
            "rejected_count": self.rejected_count,
            "imported": [
                {
                    "tier": item.tier,
                    "price": float(item.price),
                    "price_formatted": item.price_formatted,
                    "original_tier": item.original_raw_tier,
                    "original_price": item.original_raw_price,
                }
                for item in self.imported
            ],
            "deduplicated": [
                {
                    "tier": d.tier,
                    "previous_price": float(d.previous_price),
                    "new_price": float(d.new_price),
                    "resolution": d.resolution,
                }
                for d in self.deduplicated
            ],
            "rejected": [
                {
                    "row_number": r.row_number,
                    "raw_tier": str(r.raw_tier) if r.raw_tier is not None else "",
                    "raw_price": str(r.raw_price) if r.raw_price is not None else "",
                    "reason": r.reason,
                }
                for r in self.rejected
            ],
        }


class PriceListSanitizer:
    """
    Robust sanitizer for messy cinema seat price lists.
    """

    PAISA = Decimal("0.01")

    @classmethod
    def normalize_tier_name(cls, raw_tier: Any) -> Optional[str]:
        """Normalizes tier names: strips whitespace, converts to Title Case, removes noise."""
        if raw_tier is None:
            return None
        text = str(raw_tier).strip()
        if not text or text.lower() in ("none", "null", "nan", "n/a", "-", ""):
            return None
        
        # Clean extra spaces
        text = re.sub(r"\s+", " ", text)
        return text.title()

    @classmethod
    def parse_price(cls, raw_price: Any) -> Tuple[Optional[Decimal], Optional[str]]:
        """
        Parses inconsistent price representations.
        Returns (Decimal, None) if successful.
        Returns (None, error_reason) if rejected.
        """
        if raw_price is None:
            return None, "Blank or missing price"

        price_str = str(raw_price).strip()
        if not price_str or price_str.lower() in ("none", "null", "nan", "n/a", "-", "tbd", "free", ""):
            return None, "Blank or unassigned price"

        # Check for explicitly negative values with minus sign
        is_negative = False
        if "-" in price_str or "(" in price_str:
            # Check if this represents negative amount
            cleaned_neg = re.sub(r"[^\d.-]", "", price_str)
            try:
                val = float(cleaned_neg)
                if val < 0:
                    return None, f"Negative price is invalid ({price_str})"
            except ValueError:
                pass

        # Strip currency symbols, spaces, commas: '₹', 'Rs.', 'INR', '$', ','
        cleaned_str = re.sub(r"[₹$]|rs\.?|inr|,|\s", "", price_str, flags=re.IGNORECASE)

        if not cleaned_str:
            return None, f"Unable to parse numeric price from '{price_str}'"

        try:
            val = Decimal(cleaned_str).quantize(cls.PAISA, rounding=ROUND_HALF_UP)
            if val < Decimal("0.00"):
                return None, f"Negative price is invalid ({val})"
            if val == Decimal("0.00"):
                return None, "Zero price rejected (seat tiers must have positive base price)"
            return val, None
        except (InvalidOperation, ValueError):
            return None, f"Unparseable price format: '{price_str}'"

    def import_and_clean(
        self,
        raw_entries: List[Dict[str, Any]],
        tier_key: str = "tier",
        price_key: str = "price"
    ) -> PriceListImportReport:
        """
        Processes a list of raw dictionaries representing messy seat price rows.
        De-duplicates by normalized tier name, rejecting bad entries with full audit trail.
        """
        report = PriceListImportReport(total_records_processed=len(raw_entries))
        
        # Map of normalized_tier -> index in report.imported
        tier_map: Dict[str, int] = {}

        for idx, row in enumerate(raw_entries, start=1):
            raw_tier = row.get(tier_key)
            raw_price = row.get(price_key)

            # 1. Validate Tier Name
            norm_tier = self.normalize_tier_name(raw_tier)
            if not norm_tier:
                report.rejected.append(
                    RejectedEntry(
                        row_number=idx,
                        raw_tier=raw_tier,
                        raw_price=raw_price,
                        reason="Missing or blank seat tier name"
                    )
                )
                continue

            # 2. Parse & Validate Price
            cleaned_price, err = self.parse_price(raw_price)
            if err or cleaned_price is None:
                report.rejected.append(
                    RejectedEntry(
                        row_number=idx,
                        raw_tier=raw_tier,
                        raw_price=raw_price,
                        reason=err or "Invalid price"
                    )
                )
                continue

            entry = CleanedPriceEntry(
                tier=norm_tier,
                price=cleaned_price,
                price_formatted=f"₹{cleaned_price:.2f}",
                original_raw_tier=str(raw_tier),
                original_raw_price=str(raw_price)
            )

            # 3. Check for Duplicate Tier Name
            if norm_tier in tier_map:
                prev_idx = tier_map[norm_tier]
                old_entry = report.imported[prev_idx]
                
                # Log de-duplication action
                report.deduplicated.append(
                    DeduplicatedEntry(
                        tier=norm_tier,
                        previous_price=old_entry.price,
                        new_price=cleaned_price,
                        resolution=f"Overwrote previous price ₹{old_entry.price:.2f} with newer price ₹{cleaned_price:.2f}",
                        raw_row=row
                    )
                )
                # Update with latest valid price
                report.imported[prev_idx] = entry
            else:
                tier_map[norm_tier] = len(report.imported)
                report.imported.append(entry)

        return report

    def import_from_csv_text(self, csv_content: str) -> PriceListImportReport:
        """Parses CSV string with header detection and sanitizes."""
        import csv
        import io

        f = io.StringIO(csv_content.strip())
        reader = csv.reader(f)
        rows = list(reader)
        if not rows:
            return PriceListImportReport(total_records_processed=0)

        # Detect headers or fallback to col 0 = tier, col 1 = price
        first_row = [c.strip().lower() for c in rows[0]]
        has_header = any("tier" in c or "seat" in c or "class" in c or "name" in c for c in first_row)
        
        tier_col = 0
        price_col = 1

        data_rows = rows
        if has_header:
            data_rows = rows[1:]
            for i, col in enumerate(first_row):
                if any(k in col for k in ("tier", "seat", "class", "name")):
                    tier_col = i
                elif any(k in col for k in ("price", "rate", "cost", "amount")):
                    price_col = i

        raw_entries = []
        for r in data_rows:
            if not r or all(c.strip() == "" for c in r):
                continue
            raw_t = r[tier_col] if len(r) > tier_col else None
            raw_p = r[price_col] if len(r) > price_col else None
            raw_entries.append({"tier": raw_t, "price": raw_p})

        return self.import_and_clean(raw_entries)
