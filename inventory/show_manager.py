"""
CinePay Inventory & Show Management Module
Provides thread-safe show scheduling, tier configuration, live capacity tracking,
and atomic reservation locks.
"""

import threading
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from pricing_engine.models import TierPriceConfig, BookingItem


class ShowTier:
    def __init__(self, name: str, base_price: Decimal, total_seats: int, booked_seats: int = 0):
        self.name = name
        self.base_price = Decimal(str(base_price))
        self.total_seats = int(total_seats)
        self.booked_seats = int(booked_seats)

    @property
    def available_seats(self) -> int:
        return max(0, self.total_seats - self.booked_seats)

    @property
    def is_sold_out(self) -> bool:
        return self.available_seats == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.name,
            "base_price": float(self.base_price),
            "base_price_formatted": f"₹{self.base_price:.2f}",
            "total_seats": self.total_seats,
            "booked_seats": self.booked_seats,
            "available_seats": self.available_seats,
            "is_sold_out": self.is_sold_out,
            "status": "SOLD OUT" if self.is_sold_out else f"{self.available_seats} left",
        }


class Show:
    def __init__(
        self,
        show_id: str,
        movie_title: str,
        screen_name: str,
        show_time: str,
        experience: str,
        tiers: Dict[str, ShowTier]
    ):
        self.show_id = show_id
        self.movie_title = movie_title
        self.screen_name = screen_name
        self.show_time = show_time
        self.experience = experience
        self.tiers = tiers

    def to_dict(self) -> Dict[str, Any]:
        return {
            "show_id": self.show_id,
            "movie_title": self.movie_title,
            "screen_name": self.screen_name,
            "show_time": self.show_time,
            "experience": self.experience,
            "tiers": {name: tier.to_dict() for name, tier in self.tiers.items()}
        }


class ShowManager:
    """Thread-safe catalog and inventory management for multiplex shows."""

    def __init__(self):
        self._lock = threading.Lock()
        self.shows: Dict[str, Show] = {}
        self.bookings: List[Dict[str, Any]] = []
        self._seed_default_shows()

    def _seed_default_shows(self):
        """Initializes default Friday night shows reflecting real cinema environments."""
        self.shows = {
            "SHOW-101": Show(
                show_id="SHOW-101",
                movie_title="Dune: Part Two",
                screen_name="Audi 1 (Dolby Atmos 4K)",
                show_time="07:15 PM (Friday Night)",
                experience="Dolby Atmos",
                tiers={
                    "Silver": ShowTier("Silver", Decimal("180.00"), total_seats=50, booked_seats=46), # 4 left
                    "Gold": ShowTier("Gold", Decimal("280.00"), total_seats=40, booked_seats=28),   # 12 left
                    "Recliner": ShowTier("Recliner", Decimal("480.00"), total_seats=12, booked_seats=12), # SOLD OUT!
                }
            ),
            "SHOW-102": Show(
                show_id="SHOW-102",
                movie_title="Interstellar (IMAX Special)",
                screen_name="Audi 2 (IMAX Laser)",
                show_time="09:45 PM (Prime Night)",
                experience="IMAX with Laser",
                tiers={
                    "Silver": ShowTier("Silver", Decimal("220.00"), total_seats=60, booked_seats=58), # 2 left
                    "Gold": ShowTier("Gold", Decimal("350.00"), total_seats=45, booked_seats=40),   # 5 left
                    "Recliner": ShowTier("Recliner", Decimal("600.00"), total_seats=16, booked_seats=14), # 2 left
                }
            ),
            "SHOW-103": Show(
                show_id="SHOW-103",
                movie_title="Oppenheimer",
                screen_name="Audi 3 (Prime 7.1)",
                show_time="10:30 PM (Late Night)",
                experience="7.1 Surround",
                tiers={
                    "Silver": ShowTier("Silver", Decimal("150.00"), total_seats=40, booked_seats=10), # 30 left
                    "Gold": ShowTier("Gold", Decimal("240.00"), total_seats=35, booked_seats=15),   # 20 left
                    "Recliner": ShowTier("Recliner", Decimal("420.00"), total_seats=10, booked_seats=4), # 6 left
                }
            ),
        }

    def reset_inventory(self):
        """Resets shows and bookings back to seed state."""
        with self._lock:
            self._seed_default_shows()
            self.bookings.clear()

    def get_all_shows(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [show.to_dict() for show in self.shows.values()]

    def get_show(self, show_id: str) -> Optional[Show]:
        with self._lock:
            return self.shows.get(show_id)

    def validate_and_reserve_seats(
        self,
        show_id: str,
        items: List[BookingItem]
    ) -> None:
        """
        Atomically validates seat availability and reserves them.
        Raises ValueError if show does not exist or seats are insufficient/sold out.
        """
        with self._lock:
            show = self.shows.get(show_id)
            if not show:
                raise ValueError(f"Show ID '{show_id}' not found.")

            # Pre-validation check across all requested tiers
            for item in items:
                if item.quantity <= 0:
                    continue
                tier = show.tiers.get(item.tier)
                if not tier:
                    raise ValueError(f"Tier '{item.tier}' is invalid for show {show.movie_title}.")
                
                if tier.is_sold_out:
                    raise ValueError(
                        f"Tier '{item.tier}' is completely SOLD OUT for {show.movie_title} ({show.show_time})."
                    )

                if item.quantity > tier.available_seats:
                    raise ValueError(
                        f"Cannot book {item.quantity} seats in '{item.tier}'. Only {tier.available_seats} seat(s) remaining."
                    )

            # Atomic commit: increment booked counts
            for item in items:
                if item.quantity > 0:
                    show.tiers[item.tier].booked_seats += item.quantity

    def record_booking(self, booking_data: Dict[str, Any]) -> str:
        """Saves completed booking in audit log and returns unique booking ID."""
        with self._lock:
            booking_id = f"CP-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            booking_data["booking_id"] = booking_id
            booking_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.bookings.insert(0, booking_data)
            return booking_id

    def get_booking(self, booking_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for b in self.bookings:
                if b["booking_id"] == booking_id:
                    return b
            return None

    def get_all_bookings(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.bookings)

    def update_tier_prices(
        self,
        cleaned_prices: Dict[str, Decimal],
        show_id: Optional[str] = None
    ) -> List[str]:
        """
        Updates base prices for tiers from cleaned price list import.
        Returns list of updated show titles.
        """
        updated_shows = []
        with self._lock:
            targets = [self.shows[show_id]] if (show_id and show_id in self.shows) else list(self.shows.values())
            for show in targets:
                for tier_name, price in cleaned_prices.items():
                    if tier_name in show.tiers:
                        show.tiers[tier_name].base_price = price
                    else:
                        # Add new tier dynamically to the screen with default 30 seats
                        show.tiers[tier_name] = ShowTier(
                            name=tier_name,
                            base_price=price,
                            total_seats=30,
                            booked_seats=0
                        )
                updated_shows.append(show.movie_title)
        return updated_shows

