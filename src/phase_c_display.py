"""Small display-only helpers for the engine-specific difficulty graph.

Keep renderer and Dan calculation independent: this file only labels the
source of the existing Full-layout curve and the active Etterna rate.
"""
import math

import i18n


def graph_caption(engine, rate, language="en"):
    """The source of the curve, not a new difficulty calculation."""
    key = "graph_xdc1_strain" if engine == "XDC1" else "graph_legacy_strain"
    try:
        rate = float(rate)
    except (ValueError, TypeError, OverflowError):
        rate = 1.0
    if not math.isfinite(rate) or rate <= 0:
        rate = 1.0
    return f"{i18n.t(key, language)} · {rate:g}x"
