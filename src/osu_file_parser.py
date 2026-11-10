import math


class parser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.od = -1
        self.column_count = -1
        self.columns = []
        self.note_starts = []
        self.note_ends = []
        self.note_types = []

    def process(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            try:
                for line in f:
                    self.read_metadata(f, line)

                    cc = self._read_column_count(line)
                    if cc != -1:
                        self.column_count = cc

                    self.od = 9

                    if self.column_count != -1:
                        self._read_notes(f, line, self.column_count)

            except StopIteration:
                pass

    def read_metadata(self, f, line):
        # Metadata is not needed for note extraction. The original reader
        # advanced the file iterator until "Source:", which is optional in
        # .osu files. Maps without Source consequently lost the subsequent
        # [Difficulty]/CircleSize section and were falsely rejected as
        # non-4K charts. Never consume the iterator here.
        return None

    def _read_column_count(self, line):
        key, separator, raw_value = line.partition(":")
        if not separator or key.strip().lower() != "circlesize":
            return -1

        # CircleSize is the *entire* value, not the final character.
        # A real 4K mania map may use CircleSize:4.0 or 4.000000.
        # Reading only the final "0" incorrectly classified it as 10K.
        # Ignore optional inline .osu comments and surrounding spaces.
        raw_value = raw_value.split("//", 1)[0].strip()
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid osu! CircleSize: {raw_value!r}"
            ) from exc
        if not math.isfinite(value) or value <= 0 or not value.is_integer():
            raise ValueError(f"Invalid osu! CircleSize: {raw_value!r}")
        return int(value)

    def _read_notes(self, f, line, column_count):
        if "[HitObjects]" not in line:
            return
        line = next(f)
        while line is not None:
            self._parse_hit_object(line, column_count)
            line = next(f)

    def _parse_hit_object(self, line, column_count):
        params = line.split(",")
        column_width = 512 // column_count
        self.columns.append(int(float(params[0])) // column_width)
        self.note_starts.append(int(params[2]))
        self.note_types.append(int(params[3]))
        self.note_ends.append(int(params[5].split(":")[0]))

    def get_parsed_data(self):
        return [
            self.column_count,
            self.columns,
            self.note_starts,
            self.note_ends,
            self.note_types,
            self.od,
        ]