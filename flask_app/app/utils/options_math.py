"""
Options Math Utilities
======================
Black-Scholes based probability calculations for options analysis.

Functions:
- calculate_probability_of_profit: PoP using Black-Scholes d2
"""

import math

# Risk-free rate assumption
RISK_FREE_RATE = 0.05


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using math.erf (no scipy dependency)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def calculate_probability_of_profit(
    current_price: float,
    strike: float,
    iv: float,
    days_to_expiry: int,
    option_type: str,
) -> float:
    """
    Calculate probability of profit for an option using Black-Scholes d2.

    For calls:  P(profit) = 1 - N(d2)   (probability stock finishes above strike)
    For puts:   P(profit) = N(-d2)       (probability stock finishes below strike)

    where d2 = (ln(S/K) + (r - sigma^2/2) * T) / (sigma * sqrt(T))

    Args:
        current_price: Current stock price (S)
        strike: Option strike price (K)
        iv: Implied volatility as a decimal (e.g. 0.30 for 30%)
        days_to_expiry: Calendar days until expiration
        option_type: 'call' or 'put'

    Returns:
        Probability of profit as float 0-1. Returns 0.0 on invalid inputs.
    """
    if current_price <= 0 or strike <= 0 or iv <= 0 or days_to_expiry <= 0:
        return 0.0

    T = days_to_expiry / 365.0
    r = RISK_FREE_RATE
    sigma = iv

    try:
        d2 = (math.log(current_price / strike) + (r - sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    except (ValueError, ZeroDivisionError):
        return 0.0

    if option_type.lower() == 'call':
        return 1.0 - _norm_cdf(d2)
    else:
        return _norm_cdf(-d2)
