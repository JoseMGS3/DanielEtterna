"""Etterna -> XDC1 calculation pipeline (separate from the GUI).

StepMania charts are selected by the existing bridge metadata before
entering this module. This module never reads bridge files, starts threads,
or creates Tk objects; the caller controls publication of computed results.
"""
import math

import numpy as np

import algorithm
import chart_loader
import xdc1_adapter


XDC1_SKILLSETS = (
    "stream", "jumpstream", "handstream", "speedjack",
    "chordjack", "technical", "release",
)
XDC1_RELEVANCE_FRACTION = 0.20



def normalize_bridge_rate(raw):
    """Return a safe rate for both engines when a Lua bridge is incomplete."""
    try:
        rate = float(raw)
    except (TypeError, ValueError, OverflowError):
        return 1.0
    return rate if math.isfinite(rate) and rate > 0 else 1.0


def is_4k_stepstype(value):
    """Accept the 4K StepMania dance-single type emitted by Etterna.

    Older Lua bridges omit stepstype; an empty value remains compatible.
    All explicit non-4K StepTypes are rejected to avoid calculating
    another chart with a coincidentally matching difficulty and meter.
    """
    if not value:
        return True
    value = str(value).strip().lower()
    if value.startswith("stepstype_"):
        value = value[len("stepstype_"):]
    return value.replace("_", "-") == "dance-single"


def select_stepmania_chart(data, difficulty, meter, description="",
                           stepstype=""):
    """Match Etterna's selected StepMania chart without guessing.

    The bridge supplies a StepType, difficulty, meter and description.
    Multiple charts often share difficulty/meter in .ssc files; require
    an unambiguous description match rather than calculating the wrong
    chart. A single matching chart can retain the original behavior
    even if the bridge's description format differs.
    """
    if not is_4k_stepstype(stepstype):
        return None

    target_diff = str(difficulty or "").strip().lower()
    if target_diff.startswith("difficulty_"):
        target_diff = target_diff[len("difficulty_"):]
    target_description = str(description or "").strip().lower()

    try:
        target_meter = int(float(meter))
    except (ValueError, TypeError, OverflowError):
        target_meter = None

    matches = []
    for chart in data.get("charts") or []:
        if not chart.get("stepstype") or not is_4k_stepstype(
            chart["stepstype"]
        ):
            continue
        chart_diff = str(chart.get("difficulty", "")).strip().lower()
        if chart_diff != target_diff:
            continue
        try:
            chart_meter = int(float(chart.get("meter", "")))
        except (ValueError, TypeError, OverflowError):
            chart_meter = None
        if target_meter is not None and chart_meter != target_meter:
            continue
        matches.append(chart)

    if len(matches) > 1 and target_description:
        exact = [
            chart for chart in matches
            if str(chart.get("description", "")).strip().lower()
            == target_description
        ]
        if len(exact) == 1:
            return exact[0]
    return matches[0] if len(matches) == 1 else None


def chart_position_ms(music_ms, rate, elapsed_seconds=0.0):
    """Map Etterna's original song clock onto a rate-adjusted graph.

    The menu/gameplay Lua bridges write song seconds (not wall time).
    XDC1 receives note timestamps divided by rate. Therefore both
    clocks must use (song_ms / rate). Only the extrapolation since
    the most recent bridge sample advances at 1x real time.
    """
    values = (music_ms, rate, elapsed_seconds)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and math.isfinite(v) for v in values):
        raise ValueError("Non-finite Etterna playback data")
    if rate <= 0:
        raise ValueError("Etterna playback rate must be positive")
    return music_ms / rate + max(0.0, elapsed_seconds) * 1000.0


def relevant_xdc1_skillsets(overall_raw, skillsets_raw):
    """Match original Daniel 2.x: top skillset plus near-overall peers.

    Values here are XDC1 raw values, *not* Etterna native MSD or
    calibrated Dan display values. Always include the highest positive
    skillset; include up to two more if within 20% of overall.
    """
    if not math.isfinite(overall_raw) or overall_raw < 0:
        raise ValueError("Invalid XDC1 raw rating")
    if set(skillsets_raw) != set(XDC1_SKILLSETS):
        raise ValueError("XDC1 must supply the seven known skillsets")
    ranked = sorted(
        ((name, float(value)) for name, value in skillsets_raw.items()
         if math.isfinite(float(value)) and value > 0),
        key=lambda item: item[1],
        reverse=True,
    )
    limit = overall_raw * XDC1_RELEVANCE_FRACTION
    return [
        item for i, item in enumerate(ranked)
        if i == 0 or overall_raw - item[1] <= limit
    ][:3]


def remap_xdc1_columns(notes, column_layout="standard"):
    """Choose XDC1's hand grouping without changing the physical chart.

    The engine always treats internal columns 0-1 and 2-3 as two hands.
    WASD only exchanges physical columns 2 and 3 (one-based indices),
    keeping timing, LN tails and every scoring coefficient unchanged.
    """
    if column_layout not in ("standard", "wasd"):
        raise ValueError("Unknown XDC1 column layout: " + str(column_layout))
    if column_layout == "standard":
        return list(notes)
    swapped = (0, 2, 1, 3)
    return sorted(
        ((swapped[column], head, tail) for column, head, tail in notes),
        key=lambda note: (note[1], note[0]),
    )


def analyze_etterna_chart(data, selected_chart=None, *, rate=1.0,
                          include_long_notes=True, executable=None,
                          column_layout="standard"):
    """Calculate a selected Etterna 4K chart with XDC1.

    Rate is taken from the bridge snapshot and applied to both LN ends
    and tap heads. All graph timestamps are in this same rated time
    domain; the GUI must use chart_position_ms() to position its cursor.

    Return the data the existing GUI needs without changing Legacy.
    """
    notes = chart_loader.normalize_chart_notes(data, selected_chart)
    rated_notes = chart_loader.rate_normalized_notes(
        notes, rate=rate, include_long_notes=include_long_notes,
    )
    rated_notes = remap_xdc1_columns(rated_notes, column_layout)
    result = xdc1_adapter.analyze_notes(
        rated_notes, executable=executable,
    )
    times = np.asarray(result["grid"], dtype=float)
    strain = np.asarray(result["strain_rested"], dtype=float)
    if len(times) < 2 or times.shape != strain.shape:
        raise ValueError("XDC1 graph times and strain are incompatible")

    # The smoothing used by the upstream Daniel 2.x display is also
    # applied here. Leave XDC1 rating and skillsets untouched.
    note_heads = [(column, head) for column, head, _ in rated_notes]
    enveloped = algorithm._apply_proximity_envelope(
        times, strain, note_heads,
    )
    graph_strain = algorithm.smooth_D_for_graph(
        times, enveloped, note_heads,
    )
    if not np.all(np.isfinite(graph_strain)):
        raise ValueError("XDC1 graph contains invalid strain values")

    skills_raw = result["skillsets_raw"]
    return {
        "rating": result["rating"],
        "rating_rice": result["rating_rice"],
        "times": times,
        "strain": graph_strain,
        "skillsets_raw": {
            "overall": result["rating_raw"], **skills_raw,
        },
        "top_skillsets": relevant_xdc1_skillsets(
            result["rating_raw"], skills_raw,
        ),
        "details": result,
    }
