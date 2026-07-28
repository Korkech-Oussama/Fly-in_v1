import math
import time
from typing import Any

import pygame

# ─────────────────────────────────────────────────────────────────────────────
#  COLOUR PALETTE
# ─────────────────────────────────────────────────────────────────────────────
BG_DARK: tuple[int, int, int] = (8, 12, 24)
NEON_CYAN: tuple[int, int, int] = (0, 230, 255)
NEON_YELLOW: tuple[int, int, int] = (255, 220, 0)
NEON_GREEN: tuple[int, int, int] = (0, 255, 140)
NEON_RED: tuple[int, int, int] = (255, 60, 60)
NEON_BLUE: tuple[int, int, int] = (60, 140, 255)
NEON_ORANGE: tuple[int, int, int] = (255, 140, 0)
WIRE_COLOR: tuple[int, int, int] = (40, 70, 110)
WIRE_ACTIVE: tuple[int, int, int] = (0, 180, 220)
WIRE_TRANSIT: tuple[int, int, int] = (255, 160, 0)
TEXT_BRIGHT: tuple[int, int, int] = (220, 235, 255)
TEXT_DIM: tuple[int, int, int] = (80, 110, 150)
PANEL_BORDER: tuple[int, int, int] = (30, 60, 100)
PANEL_BG: tuple[int, int, int] = (10, 16, 32)

ZONE_COLORS: dict[str, tuple[int, int, int]] = {
    'green': NEON_GREEN,
    'blue': NEON_BLUE,
    'red': NEON_RED,
}

DRONE_PALETTE: list[tuple[int, int, int]] = [
    (255, 220, 0),
    (0, 230, 255),
    (180, 60, 255),
    (255, 100, 60),
    (60, 255, 140),
    (255, 60, 160),
]


class RenderUtils:

    @staticmethod
    def draw_glow(
        surface: pygame.Surface,
        colour: tuple[int, int, int] | pygame.Color,
        pos: tuple[float, float],
        radius: int,
        layers: int = 5,
        alpha_start: int = 60
    ) -> None:
        for i in range(layers, 0, -1):
            r = radius + i * 5
            alpha = int(alpha_start * (i / layers) ** 1.5)
            s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(
                s,
                (colour[0], colour[1], colour[2], alpha),
                (r + 1, r + 1),
                r
            )
            surface.blit(s, (int(pos[0] - r - 1), int(pos[1] - r - 1)))

    @staticmethod
    def draw_glow_line(
        surface: pygame.Surface,
        colour: tuple[int, int, int] | pygame.Color,
        start: tuple[float, float],
        end: tuple[float, float],
        width: int = 2,
        alpha: int = 80
    ) -> None:
        sx, sy = int(start[0]), int(start[1])
        ex, ey = int(end[0]), int(end[1])

        if math.hypot(ex - sx, ey - sy) < 1:
            return

        s = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.line(
            s,
            (colour[0], colour[1], colour[2], alpha),
            (sx, sy),
            (ex, ey),
            width + 4
        )
        pygame.draw.line(
            s,
            (colour[0], colour[1], colour[2], 200),
            (sx, sy),
            (ex, ey),
            width
        )
        surface.blit(s, (0, 0))

    @staticmethod
    def lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t


# ─────────────────────────────────────────────────────────────────────────────
#  DRONE RENDER STATE
# ─────────────────────────────────────────────────────────────────────────────
class DroneRenderState:
    MOVE_DURATION: float = 0.40

    IDLE: str = "idle"
    MOVING: str = "moving"
    TRANSIT: str = "transit"

    def __init__(self, drone: Any, index: int) -> None:
        self.drone: Any = drone
        self.index: int = index
        self.colour: tuple[int, int, int] = DRONE_PALETTE[
            index % len(DRONE_PALETTE)
        ]

        self.px: float = 0.0
        self.py: float = 0.0
        self.target_px: float = 0.0
        self.target_py: float = 0.0

        self._state: str = self.IDLE
        self._move_start: float = 0.0
        self._trail: list[tuple[float, float]] = []

        self._transit_from_px: float = 0.0
        self._transit_from_py: float = 0.0
        self._transit_to_px: float = 0.0
        self._transit_to_py: float = 0.0

    def snap_to(self, px: float, py: float) -> None:
        self.px, self.py = px, py
        self.target_px, self.target_py = px, py
        self._state = self.IDLE

    def start_move(self, to_px: float, to_py: float, in_transit: bool) -> None:
        self._trail.append((self.px, self.py))
        if len(self._trail) > 6:
            self._trail.pop(0)

        self.target_px, self.target_py = to_px, to_py
        self._move_start = time.time()

        if in_transit:
            self._transit_from_px = self.px
            self._transit_from_py = self.py
            self._transit_to_px = to_px
            self._transit_to_py = to_py
            self._state = self.TRANSIT
        else:
            self._state = self.MOVING

    def finish_transit(self) -> None:
        if self._state == self.TRANSIT:
            self._move_start = time.time()
            self._state = self.MOVING

    def update(self) -> None:
        if self._state == self.MOVING:
            t = min((time.time() - self._move_start) / self.MOVE_DURATION, 1.0)
            t = t * t * (3.0 - 2.0 * t)
            self.px = RenderUtils.lerp(self.px, self.target_px, t)
            self.py = RenderUtils.lerp(self.py, self.target_py, t)
            if t >= 1.0:
                self.px, self.py = self.target_px, self.target_py
                self._state = self.IDLE

        elif self._state == self.TRANSIT:
            mid_x = (self._transit_from_px + self._transit_to_px) / 2.0
            mid_y = (self._transit_from_py + self._transit_to_py) / 2.0
            t = min((time.time() - self._move_start) / self.MOVE_DURATION, 1.0)
            t = t * t * (3.0 - 2.0 * t)
            self.px = RenderUtils.lerp(self.px, mid_x, t)
            self.py = RenderUtils.lerp(self.py, mid_y, t)

    @property
    def is_moving(self) -> bool:
        return self._state == self.MOVING

    @property
    def is_in_transit(self) -> bool:
        return self._state == self.TRANSIT


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN VISUALIZER
# ─────────────────────────────────────────────────────────────────────────────
class SimulationVisualizer:
    WIN_W: int = 1800
    WIN_H: int = 1020
    HUD_H: int = 200
    LOG_MAX: int = 10

    def __init__(self, parser: Any, drones: list[Any]) -> None:
        pygame.init()
        pygame.display.set_caption("Drone Swarm Simulator")

        self.width: int = self.WIN_W
        self.height: int = self.WIN_H
        self.screen: pygame.Surface = pygame.display.set_mode(
            (self.width, self.height)
        )
        self.clock: pygame.time.Clock = pygame.time.Clock()

        self.font_title: pygame.font.Font = pygame.font.SysFont(
            "Consolas", 20, bold=True
        )
        self.font_body: pygame.font.Font = pygame.font.SysFont(
            "Consolas", 15
        )
        self.font_small: pygame.font.Font = pygame.font.SysFont(
            "Consolas", 13
        )
        self.font_huge: pygame.font.Font = pygame.font.SysFont(
            "Consolas", 52, bold=True
        )

        self.parser: Any = parser
        self.drones: list[Any] = drones
        self.running: bool = True
        self.turn: int = 0
        self.auto_run: bool = False
        self.auto_interval: float = 1.0
        self._last_auto: float = time.time()
        self._time_start: float = time.time()

        self.map_area_w: int = self.width
        self.map_area_h: int = self.height - self.HUD_H

        self.cell_size: int = 160
        self.offset_x: int = 80
        self.offset_y: int = 80
        self._compute_layout()

        self._drone_render: list[DroneRenderState] = []
        for i, d in enumerate(drones):
            drs = DroneRenderState(d, i)
            if d.curr_zone:
                drs.snap_to(*self._zone_px(d.curr_zone, i))
            self._drone_render.append(drs)

        self._log: list[str] = ["[SYS] Simulation ready."]

        self._active_edges: list[
            tuple[
                tuple[float, float],
                tuple[float, float],
                float,
                tuple[int, int, int]
            ]
        ] = []
        self._transit_from_cache: dict[int, tuple[float, float]] = {}

    def _compute_layout(self) -> None:
        zones = self.parser.zones
        if not zones:
            self.cell_size = 160
            self.offset_x = 80
            self.offset_y = 80
            return
        xs = [z.x for z in zones]
        ys = [z.y for z in zones]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1)
        span_y = max(max_y - min_y, 1)
        padding = 140
        avail_w = self.map_area_w - padding * 2
        avail_h = self.map_area_h - padding * 2
        self.cell_size = int(min(avail_w / span_x, avail_h / span_y, 220.0))
        graph_w = span_x * self.cell_size
        graph_h = span_y * self.cell_size
        self.offset_x = int(
            (self.map_area_w - graph_w) / 2 - min_x * self.cell_size
        )
        self.offset_y = int(
            (self.map_area_h - graph_h) / 2 - min_y * self.cell_size
        )

    def _zone_px(self, zone: Any, drone_index: int = 0) -> tuple[float, float]:
        angle = (drone_index * 55) * math.pi / 180.0
        jitter = 10.0
        x = (zone.x * self.cell_size + self.offset_x
             + math.cos(angle) * jitter)
        y = (zone.y * self.cell_size + self.offset_y
             + math.sin(angle) * jitter)
        return x, y

    def _log_event(self, msg: str) -> None:
        self._log.append(msg)
        if len(self._log) > self.LOG_MAX:
            self._log.pop(0)

    def _step_simulation(self) -> None:
        any_active: bool = False

        for i, drone in enumerate(self.drones):
            drs = self._drone_render[i]
            old_zone = drone.curr_zone
            was_in_transit = drone.flight_timer > 0

            result = drone._move()
            if result is None:
                continue

            any_active = True
            new_zone = drone.curr_zone

            if was_in_transit and drone.flight_timer == 0:
                drs.finish_transit()
                p1 = self._transit_from_cache.get(i, (drs.px, drs.py))
                p2 = self._zone_px(new_zone)
                self._active_edges.append(
                    (p1, p2, time.time() + 1.2, WIRE_TRANSIT)
                )
                self._log_event(
                    f"[T{self.turn}] D{drone.id}: transit done "
                    f"→ {new_zone.name}"
                )

            elif was_in_transit and drone.flight_timer > 0:
                self._log_event(
                    f"[T{self.turn}] D{drone.id}: holding in {new_zone.name}"
                )

            elif old_zone is not new_zone:
                p1 = self._zone_px(old_zone) if old_zone else (drs.px, drs.py)
                p2 = self._zone_px(new_zone)
                in_transit = drone.flight_timer > 0

                if in_transit:
                    self._transit_from_cache[i] = p1
                    edge_col = WIRE_TRANSIT
                    expire = time.time() + 2.5
                    self._log_event(
                        f"[T{self.turn}] D{drone.id}: entered "
                        f"{new_zone.name} [HOLD]"
                    )
                else:
                    edge_col = WIRE_ACTIVE
                    expire = time.time() + 0.8
                    self._log_event(
                        f"[T{self.turn}] D{drone.id}: → {new_zone.name}"
                    )

                self._active_edges.append((p1, p2, expire, edge_col))
                drs.start_move(
                    *self._zone_px(new_zone, i),
                    in_transit=in_transit
                )

        if any_active:
            self.turn += 1
        else:
            self._log_event(f"[T{self.turn}] No movement.")

    def _draw_background(self) -> None:
        self.screen.fill(BG_DARK)
        t = time.time() - self._time_start
        dot_gap = 44
        for gx in range(0, self.map_area_w, dot_gap):
            for gy in range(0, self.map_area_h, dot_gap):
                alpha = int(
                    25 + 12 * math.sin(t * 0.4 + gx * 0.04 + gy * 0.04)
                )
                s = pygame.Surface((3, 3), pygame.SRCALPHA)
                s.fill((WIRE_COLOR[0], WIRE_COLOR[1], WIRE_COLOR[2], alpha))
                self.screen.blit(s, (gx, gy))

    def _draw_map(self) -> None:
        t = time.time() - self._time_start
        now = time.time()
        self._active_edges = [
            (p1, p2, e, c) for p1, p2, e, c in self._active_edges if e > now
        ]

        def edge_key(
            pt1: tuple[float, float],
            pt2: tuple[float, float]
        ) -> tuple[int, int, int, int]:
            return (
                round(pt1[0]), round(pt1[1]), round(pt2[0]), round(pt2[1])
            )

        active_map: dict[tuple[int, int, int, int], tuple[int, int, int]] = {}
        for p1, p2, _, col in self._active_edges:
            k1 = edge_key(p1, p2)
            k2 = edge_key(p2, p1)
            active_map[k1] = col
            active_map[k2] = col

        for zone_obj, neighbors in self.parser.graph.items():
            sp = (
                float(zone_obj.x * self.cell_size + self.offset_x),
                float(zone_obj.y * self.cell_size + self.offset_y)
            )
            for nb_tuple in neighbors:
                nb = nb_tuple[0]
                ep = (
                    float(nb.x * self.cell_size + self.offset_x),
                    float(nb.y * self.cell_size + self.offset_y)
                )
                k = edge_key(sp, ep)
                if k in active_map:
                    RenderUtils.draw_glow_line(
                        self.screen, active_map[k], sp, ep, width=3, alpha=180
                    )
                else:
                    pygame.draw.line(self.screen, WIRE_COLOR, sp, ep, 2)

        for zone in self.parser.zones:
            pos = (
                int(zone.x * self.cell_size + self.offset_x),
                int(zone.y * self.cell_size + self.offset_y)
            )

            if zone.color in ZONE_COLORS:
                zc = ZONE_COLORS[zone.color]
            elif zone.color:
                try:
                    c_obj = pygame.Color(zone.color)
                    zc = (c_obj.r, c_obj.g, c_obj.b)
                except ValueError:
                    zc = (120, 120, 120)
            else:
                zc = (120, 120, 120)

            pulse = 0.5 + 0.5 * math.sin(t * 2.0 + zone.x + zone.y)

            if hasattr(zone, 'cost') and zone.cost == 2:
                warn_alpha = int(40 + 30 * abs(math.sin(t * 3.0)))
                RenderUtils.draw_glow(
                    self.screen, NEON_ORANGE,
                    (float(pos[0]), float(pos[1])), 26,
                    layers=4, alpha_start=warn_alpha
                )

            RenderUtils.draw_glow(
                self.screen, zc,
                (float(pos[0]), float(pos[1])), 22,
                layers=6, alpha_start=int(40 + 30 * pulse)
            )
            pygame.draw.circle(self.screen, zc, pos, 22)
            pygame.draw.circle(self.screen, BG_DARK, pos, 16)
            pygame.draw.circle(self.screen, zc, pos, 16, 2)

            if hasattr(zone, 'cost') and zone.cost == 2:
                badge = self.font_small.render("2T", True, NEON_ORANGE)
                self.screen.blit(badge, (pos[0] + 14, pos[1] - 30))

            lbl = self.font_body.render(zone.name, True, TEXT_BRIGHT)
            self.screen.blit(
                lbl,
                (pos[0] - lbl.get_width() // 2, pos[1] - 42)
            )

    def _draw_drones(self) -> None:
        t = time.time() - self._time_start
        for drs in self._drone_render:
            drs.update()
            pos = (int(drs.px), int(drs.py))
            c = drs.colour

            for ti, (tx, ty) in enumerate(drs._trail):
                alpha = int(80 * (ti + 1) / len(drs._trail))
                radius = 4 + ti
                s = pygame.Surface((radius * 2 + 2, radius * 2 + 2),
                                   pygame.SRCALPHA)
                pygame.draw.circle(
                    s,
                    (c[0], c[1], c[2], alpha),
                    (radius + 1, radius + 1),
                    radius
                )
                self.screen.blit(
                    s,
                    (int(tx) - radius - 1, int(ty) - radius - 1)
                )

            if drs.is_in_transit:
                pulse_r = int(20 + 6 * abs(math.sin(t * 4.0)))
                RenderUtils.draw_glow(
                    self.screen, NEON_ORANGE,
                    (float(pos[0]), float(pos[1])), pulse_r,
                    layers=4, alpha_start=100
                )
                pygame.draw.circle(self.screen, NEON_ORANGE, pos, pulse_r, 2)
                hold_lbl = self.font_small.render("HOLD", True, NEON_ORANGE)
                self.screen.blit(
                    hold_lbl,
                    (pos[0] - hold_lbl.get_width() // 2, pos[1] - 38)
                )
            else:
                pulse = 0.6 + 0.4 * math.sin(t * 3.0 + drs.index)
                RenderUtils.draw_glow(
                    self.screen, c,
                    (float(pos[0]), float(pos[1])), 14,
                    layers=5, alpha_start=int(80 * pulse)
                )

            body_col = NEON_ORANGE if drs.is_in_transit else c
            pygame.draw.circle(self.screen, body_col, pos, 14)
            pygame.draw.circle(self.screen, BG_DARK, pos, 9)

            if drs.is_moving:
                pygame.draw.circle(self.screen, (255, 255, 255), pos, 17, 2)

            text_col = BG_DARK if drs.is_in_transit else body_col
            id_lbl = self.font_small.render(str(drs.drone.id), True, text_col)
            self.screen.blit(
                id_lbl,
                (pos[0] - id_lbl.get_width() // 2,
                 pos[1] - id_lbl.get_height() // 2)
            )

    def _draw_hud(self) -> None:
        t = time.time() - self._time_start
        by = self.map_area_h

        panel = pygame.Surface((self.width, self.HUD_H), pygame.SRCALPHA)
        panel.fill((PANEL_BG[0], PANEL_BG[1], PANEL_BG[2], 230))
        self.screen.blit(panel, (0, by))
        RenderUtils.draw_glow_line(
            self.screen, NEON_CYAN,
            (0.0, float(by)), (float(self.width), float(by)),
            width=1, alpha=160
        )

        col_pad = 30
        col_w = self.width // 4

        cx, cy = col_pad, by + 16
        self.screen.blit(
            self.font_small.render("TURN", True, TEXT_DIM), (cx, cy)
        )
        cy += 16
        tc = self.font_huge.render(str(self.turn), True, NEON_YELLOW)
        self.screen.blit(tc, (cx, cy))
        cy += tc.get_height() + 6
        status_txt = "AUTO-RUN" if self.auto_run else "PAUSED"
        status_col = NEON_GREEN if self.auto_run else NEON_RED
        if not self.auto_run and int(t * 2) % 2 == 0:
            status_col = TEXT_DIM
        self.screen.blit(
            self.font_body.render(f"[ {status_txt} ]", True, status_col),
            (cx, cy)
        )
        cy += 22
        self.screen.blit(
            self.font_small.render(
                f"Interval: {self.auto_interval:.1f}s", True, TEXT_DIM
            ),
            (cx, cy)
        )
        pygame.draw.line(
            self.screen, PANEL_BORDER,
            (col_w, by + 10), (col_w, by + self.HUD_H - 10), 1
        )

        cx, cy = col_w + col_pad, by + 16
        self.screen.blit(
            self.font_small.render("DRONES", True, TEXT_DIM), (cx, cy)
        )
        cy += 18
        sub_col_w = (col_w - col_pad * 2) // 2
        for idx, drs in enumerate(self._drone_render):
            drone = drs.drone
            c = drs.colour
            zone_name = drone.curr_zone.name if drone.curr_zone else "—"
            row_x = cx + (idx % 2) * sub_col_w
            row_y = cy + (idx // 2) * 22

            pygame.draw.circle(self.screen, c, (row_x + 6, row_y + 7), 5)
            pygame.draw.circle(
                self.screen, BG_DARK, (row_x + 6, row_y + 7), 3
            )

            if drs.is_in_transit:
                tag = " [HOLD]"
                tag_col = NEON_ORANGE
            elif drs.is_moving:
                tag = " [MOVE]"
                tag_col = NEON_YELLOW
            else:
                tag = ""
                tag_col = TEXT_BRIGHT

            ll = self.font_small.render(
                f"D{drone.id} -> {zone_name}", True, TEXT_BRIGHT
            )
            self.screen.blit(ll, (row_x + 16, row_y))
            if tag:
                tl = self.font_small.render(tag, True, tag_col)
                self.screen.blit(tl, (row_x + 16 + ll.get_width(), row_y))

        pygame.draw.line(
            self.screen, PANEL_BORDER,
            (col_w * 2, by + 10), (col_w * 2, by + self.HUD_H - 10), 1
        )

        cx, cy = col_w * 2 + col_pad, by + 16
        self.screen.blit(
            self.font_small.render("EVENT LOG", True, TEXT_DIM), (cx, cy)
        )
        cy += 18
        visible = self._log[-self.LOG_MAX:]
        for li, line in enumerate(visible):
            age = len(visible) - li
            alpha = max(70, 255 - age * 20)
            if "[SYS]" in line:
                col = NEON_CYAN
            elif "No movement" in line:
                col = NEON_RED
            elif "HOLD" in line or "blocked" in line.lower():
                col = NEON_ORANGE
            else:
                col = TEXT_BRIGHT
            ll_log = self.font_small.render(line[:48], True, col)
            faded = pygame.Surface(ll_log.get_size(), pygame.SRCALPHA)
            faded.blit(ll_log, (0, 0))
            faded.set_alpha(alpha)
            self.screen.blit(faded, (cx, cy))
            cy += 15
        pygame.draw.line(
            self.screen, PANEL_BORDER,
            (col_w * 3, by + 10), (col_w * 3, by + self.HUD_H - 10), 1
        )

        cx, cy = col_w * 3 + col_pad, by + 16
        self.screen.blit(
            self.font_small.render("CONTROLS", True, TEXT_DIM), (cx, cy)
        )
        cy += 18

        controls = [
            ("SPACE", "Step one turn"),
            ("P", "Toggle auto-run"),
            ("+", "Speed up"),
            ("-", "Slow down"),
            ("ESC", "Quit")
        ]
        for key, desc in controls:
            self.screen.blit(
                self.font_small.render(f"{key:<7}", True, NEON_CYAN),
                (cx, cy)
            )
            self.screen.blit(
                self.font_small.render(desc, True, TEXT_BRIGHT),
                (cx + 70, cy)
            )
            cy += 17
        cy += 8
        self.screen.blit(
            self.font_small.render("LEGEND", True, TEXT_DIM), (cx, cy)
        )
        cy += 16
        pygame.draw.circle(self.screen, NEON_ORANGE, (cx + 8, cy + 7), 6)
        self.screen.blit(
            self.font_small.render("  Cost-2 zone (2 turns)",
                                   True, TEXT_BRIGHT),
            (cx + 8, cy)
        )
        cy += 16
        pygame.draw.circle(self.screen, NEON_ORANGE, (cx + 8, cy + 7), 6, 2)
        self.screen.blit(
            self.font_small.render("  Drone in HOLD", True, TEXT_BRIGHT),
            (cx + 8, cy)
        )

    def _draw_fps(self) -> None:
        fps = self.font_small.render(
            f"FPS {int(self.clock.get_fps())}", True, TEXT_DIM
        )
        self.screen.blit(fps, (8, self.map_area_h - 20))

    def run(self) -> None:
        print("\n─── Drone Swarm Visualizer ─────────────────────────────────")
        print("  SPACE = step | P = auto-run | +/- = speed | ESC = quit")
        print("  Orange glow = cost-2 zone  |  HOLD = drone mid-transit")
        print("────────────────────────────────────────────────────────────\n")

        while self.running:
            now = time.time()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_SPACE:
                        self._step_simulation()
                    elif event.key == pygame.K_p:
                        self.auto_run = not self.auto_run
                        status = "ON" if self.auto_run else "OFF"
                        self._log_event(f"[SYS] Auto-run {status}")
                    elif event.key in (
                        pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS
                    ):
                        self.auto_interval = max(0.2, self.auto_interval - 0.2)
                    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.auto_interval = min(5.0, self.auto_interval + 0.2)

            if self.auto_run and (now - self._last_auto >= self.auto_interval):
                self._step_simulation()
                self._last_auto = now

            self._draw_background()
            self._draw_map()
            self._draw_drones()
            self._draw_hud()
            self._draw_fps()
            pygame.display.flip()
            self.clock.tick(90)

        pygame.quit()
