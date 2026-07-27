from models import Zone
import heapq


class Pathfinder:

    # ─────────────────────────────────────────────────────────────────────────
    #  DIJKSTRA  (internal — supports node/edge exclusion for Yen's)
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _dijkstra(start: Zone, end: Zone, graph: dict,
                  excluded_nodes: set = None,
                  excluded_edges: set = None) -> list | None:
        if excluded_nodes is None:
            excluded_nodes = set()
        if excluded_edges is None:
            excluded_edges = set()

        dist    = {start: 0.0}
        prev    = {start: None}
        visited = set()
        heap    = [(0.0, id(start), start)]

        while heap:
            cost, _, zone = heapq.heappop(heap)
            if zone in visited:
                continue
            visited.add(zone)
            if zone == end:
                path, node = [], zone
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
    def k_shortest_paths(start: Zone, end: Zone, graph: dict,
                         k: int = 10) -> list[list[Zone]]:
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
        candidates: list[tuple]     = []
        seen: set[tuple]            = {tuple(first)}

        for _ in range(k - 1):
            base_path = confirmed[-1]
            for spur_idx in range(len(base_path) - 1):
                spur_node = base_path[spur_idx]
                root_path = base_path[:spur_idx + 1]

                excl_edges: set = set()
                for p in confirmed:
                    if len(p) > spur_idx and p[:spur_idx + 1] == root_path:
                        excl_edges.add((p[spur_idx], p[spur_idx + 1]))

                excl_nodes: set = set(root_path[:-1])
                spur_path = Pathfinder._dijkstra(
                    spur_node, end, graph,
                    excluded_nodes=excl_nodes,
                    excluded_edges=excl_edges,
                )
                if spur_path is None:
                    continue

                full      = root_path[:-1] + spur_path
                full_key  = tuple(full)
                if full_key not in seen:
                    seen.add(full_key)
                    heapq.heappush(candidates,
                                   (path_cost(full), id(full), full))

            if not candidates:
                break
            _, _, nxt = heapq.heappop(candidates)
            confirmed.append(nxt)

        return confirmed

    # ─────────────────────────────────────────────────────────────────────────
    #  SCORING
    #
    #  Why pure traffic penalty fails (the 47-turn problem):
    #    All paths converge at micro_gate1, so its traffic penalty is equal
    #    across all routes and cancels out. Only intermediate nodes differ.
    #    But intermediate nodes (maze_a1, maze_b1 etc.) are NOT shared — each
    #    path's nodes will be clear by the time the next drone arrives, because
    #    the single-lane entry (start→gate_hell1, cap=1) spaces drones exactly
    #    1 turn apart. A cap-1 node clears in 1 turn, so drone i+2 always finds
    #    maze_a1 empty even though traffic_dict still shows 1.
    #
    #    Result: static traffic overcounts congestion on short paths and makes
    #    the 5-hop PATH_C look cheaper than the 3-hop PATH_A/B after both are
    #    assigned once. PATH_C's 2 extra hops delay drone 25 by 2 turns → 47.
    #
    #  Fix — two-tier scoring:
    #    1. Primary sort: pure topology cost (shorter = better, traffic-free).
    #       This keeps PATH_A and PATH_B (3 hops) strictly preferred over PATH_C
    #       (5 hops) regardless of traffic state.
    #    2. Secondary sort: SHARED-node traffic penalty only.
    #       A shared node is one that appears on MORE THAN ONE candidate path.
    #       These nodes (e.g. micro_gate1) genuinely accrue long-term congestion
    #       because every drone passes through them. Non-shared intermediate nodes
    #       are pipeline-spaced and self-clearing — penalising them is misleading.
    #    3. Tie-breaking: when topology cost AND shared-node penalty are within
    #       epsilon, round-robin through tied paths.
    #       This enforces A/B/A/B/… alternation when both have equal topology cost.
    # ─────────────────────────────────────────────────────────────────────────

    # Persistent round-robin counter (class-level, resets each simulation run
    # via Pathfinder.reset())
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
    def _shared_penalty(path: list[Zone],
                        all_paths: list[list[Zone]],
                        traffic_dict: dict) -> float:
        """
        Penalty contribution from nodes shared across multiple candidate paths.
        Non-shared nodes are pipeline-spaced and self-clearing — ignored.
        """
        # Count how many paths each zone appears in
        zone_path_count: dict[Zone, int] = {}
        for p in all_paths:
            for z in p[1:]:
                zone_path_count[z] = zone_path_count.get(z, 0) + 1

        penalty = 0.0
        for zone in path[1:]:
            if zone_path_count.get(zone, 0) <= 1:
                continue   # unique to this path → self-clearing, skip
            traffic  = traffic_dict.get(zone, 0)
            capacity = max(zone.max_drones, 1)
            occ      = traffic / capacity
            penalty += occ * occ * 2.0
        return penalty

    # ─────────────────────────────────────────────────────────────────────────
    #  PUBLIC INTERFACE
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def get_path(start_hub: Zone, end_hub: Zone,
                 graph_dict: dict, traffic_dict: dict,
                 dispatch_turn: int = 1,
                 k: int = 10) -> list[Zone] | None:
        """
        Pick the best path for the next drone.

        Selection order:
          1. Lowest topology cost  (pure hop count / zone type weights)
          2. Lowest shared-node traffic penalty
          3. Round-robin among ties within epsilon
        """
        paths = Pathfinder.k_shortest_paths(start_hub, end_hub, graph_dict, k=k)
        if not paths:
            return None

        EPSILON = 0.05

        # Score every candidate
        scored: list[tuple[float, float, int, list[Zone]]] = []
        for path in paths:
            topo    = Pathfinder._topology_cost(path)
            shared  = Pathfinder._shared_penalty(path, paths, traffic_dict)
            scored.append((topo, shared, id(path), path))

        scored.sort(key=lambda x: (x[0], x[1]))

        # Collect paths tied with the best on both dimensions
        best_topo   = scored[0][0]
        best_shared = scored[0][1]
        tied = [
            item for item in scored
            if item[0] <= best_topo   + EPSILON
            and item[1] <= best_shared + EPSILON
        ]

        # Round-robin among tied paths
        chosen = tied[Pathfinder._rr_counter % len(tied)]
        Pathfinder._rr_counter += 1

        return chosen[3]
