from typing import Any


class Zone:

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        cost: int = 1,
        is_start: bool = False,
        is_end: bool = False,
    ) -> None:
        self.name: str = name
        self.x: int = x
        self.y: int = y
        self.cost: int = cost
        self.zone_type: str = 'normal'
        self.color: str = ""
        self.max_drones: int = 1
        self.is_start: bool = is_start
        self.is_end: bool = is_end
        self.zone_drones_count: int = 0

    def _has_space(self) -> bool:
        if self.is_end:
            return True
        return self.zone_drones_count < self.max_drones

    def __str__(self) -> str:
        return (
            f"{self.name}, {(self.x, self.y)}, {self.cost}, "
            f"{self.zone_type}, {self.color}, {self.max_drones}"
        )


class Connection:

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.max_link_capacity: int = 1
        self.conn_zone_drones_count: int = 0

    def _has_space(self) -> bool:
        return self.conn_zone_drones_count < self.max_link_capacity

    def __str__(self) -> str:
        return f"{self.name}, {self.max_link_capacity}"


class Drone:

    def __init__(
        self, id: int, coord: tuple[int, int], curr_zone: Zone
    ) -> None:
        self.id: int = id
        self.curr_zone: Zone | None = curr_zone
        self.coord: tuple[int, int] = coord
        self.flight_timer: int = 0
        self.arrived: bool = False
        self.zones: list[Zone] = []
        self.graph: dict[Zone, list[tuple[Zone, Connection]]] = {}
        self.active_connection: Connection | None = None

        # ── Dynamic re-routing support (wired in by main.py)
        self.end_hub: Zone | None = None
        self.zone_traffic: dict[Zone, int] = {}
        self.pathfinder: Any | None = None
        self._blocked_turns: float = 0.0
        self._REROUTE_AFTER: float = 2.0

    # ── helpers

    def _can_move_to(self, to_zone: Zone) -> bool:
        if not to_zone._has_space():
            return False
        conn = self._get_connection_to(to_zone)
        if not conn or conn.conn_zone_drones_count >= conn.max_link_capacity:
            return False
        return True

    def _get_connection_to(self, to_zone: Zone) -> Connection | None:
        if self.curr_zone is None:
            return None
        for neighbor, conn in self.graph.get(self.curr_zone, []):
            if neighbor == to_zone:
                return conn
        return None

    def _update_occupancy(self, to_zone: Zone, conn: Connection) -> None:
        if self.curr_zone:
            self.curr_zone.zone_drones_count -= 1
        to_zone.zone_drones_count += 1
        conn.conn_zone_drones_count += 1

    # ── dynamic re-route

    def _try_reroute(self) -> bool:
        """
        Recompute a fresh path from curr_zone to end_hub using current
        traffic. Skips rerouting when:
          - Only one neighbor reachable (no alternative exists — e.g. start)
          - New path is identical to current plan (pointless churn)
        Returns True if a genuinely different path was installed.
        """
        if (
            self.pathfinder is None
            or self.end_hub is None
            or self.curr_zone is None
        ):
            return False

        # Skip if this zone is a funnel with no real alternatives
        neighbors = self.graph.get(self.curr_zone, [])
        reachable = [n for n, _ in neighbors if n.zone_type != 'blocked']
        if len(reachable) <= 1:
            return False

        new_path = self.pathfinder.get_path(
            self.curr_zone, self.end_hub, self.graph, self.zone_traffic
        )
        if not new_path or len(new_path) <= 1:
            return False

        new_zones = list(new_path[1:])

        # Skip if identical to what we already have
        if new_zones == self.zones:
            return False

        # Swap traffic accounting
        for z in self.zones:
            self.zone_traffic[z] = max(0, self.zone_traffic.get(z, 0) - 1)
        self.zones = new_zones
        for z in self.zones:
            self.zone_traffic[z] = self.zone_traffic.get(z, 0) + 1

        self._blocked_turns = 0.0
        return True

    # ── main move logic

    def _move(self) -> str | None:

        # ── still in transit (cost-2 hold)
        if self.flight_timer > 0:
            self.flight_timer -= 1
            if self.flight_timer == 0 and self.active_connection:
                self.active_connection.conn_zone_drones_count -= 1
                self.active_connection = None
            label = self.zones[0].name if self.zones else 'transit'
            return f"D{self.id}-{label}"

        if self.arrived or not self.zones or self.curr_zone is None:
            return None

        to_zone = self.zones[0]

        if not self._can_move_to(to_zone):
            self._blocked_turns += 0.5
            if self._blocked_turns >= self._REROUTE_AFTER:
                if self._try_reroute():
                    print(
                        f"Drone {self.id} rerouted "
                        f"from {self.curr_zone.name}"
                    )
                    # Attempt the new next hop immediately this turn
                    if not self.zones:
                        return None
                    to_zone = self.zones[0]
                    if not self._can_move_to(to_zone):
                        return None
                else:
                    return None
            else:
                return None

        conn = self._get_connection_to(to_zone)
        if not conn:
            return None

        self._blocked_turns = 0.0
        self._update_occupancy(to_zone, conn)
        self.zones.pop(0)
        self.curr_zone = to_zone
        self.coord = (to_zone.x, to_zone.y)

        if to_zone.cost == 2:
            self.flight_timer = 1
            self.active_connection = conn
        else:
            conn.conn_zone_drones_count -= 1

        if to_zone.is_end:
            self.arrived = True

        # print(f"D{self.id}-{to_zone.name}")
        return f"D{self.id}-{to_zone.name}"
