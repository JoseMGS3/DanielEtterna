"""Opt-in debug console and log for DanielEtterna 2.0 development.

Start with run_debug.bat, the debug .exe, or --debug. The regular GUI
remains quiet; debug.log in the user config folder is reset per session.
No background network access and no chart contents are written to disk.
"""
import os
from pathlib import Path
import sys
import threading
import time
import traceback
from collections import OrderedDict

import chart_loader


enabled = (
    "--debug" in sys.argv
    or os.environ.get("DANIEL_DEBUG", "").strip().lower() in ("1", "true", "yes")
    or Path(sys.argv[0]).stem.casefold().endswith("-debug")
)
_log_path = None
_io_lock = threading.Lock()
_ratings = OrderedDict()
_MAX_RATING_SNAPSHOTS = 24


def configure(config_dir):
    """Start a new, local debug session, if opted in."""
    global _log_path
    if not enabled:
        return
    try:
        folder = Path(config_dir)
        folder.mkdir(parents=True, exist_ok=True)
        _log_path = folder / "debug.log"
        with _io_lock:
            _log_path.write_text(
                "DanielEtterna debug session — " + time.strftime("%Y-%m-%d %H:%M:%S")
                + "\nTimes: local; ratings: different Legacy/XDC1 scales\n",
                encoding="utf-8",
            )
    except OSError:
        _log_path = None
    emit("[Debug] Enabled; log: " + (str(_log_path) if _log_path else "console only"))


def emit(message):
    """Write a structured line/block to console and optional local file."""
    if not enabled:
        return
    stamp = time.strftime("%H:%M:%S")
    value = f"[{stamp}] {message}"
    with _io_lock:
        if sys.stdout is not None:
            try:
                print(value, file=sys.stdout, flush=True)
            except (OSError, UnicodeError):
                pass
        if _log_path is not None:
            try:
                with _log_path.open("a", encoding="utf-8") as stream:
                    stream.write(value + "\n")
            except OSError:
                pass


def count_chart_notes(data, selected_chart=None):
    """Count playable taps, hold heads and roll heads for one 4K chart.

    .osu has taps and holds, but no distinct StepMania roll encoding.
    StepMania notes are counted by head symbols 1 / 2 / 4; hold tails
    and non-playable mine/lift/fake symbols are not extra presses.
    """
    if data.get("format") == "osu":
        notes = data.get("normalized_notes") or ()
        counts = {
            "taps": sum(tail == -1 for _, _, tail in notes),
            "holds": sum(tail != -1 for _, _, tail in notes),
            "rolls": 0,
        }
    elif data.get("format") in ("sm", "ssc"):
        if selected_chart is None:
            raise ValueError("Selected SM/SSC chart required for diagnostics")
        counts = {"taps": 0, "holds": 0, "rolls": 0}
        for _, row in chart_loader._parse_sm_rows(selected_chart["note_data"]):
            if len(row) != 4:
                raise ValueError("Only 4K charts can be counted")
            counts["taps"] += row.upper().count("1")
            counts["holds"] += row.upper().count("2")
            counts["rolls"] += row.upper().count("4")
    else:
        raise ValueError("Unsupported chart format for diagnostics")
    counts["total"] = sum(counts.values())
    return counts


def bridge_health(*, connection, chart_rate, now, menu_time=0.0,
                  menu_rate=1.0, menu_received=0.0,
                  gameplay_time=0.0, gameplay_rate=1.0,
                  gameplay_received=0.0, gameplay_active=False,
                  graph_start=None, graph_end=None):
    """Describe bridge freshness and rate alignment, NOT visual sync.

    Etterna's original song clock is divided by the playback rate
    before comparing with the rated graph. This checks *only* metadata
    consistency; visual synchronization needs a manual in-game check.
    """
    def age(received):
        return max(0.0, now - received) if received > 0 else None

    gp_age = age(gameplay_received)
    mn_age = age(menu_received)
    if gameplay_active and gp_age is not None and gp_age < 0.4:
        source, sample_age, music, rate = (
            "Gameplay", gp_age, gameplay_time, gameplay_rate
        )
    elif mn_age is not None and mn_age < 0.4:
        source, sample_age, music, rate = (
            "Menu/Preview", mn_age, menu_time, menu_rate
        )
    else:
        source, sample_age, music, rate = "No fresh sample", None, None, None

    position = None
    if rate is not None and rate > 0:
        position = music / rate + sample_age * 1000.0
    if connection != "ready":
        status = "Disconnected / waiting for chart"
    elif rate is None:
        status = "Waiting for fresh bridge clock"
    elif abs(chart_rate - rate) > 0.005:
        status = "RATE MISMATCH (inspect bridge/selected chart)"
    else:
        status = "Rate aligned (visual synchronization NOT verified)"
    return {
        "connection": connection,
        "source": source,
        "age_ms": round(sample_age * 1000, 1) if sample_age is not None else None,
        "rate": rate,
        "chart_rate": chart_rate,
        "cursor_ms": round(position, 1) if position is not None else None,
        "graph_start": graph_start,
        "graph_end": graph_end,
        "clock_status": status,
    }


def _bridge_text(bridge):
    def maybe_num(value):
        return "N/A" if value is None else str(value)
    return (
        f"Connection: {bridge['connection']} | Source: {bridge['source']}\n"
        f"  Age: {maybe_num(bridge['age_ms'])} ms"
        f" | Bridge rate: {maybe_num(bridge['rate'])}x"
        f" | Selected rate: {bridge['chart_rate']}x\n"
        f"  Cursor: {maybe_num(bridge['cursor_ms'])} ms"
        f" | Graph: {maybe_num(bridge['graph_start'])}.."
        f"{maybe_num(bridge['graph_end'])} ms\n"
        f"  Clock: {bridge['clock_status']}"
    )


def report_calculation(*, engine, path, difficulty, rate, note_counts,
                       rating, calc_ms, total_ms, graph_points,
                       bridge, rice=None, skillsets=None, status="Ready"):
    if not enabled:
        return
    unit = "Dan" if engine == "XDC1" else "Legacy SR (stars)"
    rice_line = (
        f" | Rice: {rice:.3f} Dan"
        if engine == "XDC1" and rice is not None else ""
    )
    names = ", ".join(skillsets) if skillsets else "N/A"
    emit(
        "[DanielEtterna Debug]\n"
        f"  Engine: {engine} | Status: {status}\n"
        "[Chart]\n"
        f"  File: {Path(path).name} | Difficulty: {difficulty}"
        f" | Rate: {rate:g}x | Keys: 4\n"
        "[Notes]\n"
        f"  Taps: {note_counts['taps']} | Holds: {note_counts['holds']}"
        f" | Rolls: {note_counts['rolls']}"
        f" | Total heads: {note_counts['total']}\n"
        "[Calculation]\n"
        f"  Rating: {rating:.3f} {unit}{rice_line}\n"
        f"  Engine time: {calc_ms:.1f} ms"
        f" | Total parse + calculation: {total_ms:.1f} ms"
        f" | Graph points: {graph_points}\n"
        f"  Top skillsets: {names}\n"
        "[Bridge]\n  " + _bridge_text(bridge)
    )


def report_bridge(bridge):
    if enabled:
        emit("[Bridge Monitor]\n  " + _bridge_text(bridge))


def report_error(error, *, engine, path, total_ms=None):
    if not enabled:
        return
    elapsed = f" | Elapsed: {total_ms:.1f} ms" if total_ms is not None else ""
    emit(
        f"[Calculation ERROR] Engine: {engine}"
        f" | Chart: {Path(path).name}{elapsed}\n"
        f"  {type(error).__name__}: {error}\n"
        + traceback.format_exc().rstrip()
    )


def remember_engine_rating(chart_key, engine, rating, label):
    """Compare only when user has visited both engines at the same rate.

    No second engine is run automatically; labels/units are distinct and
    raw rating differences are intentionally NOT computed.
    """
    if not enabled or engine not in ("Legacy", "XDC1"):
        return
    record = _ratings.setdefault(chart_key, {})
    record[engine] = (rating, label)
    _ratings.move_to_end(chart_key)
    while len(_ratings) > _MAX_RATING_SNAPSHOTS:
        _ratings.popitem(last=False)
    if "Legacy" in record and "XDC1" in record:
        legacy_rating, legacy_label = record["Legacy"]
        xdc_rating, xdc_label = record["XDC1"]
        emit(
            "[Engine Comparison — same chart and rate]\n"
            f"  Legacy: {legacy_rating:.3f} SR | {legacy_label}\n"
            f"  XDC1: {xdc_rating:.3f} Dan | {xdc_label}\n"
            "  These ratings use different scales; do not subtract them."
        )
