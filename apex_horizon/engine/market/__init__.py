"""The market — Design Bible Volume 4.

A continuously simulated financial system that operates independently of the
player (V4.2, V4.10). Companies rise and fall whether or not the player invests,
and every price movement is traceable to a believable cause (V4.4, V4.21).
"""

from .listing import MarketListing, PriceChange
from .market import MarketSystem
from .pricing import MINIMUM_PRICE, PricingWeights, apply_change, compute_change

__all__ = [
    "MINIMUM_PRICE",
    "MarketListing",
    "MarketSystem",
    "PriceChange",
    "PricingWeights",
    "apply_change",
    "compute_change",
]
