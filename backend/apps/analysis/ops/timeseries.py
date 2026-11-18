"""Time-series statistics shared by analyses (trend tests)."""
import math

import numpy as np


def sens_slope(t, y):
    """Sen's slope (per unit of t) and the Mann-Kendall two-sided p-value; (None, None) with fewer than 3 values."""
    t, y = np.asarray(t, float), np.asarray(y, float)
    ok = np.isfinite(y)
    t, y = t[ok], y[ok]
    n = len(y)
    if n < 3:
        return None, None
    slopes = [(y[j] - y[i]) / (t[j] - t[i]) for i in range(n) for j in range(i + 1, n) if t[j] != t[i]]
    slope = float(np.median(slopes)) if slopes else None
    s = sum(np.sign(y[j] - y[i]) for i in range(n) for j in range(i + 1, n))
    var = n * (n - 1) * (2 * n + 5) / 18
    z = (s - np.sign(s)) / math.sqrt(var) if s != 0 else 0.0
    p = math.erfc(abs(z) / math.sqrt(2))
    return slope, p
