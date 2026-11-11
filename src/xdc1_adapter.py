"""Python subprocess adapter for the upstream XDC1 4K engine.

This module is deliberately independent of DanielEtterna's current
Sunny calculator and GUI. Input notes are normalized (column, head_ms,
tail_ms), with tail=-1 for taps. The underlying XDC1 program reads one
space-separated row per note on stdin and emits JSON with --graph.

XDC1 by TheBagelOfMan (MIT): see xdc1/LICENSE.
"""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import dan_scale


def resolve_xdc1_binary(executable=None):
    """Find the native XDC1 executable in source and PyInstaller layouts."""
    explicit = executable if executable is not None else os.environ.get("XDC1_BIN_PATH")
    if explicit:
        target = Path(explicit).expanduser()
        if not target.is_file():
            raise FileNotFoundError(f"XDC1 executable not found: {target}")
        return target

    binary_name = "xdc1.exe" if os.name == "nt" else "xdc1"
    source_root = Path(__file__).resolve().parent
    directories = []
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        directories.extend((Path(bundled), Path(bundled) / "src"))
    directories.extend((source_root, source_root.parent / "build"))
    for folder in directories:
        target = folder / binary_name
        if target.is_file():
            return target
    raise FileNotFoundError(
        "XDC1 is not compiled. Build xdc1/xdc1.cpp to src/"
        + binary_name
        + " or set XDC1_BIN_PATH to a compatible native executable."
    )


def _prepare_input(notes, *, time_origin="absolute"):
    """Validate XDC1 input and set its time origin.

    The default preserves Daniel's zero-anchored grid, shifting only
    negative heads. In first_note mode, the earliest note becomes 0 ms
    so arbitrary song lead-in/sync offsets cannot change the 25-ms grid
    phase. Return (stdin text, shift_ms); restore graph times afterward.
    """
    normalized = []
    for entry in notes:
        if len(entry) != 3:
            raise ValueError("Every note must have (column, head_ms, tail_ms)")
        col, head, tail = entry
        if any(type(x) is not int for x in (col, head, tail)):
            raise ValueError("XDC1 requires integer columns and milliseconds")
        if col not in (0, 1, 2, 3):
            raise ValueError(f"XDC1 supports only four columns, got {col}")
        if tail != -1 and tail < head:
            raise ValueError("Long-note end precedes its head")
        normalized.append((col, head, tail))
    if len(normalized) < 2:
        raise ValueError("At least two notes are required for XDC1")
    if time_origin not in ("absolute", "first_note"):
        raise ValueError("Unknown XDC1 time origin: " + str(time_origin))
    normalized.sort(key=lambda n: (n[1], n[0]))
    offset = (-normalized[0][1] if time_origin == "first_note"
              else max(0, -normalized[0][1]))
    rows = [
        f"{col} {head + offset} {tail + offset if tail != -1 else -1}"
        for col, head, tail in normalized
    ]
    return "\n".join(rows) + "\n", offset


def _read_nonnegative_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid XDC1 {field}: expected number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Invalid XDC1 {field}: nonfinite or negative")
    return number


def analyze_notes(notes, *, executable=None, timeout=45,
                  time_origin="absolute"):
    """Calculate Dan, seven skillsets, and strain directly from XDC1.

    Input timestamps are already playback-rate adjusted. For SM/SSC,
    use chart_loader.normalize_chart_notes(...), then
    chart_loader.rate_normalized_notes(...).

    Returns a dictionary with both calibrated Dan values and raw
    engine outputs. XDC1's graph includes no stamina strain, matching
    upstream Daniel 2.x's graph presentation.
    """
    payload, offset = _prepare_input(notes, time_origin=time_origin)
    binary = resolve_xdc1_binary(executable)
    command = [str(binary), "--graph"]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

    subprocess_started = time.perf_counter()
    result = subprocess.run(
        command,
        input=payload,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        creationflags=flags,
    )
    subprocess_ms = (time.perf_counter() - subprocess_started) * 1000.0
    if result.returncode:
        raise RuntimeError(
            f"XDC1 failed (exit {result.returncode}): "
            f"{result.stderr.strip()[:600]}"
        )
    try:
        output = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("XDC1 did not produce valid JSON") from exc
    if not isinstance(output, dict):
        raise ValueError("XDC1 JSON result must be an object")

    rating_points = _read_nonnegative_number(output["rating"], "rating")
    rice_points = _read_nonnegative_number(output["rating_rice"], "rating_rice")
    raw_skills = output["skillsets"]
    if not isinstance(raw_skills, dict) or len(raw_skills) != 7:
        raise ValueError("XDC1 must report exactly seven skillsets")
    skill_points = {
        name: _read_nonnegative_number(value, "skillset")
        for name, value in raw_skills.items()
        if isinstance(name, str)
    }
    if len(skill_points) != 7:
        raise ValueError("Invalid XDC1 skillset names")

    grid = output["grid"]
    graph = output["graph"]
    if not isinstance(grid, list) or not isinstance(graph, list):
        raise ValueError("XDC1 grid and graph must be lists")
    if len(grid) != len(graph) or len(grid) < 2:
        raise ValueError("XDC1 returned incompatible graph arrays")
    grid_ms = [float(value) - offset for value in grid]
    if not all(math.isfinite(t) for t in grid_ms):
        raise ValueError("XDC1 returned invalid time coordinates")
    if any(a > b for a, b in zip(grid_ms, grid_ms[1:])):
        raise ValueError("XDC1 returned an unsorted time grid")
    graph_points = [_read_nonnegative_number(p, "graph") for p in graph]

    raw = dan_scale.points_to_raw(rating_points)
    raw_rice = dan_scale.points_to_raw(rice_points)
    skill_raw = {
        name: dan_scale.points_to_raw(p)
        for name, p in skill_points.items()
    }
    strain = [
        dan_scale.points_to_raw(p) / dan_scale.STRAIN_TO_RAW
        for p in graph_points
    ]
    return {
        "subprocess_ms": subprocess_ms,
        "rating": dan_scale.to_dan(raw),
        "rating_rice": dan_scale.to_dan(raw_rice),
        "rating_points": rating_points,
        "rating_rice_points": rice_points,
        "rating_raw": raw,
        "rice": dan_scale.to_dan(raw_rice),
        "skillsets": {
            name: dan_scale.to_dan(raw_value)
            for name, raw_value in skill_raw.items()
        },
        "skillsets_raw": skill_raw,
        "skillsets_points": skill_points,
        "grid": grid_ms,
        "graph_points": graph_points,
        "strain_rested": strain,
    }


def analyze_chart(data, chart=None, *, rate=1.0, include_long_notes=True,
                  executable=None, timeout=45, time_origin="absolute"):
    """Convenience entry point for the new 2.0 chart-loader API.

    Does not change the old application calculation loop. Negative song
    times are kept so the adapter can shift them before invoking XDC1.
    """
    import chart_loader

    notes = chart_loader.normalize_chart_notes(data, chart)
    rated_notes = chart_loader.rate_normalized_notes(
        notes, rate=rate, include_long_notes=include_long_notes
    )
    return analyze_notes(rated_notes, executable=executable, timeout=timeout,
                         time_origin=time_origin)
