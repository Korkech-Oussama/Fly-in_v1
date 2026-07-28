# Fly-In: Dynamic Drone Routing Engine

*This project has been created as part of the 42 curriculum by <okorkech>.*

## Description

Fly-In is a data engineering and pathfinding simulation designed to route a fleet of drones through highly congested, dynamically changing network maps. The primary goal of the project is to transport multiple agents from a starting hub to an ending hub in the fewest possible turns (e.g., beating the sub-45 turn threshold on complex maps like "The Impossible Dream").

The project simulates real-time traffic bottlenecks, limited-capacity gates, and emergency bypass routes. It challenges standard shortest-path logic by demonstrating that the shortest topological distance is often the slowest route when traffic is factored in.

## Instructions

This project uses a Makefile to automatically manage the Python virtual environment, dependencies, execution, and linting.

### Installation

To create the virtual environment and install all required dependencies (such as `pygame`), run:

```bash
make install
```

### Execution

To run the simulation using the default challenger map (`01_the_impossible_dream.txt`) with capacity info enabled, run:

```bash
make run
```

### Development and Utility Commands

- `make debug`: Launches the simulation inside the standard Python debugger (pdb).
- `make lint`: Runs standard linting and type checking using `flake8` and `mypy`.
- `make lint-strict`: Runs strict linting for enforcing rigorous type hints.
- `make clean`: Removes the virtual environment, `__pycache__` directories, and all temporary linting caches.

## Algorithm Choices and Implementation Strategy

The core routing engine underwent significant optimization to handle extreme congestion and tight bottlenecks:

- **Dynamic Traffic-Aware Dijkstra**: While traditional implementations of Dijkstra's algorithm evaluate strict topological distances, this engine injects dynamic congestion penalties directly into the node discovery phase. By doing this, the algorithm naturally bypasses jammed 1-capacity gates in favor of longer, but empty, emergency routes.

- **Hyper-Aggressive Penalties & Time Decay**: To prevent drones from getting trapped in "phantom traffic" (reacting to traffic that will be gone by the time they arrive), the engine uses a time-decay penalty system. Zones that are actively full receive a massive 100x weight penalty, which is mathematically divided by the drone's future distance (depth) from that node.

- **Evolution from Yen's Algorithm**: The project initially utilized Yen's K-Shortest Paths to find topological routes, later scoring them for traffic. This was strategically refactored. Integrating traffic data directly into the base A*/Dijkstra heuristic proved to be fundamentally faster and more adaptive than Yen's static path generation.

- **Round-Robin Load Balancing**: When multiple routes offer identical (or near-identical) topological and traffic costs within a strict margin of error (epsilon = 0.05), a round-robin distributor evenly disperses the drones across all tied lanes. This acts as a macro-level zipper, preventing micro-gridlocks before they form.

## Visual Representation Features

The simulation utilizes Pygame to translate the abstract graph mathematics into an observable, dynamic 2D visualizer, heavily enhancing the user experience and debugging process:

- **Pygame-Driven Dynamic Rendering**: The visualizer leverages Pygame's rendering loop to track and draw each drone's real-time position across the graph frame by frame. The edges update dynamically to represent active flight paths (e.g., transitioning to a specific `WIRE_TRANSIT` color when a drone is on the move).

- **Color-Coded Network Topology**: Zones are drawn using high-contrast neon palettes against a dark background (`BG_DARK`) to immediately communicate operational states to the user. Restricted nodes, priority lanes, and dead-ends are visually distinct (utilizing colors like `NEON_RED`, `PURPLE`, and `DARK_GREY`), allowing users to instantly comprehend the map's layout and difficulty.

- **Traffic Congestion Feedback**: By visually tracking how many drones occupy specific nodes and edges at any given turn directly on the Pygame canvas, the UI makes it effortless to spot algorithmic inefficiencies and bottleneck clusters without digging through terminal logs.
