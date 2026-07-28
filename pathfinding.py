import heapq
from typing import Any

from models import Zone


class Pathfinder:

    # ─────────────────────────────────────────────────────────────────────────
    #  DIJKSTRA  (internal — supports node/edge exclusion for Yen's)
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _dijkstra(
        start: Zone,
        end: Zone,
        graph: dict[Zone, list[tuple[Zone, Any]]],
        excluded_nodes: set[Zone] | None = None,
        excluded_edges: set[tuple[Zone, Zone]] | None = None,
    ) -> list[Zone] | None:
        if excluded_nodes is None:
            excluded_nodes = set()
        if excluded_edges is None:
            excluded_edges = set()

        dist: dict[Zone, float] = {start: 0.0}
        prev: dict[Zone, Zone | None] = {start: None}
        visited: set[Zone] = set()
        heap: list[tuple[float, int, Zone]] = [(0.0, id(start), start)]

        while heap:
            cost, _, zone = heapq.heappop(heap)
            if zone in visited:
                continue
            visited.add(zone)
            if zone == end:
                path: list[Zone] = []
                node: Zone | None = zone
                while node is not None:
                    path.append(node)
                    node = prev[node]
                path.reverse()
                return path

            for neighbor, _ in graph.get(zone, []):
                if neighbor in excluded_nodes:
                    continue
                if (zone, neighbor) in excluded_edges or \
                   (neighbor, zone) in excluded_edges:
                    continue
                if neighbor.zone_type == "blocked":
                    continue

                if neighbor.zone_type == "priority":
                    base = 0.5
                elif neighbor.zone_type == "restricted":
                    base = 2.0
                else:
                    base = 1.0

                new_cost = cost + base
                if new_cost < dist.get(neighbor, float('inf')):
                    dist[neighbor] = new_cost
                    prev[neighbor] = zone
                    heapq.heappush(heap, (new_cost, id(neighbor), neighbor))

        return None

    # ─────────────────────────────────────────────────────────────────────────
    #  YEN'S K-SHORTEST PATHS
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def k_shortest_paths(
        start: Zone,
        end: Zone,
        graph: dict[Zone, list[tuple[Zone, Any]]],
        k: int = 10,
    ) -> list[list[Zone]]:
        def path_cost(path: list[Zone]) -> float:
            total = 0.0
            for zone in path[1:]:
                if zone.zone_type == "priority":
                    total += 0.5
                elif zone.zone_type == "restricted":
                    total += 2.0
                else:
                    total += 1.0
            return total

        first = Pathfinder._dijkstra(start, end, graph)
        if first is None:
            return []

        confirmed: list[list[Zone]] = [first]
        candidates: list[tuple[float, int, list[Zone]]] = []
        seen: set[tuple[Zone, ...]] = {tuple(first)}

        for _ in range(k - 1):
            base_path = confirmed[-1]
            for spur_idx in range(len(base_path) - 1):
                spur_node = base_path[spur_idx]
                root_path = base_path[:spur_idx + 1]

                excl_edges: set[tuple[Zone, Zone]] = set()
                for p in confirmed:
                    if len(p) > spur_idx and p[:spur_idx + 1] == root_path:
                        excl_edges.add((p[spur_idx], p[spur_idx + 1]))

                excl_nodes: set[Zone] = set(root_path[:-1])
                spur_path = Pathfinder._dijkstra(
                    spur_node,
                    end,
                    graph,
                    excluded_nodes=excl_nodes,
                    excluded_edges=excl_edges,
                )
                if spur_path is None:
                    continue

                full = root_path[:-1] + spur_path
                full_key = tuple(full)
                if full_key not in seen:
                    seen.add(full_key)
                    heapq.heappush(
                        candidates,
                        (path_cost(full), id(full), full)
                    )

            if not candidates:
                break
            _, _, nxt = heapq.heappop(candidates)
            confirmed.append(nxt)

        return confirmed

    # ─────────────────────────────────────────────────────────────────────────
    #  SCORING
    #    two-tier scoring:
    #    1. Primary sort: pure topology cost (shorter = better, traffic-free).
    #       This keeps PATH_A and PATH_B (3 hops) strictly preferred over
    #       PATH_C (5 hops) regardless of traffic state.
    #    2. Secondary sort: SHARED-node traffic penalty only.
    #       A shared node is one that appears on MORE THAN ONE candidate path.
    #       These nodes genuinely accrue long-term congestion because every
    #       drone passes through them. Non-shared nodes are pipeline-spaced
    #       and self-clearing — penalising them is misleading.
    #    3. Tie-breaking: when topology cost AND shared-node penalty are
    #       within epsilon, round-robin through tied paths.
    # ─────────────────────────────────────────────────────────────────────────

    _rr_counter: int = 0

    @classmethod
    def reset(cls) -> None:
        cls._rr_counter = 0

    @staticmethod
    def _topology_cost(path: list[Zone]) -> float:
        total = 0.0
        for zone in path[1:]:
            if zone.zone_type == "priority":
                total += 0.5
            elif zone.zone_type == "restricted":
                total += 2.0
            else:
                total += 1.0
        return total

    @staticmethod
    def _shared_penalty(
        path: list[Zone],
        all_paths: list[list[Zone]],
        traffic_dict: dict[Zone, int]
    ) -> float:
        """
        Penalty contribution from nodes shared across multiple candidate paths.
        Non-shared nodes are pipeline-spaced and self-clearing — ignored.
        """
        zone_path_count: dict[Zone, int] = {}
        for p in all_paths:
            for z in p[1:]:
                zone_path_count[z] = zone_path_count.get(z, 0) + 1

        penalty = 0.0
        for zone in path[1:]:
            if zone_path_count.get(zone, 0) <= 1:
                continue
            traffic = traffic_dict.get(zone, 0)
            capacity = max(zone.max_drones, 1)
            occ = traffic / capacity
            penalty += occ * occ * 2.0
        return penalty

    # ─────────────────────────────────────────────────────────────────────────
    #  PUBLIC INTERFACE
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def get_path(
        start_hub: Zone,
        end_hub: Zone,
        graph_dict: dict[Zone, list[tuple[Zone, Any]]],
        traffic_dict: dict[Zone, int],
        dispatch_turn: int = 1,
        k: int = 10
    ) -> list[Zone] | None:
        """
        Pick the best path for the next drone.
        """
        paths = Pathfinder.k_shortest_paths(
            start_hub, end_hub, graph_dict, k=k
        )
        if not paths:
            return None

        epsilon = 0.05

        scored: list[tuple[float, float, int, list[Zone]]] = []
        for path in paths:
            topo = Pathfinder._topology_cost(path)
            shared = Pathfinder._shared_penalty(path, paths, traffic_dict)
            scored.append((topo, shared, id(path), path))

        scored.sort(key=lambda x: (x[0], x[1]))

        best_topo = scored[0][0]
        best_shared = scored[0][1]
        tied = [
            item for item in scored
            if item[0] <= best_topo + epsilon
            and item[1] <= best_shared + epsilon
        ]

        chosen = tied[Pathfinder._rr_counter % len(tied)]
        Pathfinder._rr_counter += 1

        return chosen[3]
