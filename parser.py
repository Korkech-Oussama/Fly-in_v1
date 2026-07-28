import re
from typing import List, Optional, Tuple
from models import Zone, Connection


class ParserError(Exception):
    """Raised for any map file parsing or validation error."""
    pass


# A raw parsed line: (line_number, key, value)
RawLine = Tuple[int, str, str]

# A parsed connection: (line_number, zone_a, zone_b, capacity | None)
ParsedConnection = Tuple[int, str, str, Optional[int]]

# A parsed zone field row: (line_number, key, name, x, y, raw_metadata | None)
ParsedZone = Tuple[int, str, str, int, int, Optional[str]]


class Parser:

    VALID_KEYS = {'nb_drones', 'hub', 'start_hub', 'end_hub', 'connection'}
    ZONE_KEYS = {'hub', 'start_hub', 'end_hub'}
    VALID_ZONE_TYPES = {'normal', 'blocked', 'restricted', 'priority'}

    def __init__(self, path_to_map: str):
        self.path_to_map = path_to_map
        self.nb_drones: int = 1
        self.zones: List[Zone] = []
        self.connections: List[Connection] = []
        self.name_to_zone: dict = {}
        self.graph: dict = {}

        # Internal cache — populated once by _parse_file()
        self._raw_lines: List[RawLine] = []
        self._zone_lines: List[RawLine] = []
        self._connection_lines: List[RawLine] = []

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Parse the file and populate all public data structures."""
        self._parse_file()
        self._extract_nb_drones()
        self._split_zones_and_connections()
        self._process_zones()
        self._process_connections()
        self._build_lookup_table()
        self._build_graph()

    # ------------------------------------------------------------------ #
    #  Step 1 – read & tokenise the file exactly once                     #
    # ------------------------------------------------------------------ #

    def _parse_file(self) -> None:
        """
        Read every non-blank, non-comment line and store it as
        (line_number, key, value).  The colon is the only separator
        recognised; the first colon splits key from value so that
        values such as connection values (hub-roof1) are kept intact.
        """
        try:
            with open(self.path_to_map) as f:
                lines = f.readlines()
        except OSError as e:
            raise ParserError(f"Cannot open map file: {e}") from e

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            if '#' in stripped:
                for index, char in enumerate(stripped):
                    if char == '#':
                        stripped = stripped[:index]
                        break

            if ':' not in stripped:
                raise ParserError(
                    f"Line {lineno}: expected 'KEY: VALUE' format, "
                    f"got: {stripped!r}"
                )

            key, _, value = stripped.partition(':')
            key = key.strip()
            value = value.strip()

            if not key:
                raise ParserError(
                    f"Line {lineno}: key is empty in: {stripped!r}"
                )
            if not value:
                raise ParserError(
                    f"Line {lineno}: value is missing for key '{key}'."
                )
            if key not in self.VALID_KEYS:
                raise ParserError(
                    f"Line {lineno}: unknown key '{key}'. "
                    f"Valid keys are: {sorted(self.VALID_KEYS)}."
                )

            self._raw_lines.append((lineno, key, value))

    # ------------------------------------------------------------------ #
    #  Step 2 – nb_drones (must be first non-comment line)               #
    # ------------------------------------------------------------------ #

    def _extract_nb_drones(self) -> None:
        if not self._raw_lines:
            raise ParserError("Map file is empty or contains only comments.")

        lineno, key, value = self._raw_lines[0]

        if key != 'nb_drones':
            raise ParserError(
                f"Line {lineno}: first directive must be 'nb_drones', "
                f"got '{key}'."
            )
        try:
            self.nb_drones = int(value)
        except ValueError:
            raise ParserError(
                f"Line {lineno}: 'nb_drones' must be a positive integer, "
                f"got '{value}'."
            )
        if self.nb_drones <= 0:
            raise ParserError(
                f"Line {lineno}: 'nb_drones' must be > 0,"
                + f" got {self.nb_drones}."
            )

    # ------------------------------------------------------------------ #
    #  Step 3 – separate zone lines from connection lines                 #
    # ------------------------------------------------------------------ #

    def _split_zones_and_connections(self) -> None:
        for entry in self._raw_lines[1:]:
            lineno, key, value = entry
            if key in self.ZONE_KEYS:
                self._zone_lines.append(entry)
            else:  # key == 'connection' (unknown already rejected)
                self._connection_lines.append(entry)

    # ------------------------------------------------------------------ #
    #  Step 4 – zones                                                     #
    # ------------------------------------------------------------------ #

    def _process_zones(self) -> None:
        self._validate_hub_counts()
        parsed_zones = self._parse_zone_fields()
        self._build_zone_objects(parsed_zones)

    def _validate_hub_counts(self) -> None:
        keys = [key for _, key, _ in self._zone_lines]
        starts = keys.count('start_hub')
        ends = keys.count('end_hub')
        if starts != 1:
            raise ParserError(
                f"Expected exactly one 'start_hub', found {starts}."
            )
        if ends != 1:
            raise ParserError(
                f"Expected exactly one 'end_hub', found {ends}."
            )

    def _parse_zone_fields(self) -> List[ParsedZone]:
        """
        Tokenise each zone line into (lineno, role, name, x, y, raw_meta).
        raw_meta is the [...] string if present, else None.
        """
        results: List[ParsedZone] = []

        # metadata block starts with '[' — split at most 3 whitespace gaps
        # to keep the metadata block (which may contain spaces) intact
        field_pattern = re.compile(
            r'^(\S+)\s+(-?\d+)\s+(-?\d+)(?:\s+(\[.+\]))?$'
        )

        for lineno, key, value in self._zone_lines:
            m = field_pattern.match(value)
            if not m:
                raise ParserError(
                    f"Line {lineno}: invalid zone format. "
                    f"Expected 'name x y [metadata]', got: {value!r}"
                )
            name = m.group(1)
            x = int(m.group(2))
            y = int(m.group(3))
            raw_meta = m.group(4)  # None if absent

            # Zone names must not contain dashes or spaces
            if re.search(r'[-\s]', name):
                raise ParserError(
                    f"Line {lineno}: zone name '{name}' must not "
                    f"contain dashes or spaces."
                )

            results.append((lineno, key, name, x, y, raw_meta))
        return results

    def _build_zone_objects(self, parsed_zones: List[ParsedZone]) -> None:
        """
        Create Zone objects, check for duplicate names, parse and apply
        metadata, and mark start/end roles.
        """
        seen_names: dict = {}   # name -> lineno (for duplicate reporting)

        for lineno, role, name, x, y, raw_meta in parsed_zones:

            # Duplicate name check
            if name in seen_names:
                raise ParserError(
                    f"Line {lineno}: duplicate zone name '{name}' "
                    f"(first defined at line {seen_names[name]})."
                )
            seen_names[name] = lineno

            zone = Zone(name, x, y)

            # Mark start / end role directly on the Zone object
            if role == 'start_hub':
                zone.is_start = True
            elif role == 'end_hub':
                zone.is_end = True

            # Parse optional metadata block
            if raw_meta is not None:
                metadata = self._parse_metadata_block(lineno, raw_meta)
                self._apply_zone_metadata(lineno, zone, metadata)

            self.zones.append(zone)

    # ---- metadata helpers ------------------------------------------------

    # Allowed keys inside a zone metadata block
    _ZONE_META_KEYS = {'zone', 'color', 'max_drones'}
    # Pattern: key=value pairs inside balanced brackets, spaces allowed
    _META_BLOCK_PATTERN = re.compile(
        r'^\[(\s*\w+=[\w-]+(?:\s+\w+=[\w-]+)*\s*)\]$'
    )

    def _parse_metadata_block(self, lineno: int, raw: str) -> dict:
        """
        Parse '[key=value key=value ...]' into a dict.
        Raises ParserError for any syntax issue.
        """
        m = self._META_BLOCK_PATTERN.match(raw)
        if not m:
            raise ParserError(
                f"Line {lineno}: invalid metadata syntax: {raw!r}. "
                f"Expected '[key=value ...]'."
            )
        pairs = re.findall(r'(\w+)=([\w-]+)', m.group(1))
        return dict(pairs)

    def _apply_zone_metadata(
        self, lineno: int, zone: Zone, data: dict
    ) -> None:
        # Unknown metadata keys
        unknown = set(data) - self._ZONE_META_KEYS
        if unknown:
            raise ParserError(
                f"Line {lineno}: unknown metadata key(s) for zone "
                f"'{zone.name}': {sorted(unknown)}. "
                f"Valid keys: {sorted(self._ZONE_META_KEYS)}."
            )

        zone_type = data.get('zone')
        if zone_type is not None:
            if zone_type not in self.VALID_ZONE_TYPES:
                raise ParserError(
                    f"Line {lineno}: zone '{zone.name}' has invalid type "
                    f"'{zone_type}'. Must be one of {self.VALID_ZONE_TYPES}."
                )
            zone.zone_type = zone_type
            if zone_type == 'restricted':
                zone.cost = 2

        max_drones_raw = data.get('max_drones')
        if max_drones_raw is not None:
            max_drones = int(max_drones_raw)
            if max_drones < 1:
                raise ParserError(
                    f"Line {lineno}: 'max_drones' for zone '{zone.name}' "
                    f"must be a positive integer, got {max_drones}."
                )
            zone.max_drones = max_drones

        color = data.get('color')
        if color is not None:
            zone.color = color

    # ------------------------------------------------------------------ #
    #  Step 5 – connections                                               #
    # ------------------------------------------------------------------ #

    def _process_connections(self) -> None:
        parsed = self._parse_connection_fields()
        self._validate_connection_zones(parsed)
        self._validate_no_duplicate_connections(parsed)
        self._create_connection_objects(parsed)

    # Pattern: zone_a-zone_b  optionally followed by [max_link_capacity=N]
    _CONN_PATTERN = re.compile(
        r'^(\w+)-(\w+)(?:\s+\[max_link_capacity=(\d+)\])?$'
    )

    def _parse_connection_fields(self) -> List[ParsedConnection]:
        results: List[ParsedConnection] = []
        for lineno, _, value in self._connection_lines:
            m = self._CONN_PATTERN.match(value)
            if not m:
                raise ParserError(
                    f"Line {lineno}: invalid connection syntax: {value!r}. "
                    f"Expected 'zone1-zone2' or "
                    f"'zone1-zone2 [max_link_capacity=N]'."
                )
            zone_a = m.group(1)
            zone_b = m.group(2)
            capacity = int(m.group(3)) if m.group(3) is not None else None

            # Capacity must be a positive integer (0 is not valid)
            if capacity is not None and capacity < 1:
                raise ParserError(
                    f"Line {lineno}: 'max_link_capacity' must be a positive "
                    f"integer, got {capacity}."
                )

            results.append((lineno, zone_a, zone_b, capacity))
        return results

    def _validate_connection_zones(
        self, parsed: List[ParsedConnection]
    ) -> None:
        """Every zone name in a connection must have been declared."""
        known = {zone.name for zone in self.zones}
        for lineno, zone_a, zone_b, _ in parsed:
            for name in (zone_a, zone_b):
                if name not in known:
                    raise ParserError(
                        f"Line {lineno}: connection references undeclared "
                        f"zone '{name}'."
                    )

    def _validate_no_duplicate_connections(
        self, parsed: List[ParsedConnection]
    ) -> None:
        seen: dict = {}   # frozenset -> lineno
        for lineno, zone_a, zone_b, _ in parsed:
            pair = frozenset((zone_a, zone_b))
            if pair in seen:
                raise ParserError(
                    f"Line {lineno}: duplicate connection between "
                    f"'{zone_a}' and '{zone_b}' — already defined at "
                    f"line {seen[pair]} (a-b and b-a are the same)."
                )
            seen[pair] = lineno

    def _create_connection_objects(
        self, parsed: List[ParsedConnection]
    ) -> None:
        for _, zone_a, zone_b, capacity in parsed:
            conn = Connection(f"{zone_a}-{zone_b}")
            if capacity is not None:
                conn.max_link_capacity = capacity
            self.connections.append(conn)

    # ------------------------------------------------------------------ #
    #  Step 6 – build adjacency graph                                     #
    # ------------------------------------------------------------------ #

    def _build_lookup_table(self) -> None:
        """build a look up table to quiqly find a zone by name"""
        self.name_to_zone = {zone.name: zone for zone in self.zones}

    # def _build_graph(self) -> None:
    #     """
    #     Build an undirected adjacency list: {zone_name: [neighbour, ...]}.
    #     Zone names cannot contain dashes, so splitting on '-' is unambiguous.
    #     """
    #     self.graph = {zone.name: [] for zone in self.zones}
    #     for conn in self.connections:
    #         zone_a, zone_b = conn.name.split('-', 1)
    #         self.graph[zone_a].append(zone_b)
    #         self.graph[zone_b].append(zone_a)

    def _build_graph(self) -> None:
        """
        Build an undirected adjacency list: {zone_name: [neighbour, ...]}.
        Zone names cannot contain dashes, so splitting on '-' is unambiguous.
        """
        self.graph = {zone: [] for zone in self.zones}
        for conn in self.connections:
            name_a, name_b = conn.name.split('-', 1)
            zone_a = self.name_to_zone[name_a]
            zone_b = self.name_to_zone[name_b]

            self.graph[zone_a].append((zone_b, conn))
            self.graph[zone_b].append((zone_a, conn))
