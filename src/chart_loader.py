from pathlib import Path
import re

import osu_file_parser as osu_parser


# ============================================================
# UTILIDADES
# ============================================================

def _read_text(path):
    with open(
        path,
        "r",
        encoding="utf-8-sig",
        errors="ignore"
    ) as f:
        return f.read()


def _read_tag(text, tag):
    """
    Lee un tag StepMania/SSC:

        #OFFSET:-0.123;
        #BPMS:0.000=180.000;
        #NOTES: ... ;

    Devuelve:
        - None si el tag no existe.
        - "" si el tag existe pero está vacío.
        - El contenido (sin ;) en cualquier otro caso.
    """

    pattern = rf"#{re.escape(tag)}\s*:\s*(.*?);"

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None

    return match.group(1).strip()


def _parse_float(raw, default=0.0):
    if raw is None or raw == "":
        return default

    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_timing_pairs(raw):
    """
    Convierte:

        0.000=180.000,64.000=200.000

    en:

        [
            (0.0, 180.0),
            (64.0, 200.0)
        ]
    """

    if not raw:
        return []

    result = []

    for item in raw.split(","):
        item = item.strip()

        if not item or "=" not in item:
            continue

        left, right = item.split("=", 1)

        try:
            result.append(
                (
                    float(left.strip()),
                    float(right.strip())
                )
            )
        except ValueError:
            continue

    result.sort(key=lambda x: x[0])

    return result


# ============================================================
# .OSU
# ============================================================

def load_osu(path):
    """
    Usa exactamente el parser original de Daniel.
    """

    p_obj = osu_parser.parser(str(path))
    p_obj.process()

    p = p_obj.get_parsed_data()

    keycount = int(p[0])
    columns = p[1]
    times = p[2]
    od = p[5]

    notes = list(
        zip(columns, times)
    )

    return {
        "format": "osu",
        "keycount": keycount,
        "notes": notes,
        "od": od,
        "charts": None,
        "timing": None,
    }


# ============================================================
# FILAS STEPMania (.SM / .SSC)
# ============================================================

def _parse_sm_rows(note_data):
    """
    Convierte el bloque visual de notas en:

        [
            (beat, "1000"),
            (beat, "0100"),
            ...
        ]

    Igual que en .sm, cada bloque separado por coma representa
    4 beats de note rows. Esto también se usa para .ssc.
    """

    measures = note_data.split(",")

    rows = []

    measure_start_beat = 0.0

    for measure in measures:

        clean_lines = []

        for line in measure.splitlines():

            # Quitar comentarios //
            line = re.sub(
                r"//.*$",
                "",
                line
            ).strip()

            if not line:
                continue

            clean_lines.append(line)

        if not clean_lines:
            measure_start_beat += 4.0
            continue

        row_count = len(clean_lines)

        beat_step = 4.0 / row_count

        for i, row in enumerate(clean_lines):

            beat = (
                measure_start_beat
                + i * beat_step
            )

            rows.append(
                (beat, row)
            )

        measure_start_beat += 4.0

    return rows


def _sm_rows_to_notes(rows):
    """
    Daniel es rice-oriented.

    Se cuentan:
        1 = tap
        2 = inicio hold
        4 = inicio roll

    Se ignoran:
        0 = vacío
        3 = final de hold/roll
        M = mine
        L = lift
        F = fake

    Daniel actualmente solo trabaja con 4K.
    """

    notes = []

    ignored_symbols = {}

    for beat, row in rows:

        if len(row) != 4:
            continue

        for column, symbol in enumerate(row):

            if symbol in ("1", "2", "4"):

                notes.append(
                    (
                        column,
                        beat
                    )
                )

            elif symbol not in ("0", "3"):

                ignored_symbols[symbol] = (
                    ignored_symbols.get(symbol, 0)
                    + 1
                )

    return notes, ignored_symbols


# ============================================================
# TIMING STEPMania
# ============================================================

def _beat_to_seconds_without_stops(
    beat,
    bpms,
    offset
):
    """
    Calcula el tiempo base con cambios de BPM.

    Etterna/StepMania usan OFFSET de forma que beat 0 cae en
    -OFFSET segundos, por eso current_time comienza en -offset.
    """

    if not bpms:
        raise ValueError(
            "El simfile no contiene datos de BPM utilizables."
        )

    current_time = -offset
    current_beat = 0.0
    current_bpm = bpms[0][1]

    for change_beat, new_bpm in bpms:

        if change_beat <= 0:
            current_bpm = new_bpm
            continue

        # Para obtener el timestamp exacto de una fila ubicada
        # en change_beat, no hace falta integrar con el nuevo BPM
        # hasta después de ese beat.
        if change_beat >= beat:
            break

        beat_delta = (
            change_beat - current_beat
        )

        current_time += (
            beat_delta
            * 60.0
            / current_bpm
        )

        current_beat = change_beat
        current_bpm = new_bpm

    remaining_beats = (
        beat - current_beat
    )

    current_time += (
        remaining_beats
        * 60.0
        / current_bpm
    )

    return current_time


def _beat_to_seconds(
    beat,
    bpms,
    stops,
    delays,
    offset
):
    """
    BPM changes + STOPS + DELAYS.

    Semántica utilizada:
      - STOP en el mismo beat ocurre después de la fila, por eso
        solo desplaza beats posteriores: stop_beat < beat.
      - DELAY en el mismo beat ocurre antes de la fila, por eso
        desplaza esa fila y las posteriores: delay_beat <= beat.
    """

    seconds = (
        _beat_to_seconds_without_stops(
            beat,
            bpms,
            offset
        )
    )

    for stop_beat, duration in stops:

        if stop_beat < beat:
            seconds += duration

    for delay_beat, duration in delays:

        if delay_beat <= beat:
            seconds += duration

    return seconds


def _convert_stepmania_notes(
    note_data,
    bpms,
    stops,
    delays,
    warps,
    offset
):
    """
    Conversión compartida por .sm y .ssc.
    """

    # Por seguridad no aproximamos WARPS. Un warp cambia el mapeo
    # beat->tiempo y requiere eliminar/colapsar intervalos completos.
    if warps:
        raise NotImplementedError(
            "Este chart contiene #WARPS. "
            "El soporte .ssc ya funciona para timing normal, "
            "BPMs, STOPS y DELAYS, pero WARPS todavía no."
        )

    rows = _parse_sm_rows(
        note_data
    )

    beat_notes, ignored = (
        _sm_rows_to_notes(rows)
    )

    notes = []

    for column, beat in beat_notes:

        seconds = _beat_to_seconds(
            beat=beat,
            bpms=bpms,
            stops=stops,
            delays=delays,
            offset=offset
        )

        notes.append(
            (
                column,
                seconds * 1000.0
            )
        )

    notes.sort(
        key=lambda x: (
            x[1],
            x[0]
        )
    )

    return notes, ignored


# ============================================================
# .SM - CHARTS
# ============================================================

def _extract_sm_note_blocks(text):
    """
    Extrae todos los bloques #NOTES:...; de un .sm.
    """

    return re.findall(
        r"#NOTES\s*:\s*(.*?);",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )


def _parse_sm_chart(block, index):
    """
    Formato típico .sm:

    #NOTES:
         dance-single:
         descripcion:
         Challenge:
         20:
         0.000,0.000,0.000,0.000,0.000:
    1000
    0100
    ...
    ;
    """

    parts = block.split(":", 5)

    if len(parts) < 6:
        return None

    stepstype = parts[0].strip()
    description = parts[1].strip()
    difficulty = parts[2].strip()
    meter = parts[3].strip()
    radar = parts[4].strip()
    note_data = parts[5].strip()

    return {
        "index": index,
        "stepstype": stepstype,
        "description": description,
        "difficulty": difficulty,
        "meter": meter,
        "radar": radar,
        "note_data": note_data,
    }


# ============================================================
# CARGADOR .SM
# ============================================================

def load_sm(path):
    text = _read_text(path)

    offset = _parse_float(
        _read_tag(
            text,
            "OFFSET"
        ),
        0.0
    )

    bpms = _parse_timing_pairs(
        _read_tag(
            text,
            "BPMS"
        )
    )

    stops = _parse_timing_pairs(
        _read_tag(
            text,
            "STOPS"
        )
    )

    delays = _parse_timing_pairs(
        _read_tag(
            text,
            "DELAYS"
        )
    )

    warps = _parse_timing_pairs(
        _read_tag(
            text,
            "WARPS"
        )
    )

    blocks = (
        _extract_sm_note_blocks(
            text
        )
    )

    charts = []

    for i, block in enumerate(blocks):

        chart = _parse_sm_chart(
            block,
            i
        )

        if chart is not None:
            charts.append(chart)

    return {
        "format": "sm",
        "offset": offset,
        "bpms": bpms,
        "stops": stops,
        "delays": delays,
        "warps": warps,
        "charts": charts,
    }


def convert_sm_chart(data, chart):
    """
    Mantiene compatibilidad con el código anterior.
    """

    return _convert_stepmania_notes(
        note_data=chart["note_data"],
        bpms=data["bpms"],
        stops=data["stops"],
        delays=data["delays"],
        warps=data["warps"],
        offset=data["offset"]
    )


# ============================================================
# .SSC
# ============================================================

def _split_ssc(text):
    """
    Separa:
      - cabecera/global timing: antes del primer #NOTEDATA:;
      - un bloque por chart: desde #NOTEDATA:; hasta el siguiente.
    """

    matches = list(
        re.finditer(
            r"#NOTEDATA\s*:\s*;",
            text,
            flags=re.IGNORECASE
        )
    )

    if not matches:
        return text, []

    header = text[:matches[0].start()]

    blocks = []

    for i, match in enumerate(matches):

        start = match.end()

        end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(text)
        )

        blocks.append(
            text[start:end]
        )

    return header, blocks


def _chart_timing_pairs(
    block,
    header,
    tag
):
    """
    SSC permite split timing por chart.

    Si el tag aparece dentro del #NOTEDATA, ese valor gana.
    Si no aparece, se hereda el timing global de la canción.

    Importante:
      #STOPS:; cuenta como override explícito a lista vacía.
    """

    chart_raw = _read_tag(
        block,
        tag
    )

    if chart_raw is not None:
        return _parse_timing_pairs(
            chart_raw
        )

    return _parse_timing_pairs(
        _read_tag(
            header,
            tag
        )
    )


def _chart_offset(
    block,
    header
):
    chart_raw = _read_tag(
        block,
        "OFFSET"
    )

    if chart_raw is not None:
        return _parse_float(
            chart_raw,
            0.0
        )

    return _parse_float(
        _read_tag(
            header,
            "OFFSET"
        ),
        0.0
    )


def _parse_ssc_chart(
    block,
    header,
    index
):
    """
    Lee los metadatos y el timing efectivo de un #NOTEDATA.
    """

    stepstype = (
        _read_tag(
            block,
            "STEPSTYPE"
        )
        or ""
    ).strip()

    description = (
        _read_tag(
            block,
            "DESCRIPTION"
        )
        or ""
    ).strip()

    chartname = (
        _read_tag(
            block,
            "CHARTNAME"
        )
        or ""
    ).strip()

    # GetDescription() suele ser suficiente para seleccionar,
    # pero CHARTNAME es un fallback útil en SSC modernos.
    if not description:
        description = chartname

    difficulty = (
        _read_tag(
            block,
            "DIFFICULTY"
        )
        or ""
    ).strip()

    meter = (
        _read_tag(
            block,
            "METER"
        )
        or ""
    ).strip()

    radar = (
        _read_tag(
            block,
            "RADARVALUES"
        )
        or ""
    ).strip()

    note_data = _read_tag(
        block,
        "NOTES"
    )

    if note_data is None:
        return None

    bpms = _chart_timing_pairs(
        block,
        header,
        "BPMS"
    )

    stops = _chart_timing_pairs(
        block,
        header,
        "STOPS"
    )

    delays = _chart_timing_pairs(
        block,
        header,
        "DELAYS"
    )

    warps = _chart_timing_pairs(
        block,
        header,
        "WARPS"
    )

    offset = _chart_offset(
        block,
        header
    )

    return {
        "index": index,
        "stepstype": stepstype,
        "description": description,
        "chartname": chartname,
        "difficulty": difficulty,
        "meter": meter,
        "radar": radar,
        "note_data": note_data.strip(),

        # Timing efectivo de ESTE chart.
        "offset": offset,
        "bpms": bpms,
        "stops": stops,
        "delays": delays,
        "warps": warps,
    }


def load_ssc(path):
    """
    Carga .ssc incluyendo split timing por chart.
    """

    text = _read_text(
        path
    )

    header, blocks = (
        _split_ssc(
            text
        )
    )

    # Conservamos también el timing global para diagnóstico.
    global_offset = _parse_float(
        _read_tag(
            header,
            "OFFSET"
        ),
        0.0
    )

    global_bpms = _parse_timing_pairs(
        _read_tag(
            header,
            "BPMS"
        )
    )

    global_stops = _parse_timing_pairs(
        _read_tag(
            header,
            "STOPS"
        )
    )

    global_delays = _parse_timing_pairs(
        _read_tag(
            header,
            "DELAYS"
        )
    )

    global_warps = _parse_timing_pairs(
        _read_tag(
            header,
            "WARPS"
        )
    )

    charts = []

    for i, block in enumerate(blocks):

        chart = _parse_ssc_chart(
            block,
            header,
            i
        )

        if chart is not None:
            charts.append(chart)

    return {
        "format": "ssc",
        "offset": global_offset,
        "bpms": global_bpms,
        "stops": global_stops,
        "delays": global_delays,
        "warps": global_warps,
        "charts": charts,
    }


def convert_ssc_chart(data, chart):
    """
    Convierte el chart SSC seleccionado usando SU timing efectivo,
    no necesariamente el timing global del archivo.
    """

    return _convert_stepmania_notes(
        note_data=chart["note_data"],
        bpms=chart["bpms"],
        stops=chart["stops"],
        delays=chart["delays"],
        warps=chart["warps"],
        offset=chart["offset"]
    )


def convert_stepmania_chart(data, chart):
    """
    API unificada para .sm y .ssc.
    """

    fmt = data.get(
        "format",
        ""
    ).lower()

    if fmt == "sm":
        return convert_sm_chart(
            data,
            chart
        )

    if fmt == "ssc":
        return convert_ssc_chart(
            data,
            chart
        )

    raise ValueError(
        "convert_stepmania_chart solo acepta .sm o .ssc"
    )


# ============================================================
# CARGADOR UNIVERSAL
# ============================================================

def load_chart_file(path):
    path = Path(path)

    extension = (
        path.suffix.lower()
    )

    if extension == ".osu":
        return load_osu(path)

    if extension == ".sm":
        return load_sm(path)

    if extension == ".ssc":
        return load_ssc(path)

    raise ValueError(
        f"Formato no soportado: {extension}"
    )
