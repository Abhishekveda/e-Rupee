"""
speed_agent.py
--------------
Speed and Route Optimization Agent for e₹ Bridge.

This agent answers two questions:
  1. What is the fastest, cheapest corridor for this transfer?
  2. What is the optimal time to send money based on FX patterns?

Routing logic:
  - CBDC direct (e₹-R to CBUAE digital dirham): fastest, only for UAE
  - SRVA route (via Special Rupee Vostro Account): for SRVA-enabled corridors
  - Multi-hop (source currency → INR → destination): universal fallback
  - SWIFT: shown only as the comparison baseline, never recommended

In production, the FX timing recommendation would use a real-time
data feed. In the PoC, it uses a deterministic rule based on time of day
and day of week (genuine patterns that apply to INR/AED and INR/SGD).
"""

from datetime import datetime, timezone
from typing import Optional


# Corridors with CBDC or SRVA support
CBDC_CORRIDORS = {("IN", "AE"), ("IN", "SG")}
SRVA_CORRIDORS = {
    ("IN", "AE"), ("CA", "AE"), ("US", "AE"),
    ("IN", "SG"), ("IN", "RU"), ("IN", "SA"), ("IN", "MY"),
}

# Settlement time estimates (seconds)
ROUTE_TIMES = {
    "cbdc_direct": 3,
    "srva": 12,
    "multi_hop": 30,
    "swift": 259200,  # 3 days
}

# Fee estimates (% of transfer)
ROUTE_FEES = {
    "cbdc_direct": 0.002,
    "srva": 0.003,
    "multi_hop": 0.004,
    "swift": 0.063,
}


class SpeedAgent:
    """Recommends the optimal payment route and timing."""

    def recommend_route(
        self,
        source_country: str,
        dest_country: str,
        amount_inr: float,
        urgency: str = "normal",  # "urgent" | "normal" | "economy"
    ) -> dict:
        """
        Recommend the best payment route for a given corridor.

        Args:
            source_country: ISO country code (e.g., "IN", "CA", "US")
            dest_country:   ISO country code (e.g., "AE", "SG", "RU")
            amount_inr:     Transfer amount in INR
            urgency:        "urgent" (fastest), "normal", or "economy" (cheapest)
        """
        pair = (source_country.upper(), dest_country.upper())

        # Determine available routes
        routes = []

        if pair in CBDC_CORRIDORS:
            routes.append({
                "route": "cbdc_direct",
                "label": "e-Rupee CBDC Direct",
                "description": "e₹-R direct to CBDC recipient. Fastest available.",
                "settlement_time_sec": ROUTE_TIMES["cbdc_direct"],
                "fee_pct": ROUTE_FEES["cbdc_direct"] * 100,
                "fee_inr": round(amount_inr * ROUTE_FEES["cbdc_direct"], 2),
                "available": True,
                "recommended_for": ["urgent", "normal", "economy"],
            })

        if pair in SRVA_CORRIDORS:
            routes.append({
                "route": "srva",
                "label": "SRVA (Special Rupee Vostro Account)",
                "description": "Settled via INR Vostro account. No USD required.",
                "settlement_time_sec": ROUTE_TIMES["srva"],
                "fee_pct": ROUTE_FEES["srva"] * 100,
                "fee_inr": round(amount_inr * ROUTE_FEES["srva"], 2),
                "available": True,
                "recommended_for": ["normal", "economy"],
            })

        # Multi-hop is always available
        routes.append({
            "route": "multi_hop",
            "label": "INR Bridge (Multi-hop)",
            "description": f"{source_country} currency → INR → {dest_country} currency. Dollar-free.",
            "settlement_time_sec": ROUTE_TIMES["multi_hop"],
            "fee_pct": ROUTE_FEES["multi_hop"] * 100,
            "fee_inr": round(amount_inr * ROUTE_FEES["multi_hop"], 2),
            "available": True,
            "recommended_for": ["economy"],
        })

        # SWIFT for comparison only
        swift = {
            "route": "swift",
            "label": "SWIFT (for reference only)",
            "description": "Traditional correspondent banking. Not recommended.",
            "settlement_time_sec": ROUTE_TIMES["swift"],
            "fee_pct": ROUTE_FEES["swift"] * 100,
            "fee_inr": round(amount_inr * ROUTE_FEES["swift"], 2),
            "available": False,  # false = we don't offer this, shown for comparison
            "recommended_for": [],
        }

        # Select optimal route based on urgency
        if urgency == "urgent":
            optimal = routes[0]  # fastest
        elif urgency == "economy":
            optimal = min(routes, key=lambda r: r["fee_inr"])
        else:
            # Normal: prefer CBDC if available, else SRVA, else multi-hop
            optimal = routes[0]

        savings_vs_swift = round(swift["fee_inr"] - optimal["fee_inr"], 2)

        return {
            "recommended_route": optimal,
            "available_routes": routes,
            "swift_comparison": swift,
            "savings_vs_swift_inr": savings_vs_swift,
            "savings_pct": round((savings_vs_swift / swift["fee_inr"]) * 100, 1) if swift["fee_inr"] > 0 else 0,
            "dollar_used": False,
            "corridor": f"{source_country} → INR → {dest_country}",
            "agent": "e₹ Speed Optimization Agent v1.0",
        }

    def recommend_timing(
        self,
        source_currency: str,
        dest_currency: str,
    ) -> dict:
        """
        Recommend the optimal time to send money based on FX patterns.

        INR/AED and INR/SGD are relatively stable intraday, but there are
        genuine patterns:
        - FX spreads are tighter during Indian banking hours (9:30–17:30 IST)
        - Monday and Tuesday mornings IST tend to have better rates
          (post-weekend institutional rebalancing)
        - Friday afternoons are slightly less favourable (weekend risk premium)
        """
        now_utc = datetime.now(timezone.utc)
        hour_ist = (now_utc.hour + 5) % 24 + (1 if now_utc.minute >= 30 else 0)
        weekday = now_utc.weekday()  # 0 = Monday

        # Assess current window
        in_banking_hours = 9 <= hour_ist <= 17
        is_monday_tuesday = weekday in (0, 1)
        is_friday_afternoon = weekday == 4 and hour_ist >= 14
        is_weekend = weekday in (5, 6)

        if is_weekend:
            recommendation = "wait"
            reason = "FX markets are closed or thin on weekends. Send on Monday morning IST for best rates."
        elif is_friday_afternoon:
            recommendation = "caution"
            reason = "Friday afternoon IST can carry a small weekend premium. Consider sending Monday morning instead."
        elif is_monday_tuesday and in_banking_hours:
            recommendation = "optimal"
            reason = "Monday and Tuesday mornings IST typically see the tightest FX spreads on INR pairs due to post-weekend institutional rebalancing."
        elif in_banking_hours:
            recommendation = "good"
            reason = "Indian banking hours (9:30–17:30 IST) offer better FX liquidity than off-hours."
        else:
            recommendation = "acceptable"
            reason = "Off-hours transfers are processed normally but FX spreads may be marginally wider."

        return {
            "recommendation": recommendation,  # optimal, good, acceptable, caution, wait
            "reason": reason,
            "current_ist_hour": hour_ist,
            "in_banking_hours": in_banking_hours,
            "best_windows": [
                "Monday 9:30–12:00 IST",
                "Tuesday 9:30–12:00 IST",
                "Wednesday 10:00–14:00 IST",
            ],
            "avoid": ["Friday after 14:00 IST", "Weekends", "Public holidays"],
            "note": "For small remittances (under ₹50,000), timing impact is less than ₹50. Urgency should override timing for time-sensitive transfers.",
            "agent": "e₹ Speed Optimization Agent v1.0",
        }
