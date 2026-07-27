from parser import Parser, ParserError
from models import Drone, Zone
from pathfinding import Pathfinder
from simulation import SimulationVisualizer
import sys

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 \
        else "maps/hard/03_ultimate_challenge.txt"

    try:
        parser = Parser(path)
        parser.run()
    except ParserError as e:
        print(f"[Parser Error] {e}", file=sys.stderr)
        sys.exit(1)

    try:
        start_hub: Zone = next(z for z in parser.zones if z.is_start)
        end_hub:   Zone = next(z for z in parser.zones if z.is_end)

        zone_traffic: dict[Zone, int] = {z: 0 for z in parser.zones}
        drones: list[Drone] = []

        # Reset round-robin counter for each new simulation run
        Pathfinder.reset()

        for i in range(parser.nb_drones):
            path_for_drone = Pathfinder.get_path(
                start_hub, end_hub,
                parser.graph, zone_traffic,
                dispatch_turn=i + 1,
            )

            if not path_for_drone:
                print(f"Fatal: no valid path found for drone {i + 1}.")
                sys.exit(1)

            drone = Drone(
                id=i + 1,
                coord=(start_hub.x, start_hub.y),
                curr_zone=start_hub,
                )
            drone.graph = parser.graph
            drone.end_hub = end_hub
            drone.zone_traffic = zone_traffic
            drone.pathfinder = Pathfinder
            drone.zones = list(path_for_drone[1:])
            drones.append(drone)

            for z in path_for_drone[1:]:
                zone_traffic[z] = zone_traffic.get(z, 0) + 1

        start_hub.zone_drones_count = parser.nb_drones

        engine = SimulationVisualizer(parser, drones)
        engine.run()
    except Exception as e:
        print(f"Error: {e}")
        raise
