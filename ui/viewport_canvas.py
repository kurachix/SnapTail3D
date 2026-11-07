"""
Viewport CAD 2D Interativo com Traçado Ao Vivo Click & Drag e HUD de Telemetria (Seções 5.2 e 5.3).
Papel do Módulo: Renderizar a peça, a mesa da impressora, os furos protegidos (RN01), os dentes
dovetail ativos, zonas de furos desviados e o HUD de validação (RN06, RN07).
"""

import math
import tkinter as tk
from typing import Callable, List, Optional, Tuple
from config.printer_profiles import PrinterProfile
from models.cut_line import CutLine, Point2D
from models.dovetail_params import DovetailParams
from models.part_model import PartModel
from models.validation_report import CutValidationReport
from ui.theme import THEME


class ViewportCanvas(tk.Canvas):
    """
    Canvas principal do Dovetail Studio 3D.
    Suporta:
    - Arrastar pontos P1 e P2 ou o ponto central M da linha de corte
    - Clique e arraste livre (Click & Drag) para traçar uma nova linha de corte
    - Zoom com roda do mouse e Pan com botão direito/meio
    """

    HANDLE_RADIUS_PX = 8.0

    def __init__(
        self,
        master: tk.Widget,
        on_cut_line_changed: Callable[[CutLine], None],
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            bg=THEME.BG_CANVAS,
            highlightthickness=1,
            highlightbackground=THEME.BORDER_SUBTLE,
            cursor="crosshair",
            **kwargs,
        )
        self._on_cut_line_changed = on_cut_line_changed

        self._part: Optional[PartModel] = None
        self._cut_line: Optional[CutLine] = None
        self._params: Optional[DovetailParams] = None
        self._printer: Optional[PrinterProfile] = None
        self._report: Optional[CutValidationReport] = None

        # Estado de câmera (Zoom e Pan)
        self._zoom: float = 2.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._camera_initialized: bool = False

        # Estado de interação do mouse
        self._drag_mode: Optional[str] = None  # "p1", "p2", "mid", "new_line", "pan"
        self._drag_start_px: Point2D = (0.0, 0.0)
        self._drag_start_p1: Point2D = (0.0, 0.0)
        self._drag_start_p2: Point2D = (0.0, 0.0)

        self.bind("<Configure>", self._on_resize)
        self.bind("<ButtonPress-1>", self._on_left_down)
        self.bind("<B1-Motion>", self._on_left_drag)
        self.bind("<ButtonRelease-1>", self._on_left_up)
        self.bind("<ButtonPress-2>", self._on_pan_start)
        self.bind("<B2-Motion>", self._on_pan_drag)
        self.bind("<ButtonPress-3>", self._on_pan_start)
        self.bind("<B3-Motion>", self._on_pan_drag)
        self.bind("<MouseWheel>", self._on_mouse_wheel)

    def set_scene(
        self,
        part: PartModel,
        cut_line: CutLine,
        params: DovetailParams,
        printer: PrinterProfile,
        report: CutValidationReport,
        reset_camera: bool = False,
    ) -> None:
        """Atualiza os dados da cena e redesenha o viewport."""
        self._part = part
        self._cut_line = cut_line
        self._params = params
        self._printer = printer
        self._report = report

        if reset_camera or not self._camera_initialized:
            self.fit_view_to_scene()
        else:
            self.redraw()

    def fit_view_to_scene(self) -> None:
        """Centraliza e ajusta o zoom para enquadrar a peça e a mesa da impressora."""
        if self._part is None:
            return
        w = max(400, self.winfo_width())
        h = max(320, self.winfo_height())

        bed_x = self._printer.bed_x_mm if self._printer else 256.0
        bed_y = self._printer.bed_y_mm if self._printer else 256.0
        span_x = max(self._part.bbox.size_x, bed_x) * 1.22
        span_y = max(self._part.bbox.size_y, bed_y) * 1.28

        self._zoom = min((w - 60.0) / max(10.0, span_x), (h - 90.0) / max(10.0, span_y))
        cx, cy = self._part.bbox.center_2d
        self._pan_x = w * 0.5 - cx * self._zoom
        self._pan_y = (h - 35.0) * 0.5 + cy * self._zoom
        self._camera_initialized = True
        self.redraw()

    def world_to_screen(self, x: float, y: float) -> Point2D:
        return (self._pan_x + x * self._zoom, self._pan_y - y * self._zoom)

    def screen_to_world(self, sx: float, sy: float) -> Point2D:
        return ((sx - self._pan_x) / self._zoom, (self._pan_y - sy) / self._zoom)

    def _on_resize(self, _event: tk.Event) -> None:
        if not self._camera_initialized and self._part is not None:
            self.fit_view_to_scene()
        else:
            self.redraw()

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        factor = 1.12 if event.delta > 0 else (1.0 / 1.12)
        new_zoom = max(0.35, min(18.0, self._zoom * factor))
        wx, wy = self.screen_to_world(event.x, event.y)
        self._zoom = new_zoom
        self._pan_x = event.x - wx * self._zoom
        self._pan_y = event.y + wy * self._zoom
        self.redraw()

    def _on_pan_start(self, event: tk.Event) -> None:
        self._drag_mode = "pan"
        self._drag_start_px = (float(event.x), float(event.y))

    def _on_pan_drag(self, event: tk.Event) -> None:
        if self._drag_mode != "pan":
            return
        dx = float(event.x) - self._drag_start_px[0]
        dy = float(event.y) - self._drag_start_px[1]
        self._pan_x += dx
        self._pan_y += dy
        self._drag_start_px = (float(event.x), float(event.y))
        self.redraw()

    def _on_left_down(self, event: tk.Event) -> None:
        if self._cut_line is None:
            return
        sx, sy = float(event.x), float(event.y)
        p1_s = self.world_to_screen(*self._cut_line.p1)
        p2_s = self.world_to_screen(*self._cut_line.p2)
        mid_s = self.world_to_screen(*self._cut_line.origin)

        hit_r = self.HANDLE_RADIUS_PX + 5.0
        if math.hypot(sx - p1_s[0], sy - p1_s[1]) <= hit_r:
            self._drag_mode = "p1"
        elif math.hypot(sx - p2_s[0], sy - p2_s[1]) <= hit_r:
            self._drag_mode = "p2"
        elif math.hypot(sx - mid_s[0], sy - mid_s[1]) <= hit_r:
            self._drag_mode = "mid"
            self._drag_start_px = (sx, sy)
            self._drag_start_p1 = self._cut_line.p1
            self._drag_start_p2 = self._cut_line.p2
        else:
            # Traçado Livre Click & Drag (Seção 5.3.1)
            self._drag_mode = "new_line"
            w_pt = self.screen_to_world(sx, sy)
            self._drag_start_p1 = w_pt

    def _on_left_drag(self, event: tk.Event) -> None:
        if self._cut_line is None or self._drag_mode is None:
            return
        sx, sy = float(event.x), float(event.y)
        w_pt = self.screen_to_world(sx, sy)

        if self._drag_mode == "p1":
            if math.hypot(w_pt[0] - self._cut_line.p2[0], w_pt[1] - self._cut_line.p2[1]) > 5.0:
                new_line = CutLine(p1=w_pt, p2=self._cut_line.p2, invert_normal=self._cut_line.invert_normal)
                self._on_cut_line_changed(new_line)
        elif self._drag_mode == "p2":
            if math.hypot(w_pt[0] - self._cut_line.p1[0], w_pt[1] - self._cut_line.p1[1]) > 5.0:
                new_line = CutLine(p1=self._cut_line.p1, p2=w_pt, invert_normal=self._cut_line.invert_normal)
                self._on_cut_line_changed(new_line)
        elif self._drag_mode == "mid":
            w_start = self.screen_to_world(*self._drag_start_px)
            dx = w_pt[0] - w_start[0]
            dy = w_pt[1] - w_start[1]
            new_p1 = (self._drag_start_p1[0] + dx, self._drag_start_p1[1] + dy)
            new_p2 = (self._drag_start_p2[0] + dx, self._drag_start_p2[1] + dy)
            new_line = CutLine(p1=new_p1, p2=new_p2, invert_normal=self._cut_line.invert_normal)
            self._on_cut_line_changed(new_line)
        elif self._drag_mode == "new_line":
            if math.hypot(w_pt[0] - self._drag_start_p1[0], w_pt[1] - self._drag_start_p1[1]) > 8.0:
                new_line = CutLine(
                    p1=self._drag_start_p1,
                    p2=w_pt,
                    invert_normal=self._cut_line.invert_normal,
                )
                self._on_cut_line_changed(new_line)

    def _on_left_up(self, _event: tk.Event) -> None:
        self._drag_mode = None

    def redraw(self) -> None:
        """Renderiza todas as camadas do Viewport CAD e o HUD de telemetria."""
        self.delete("all")
        if self._part is None or self._cut_line is None or self._report is None:
            return

        w = max(300, self.winfo_width())
        h = max(250, self.winfo_height())

        self._draw_grid(w, h)
        self._draw_printer_bed()
        self._draw_part_geometry()
        self._draw_tooth_envelopes_and_avoided_holes()
        self._draw_dovetail_seam()
        self._draw_handles()
        self._draw_hud_overlay(w, h)

    def _draw_grid(self, w: int, h: int) -> None:
        """Desenha a grade milimétrica de engenharia (10 mm e 50 mm)."""
        wx0, wy1 = self.screen_to_world(0, 0)
        wx1, wy0 = self.screen_to_world(w, h)

        step_minor = 10.0 if self._zoom >= 1.2 else 25.0
        step_major = 50.0

        start_x = math.floor(wx0 / step_minor) * step_minor
        curr_x = start_x
        while curr_x <= wx1:
            sx, _ = self.world_to_screen(curr_x, 0.0)
            is_major = abs(curr_x % step_major) < 1e-3
            color = THEME.GRID_MAJOR if is_major else THEME.GRID_MINOR
            self.create_line(sx, 0, sx, h, fill=color)
            curr_x += step_minor

        start_y = math.floor(wy0 / step_minor) * step_minor
        curr_y = start_y
        while curr_y <= wy1:
            _, sy = self.world_to_screen(0.0, curr_y)
            is_major = abs(curr_y % step_major) < 1e-3
            color = THEME.GRID_MAJOR if is_major else THEME.GRID_MINOR
            self.create_line(0, sy, w, sy, fill=color)
            curr_y += step_minor

    def _draw_printer_bed(self) -> None:
        """Desenha o contorno da mesa da impressora selecionada e a área útil (RN06)."""
        if self._printer is None or self._part is None:
            return
        cx, cy = self._part.bbox.center_2d
        bx = self._printer.bed_x_mm * 0.5
        by = self._printer.bed_y_mm * 0.5
        ux = self._printer.usable_x_mm * 0.5
        uy = self._printer.usable_y_mm * 0.5

        b_tl = self.world_to_screen(cx - bx, cy + by)
        b_br = self.world_to_screen(cx + bx, cy - by)
        self.create_rectangle(
            b_tl[0], b_tl[1], b_br[0], b_br[1],
            outline="#334155", width=1, dash=(6, 4)
        )

        u_tl = self.world_to_screen(cx - ux, cy + uy)
        u_br = self.world_to_screen(cx + ux, cy - uy)
        self.create_rectangle(
            u_tl[0], u_tl[1], u_br[0], u_br[1],
            outline="#1E3A8A", width=1, dash=(3, 3)
        )
        self.create_text(
            b_tl[0] + 8,
            b_tl[1] + 12,
            anchor="w",
            text=f"Mesa {self._printer.name}: {int(self._printer.bed_x_mm)}×{int(self._printer.bed_y_mm)} mm (Útil: {int(self._printer.usable_x_mm)}×{int(self._printer.usable_y_mm)} mm)",
            fill=THEME.TEXT_MUTED,
            font=(THEME.FONT_FAMILY, 8, "bold"),
        )

    def _draw_part_geometry(self) -> None:
        """Renderiza a silhueta da peça e seus furos internos com halo de proteção RN01."""
        assert self._part is not None
        margin_wall = self._params.margin_wall_mm if self._params else 1.6

        for poly in self._part.all_outer_polygons:
            pts_px: List[float] = []
            for wx, wy in poly:
                pts_px.extend(self.world_to_screen(wx, wy))
            if len(pts_px) >= 6:
                self.create_polygon(
                    pts_px,
                    fill=THEME.PART_FILL,
                    outline=THEME.PART_OUTLINE,
                    width=2,
                )

        for hole in self._part.holes:
            hx, hy = hole.center
            r = hole.radius_mm
            r_safe = r + margin_wall

            # Halo tracejado de proteção RN01 (MARGEM_PAREDE)
            s_tl = self.world_to_screen(hx - r_safe, hy + r_safe)
            s_br = self.world_to_screen(hx + r_safe, hy - r_safe)
            self.create_oval(
                s_tl[0], s_tl[1], s_br[0], s_br[1],
                outline="#78350F", width=1, dash=(2, 2)
            )

            # Furo real
            h_tl = self.world_to_screen(hx - r, hy + r)
            h_br = self.world_to_screen(hx + r, hy - r)
            self.create_oval(
                h_tl[0], h_tl[1], h_br[0], h_br[1],
                fill=THEME.HOLE_FILL,
                outline=THEME.HOLE_OUTLINE,
                width=1.5,
            )

    def _draw_tooth_envelopes_and_avoided_holes(self) -> None:
        """Renderiza os envelopes verdes dos dentes aprovados e alertas âmbar de furos desviados (RN01)."""
        assert self._report is not None

        # Envelopes aprovados (Verde Esmeralda sutil)
        for info in self._report.active_teeth_info:
            env_px: List[float] = []
            for wx, wy in info.envelope_polygon:
                env_px.extend(self.world_to_screen(wx, wy))
            if len(env_px) >= 6:
                self.create_polygon(
                    env_px,
                    fill="#064E3B",
                    stipple="gray25",
                    outline="#059669",
                    width=1,
                )

        # Posições onde a RN01 suprimiu dentes automaticamente para desviar de furos
        for h_info in self._report.avoided_holes_info:
            env_px = []
            for wx, wy in h_info.envelope_polygon:
                env_px.extend(self.world_to_screen(wx, wy))
            if len(env_px) >= 6:
                self.create_polygon(
                    env_px,
                    fill="",
                    outline=THEME.STATUS_WARN,
                    width=1.5,
                    dash=(3, 2),
                )
            cx_s, cy_s = self.world_to_screen(*h_info.global_center)
            self.create_text(
                cx_s,
                cy_s - 14,
                text="[Furo Desviado]",
                fill=THEME.STATUS_WARN,
                font=(THEME.FONT_FAMILY, 8, "bold"),
            )

    def _draw_dovetail_seam(self) -> None:
        """Desenha a linha de corte e as curvas analíticas Macho/Fêmea com dentes arredondados."""
        assert self._report is not None and self._cut_line is not None

        # Linha guia estendida entre P1 e P2
        p1_s = self.world_to_screen(*self._cut_line.p1)
        p2_s = self.world_to_screen(*self._cut_line.p2)
        self.create_line(
            p1_s[0], p1_s[1], p2_s[0], p2_s[1],
            fill="#334155", width=1, dash=(4, 4)
        )

        # Curva Offset B (+δ) em Ciano Técnico
        if len(self._report.offset_curve_b_points) >= 2:
            pts_b: List[float] = []
            for wx, wy in self._report.offset_curve_b_points:
                pts_b.extend(self.world_to_screen(wx, wy))
            self.create_line(pts_b, fill=THEME.ACCENT_CYAN, width=2)

        # Curva Offset A (-δ) em Verde Esmeralda
        if len(self._report.offset_curve_a_points) >= 2:
            pts_a: List[float] = []
            for wx, wy in self._report.offset_curve_a_points:
                pts_a.extend(self.world_to_screen(wx, wy))
            self.create_line(pts_a, fill=THEME.STATUS_OK, width=2)

    def _draw_handles(self) -> None:
        """Desenha as alças interativas P1, P2 e o ponto central M da linha de corte."""
        assert self._cut_line is not None
        r = self.HANDLE_RADIUS_PX

        for label, pt, color in (
            ("P1", self._cut_line.p1, THEME.ACCENT_CYAN),
            ("P2", self._cut_line.p2, THEME.ACCENT_BLUE),
        ):
            sx, sy = self.world_to_screen(*pt)
            self.create_oval(
                sx - r, sy - r, sx + r, sy + r,
                fill=THEME.BG_MAIN, outline=color, width=2.5
            )
            self.create_text(
                sx, sy - r - 9,
                text=label,
                fill=THEME.TEXT_PRIMARY,
                font=(THEME.FONT_MONO, 8, "bold"),
            )

        # Alça central de translação paralela
        mx, my = self.world_to_screen(*self._cut_line.origin)
        self.create_oval(
            mx - 5, my - 5, mx + 5, my + 5,
            fill=THEME.ACCENT_CYAN, outline=THEME.BG_MAIN, width=1.5
        )

    def _draw_hud_overlay(self, w: int, h: int) -> None:
        """Desenha o HUD flutuante de diagnóstico na base do Canvas (Seção 5.2)."""
        assert self._report is not None and self._params is not None
        rep = self._report

        # Banner de Alerta de Fragmentação Multi-Corpo (RN07) caso detectado
        if rep.has_fragmentation_warning:
            banner_h = 30
            self.create_rectangle(
                14, 38, w - 14, 38 + banner_h,
                fill=THEME.STATUS_ERR_BG, outline=THEME.STATUS_ERR, width=1.5
            )
            self.create_text(
                w * 0.5,
                38 + banner_h * 0.5,
                text=(
                    f"⚠ ALERTA DE FRAGMENTAÇÃO (RN07): Linha atravessa vão aberto e divide a peça em "
                    f"{rep.total_fragments} sólidos desconectados (A: {rep.half_a_nesting.num_fragments}, "
                    f"B: {rep.half_b_nesting.num_fragments})!"
                ),
                fill="#FCA5A5",
                font=(THEME.FONT_FAMILY, 9, "bold"),
            )

        # Caixa do HUD inferior
        hud_h = 54
        hud_y0 = h - hud_h - 10
        self.create_rectangle(
            12, hud_y0, w - 12, h - 10,
            fill=THEME.BG_PANEL, outline=THEME.BORDER_SUBTLE, width=1
        )

        teeth_color = THEME.STATUS_OK if rep.num_active_teeth > 0 else THEME.STATUS_ERR
        line1 = (
            f"[HUD] {rep.num_active_teeth} dentes ativos  |  "
            f"Furos desviados: {rep.num_avoided_holes}  |  "
            f"Ângulo: {rep.cut_angle_deg:+.1f}°  |  "
            f"W_head: {self._params.head_width_mm:.1f} mm  |  "
            f"Passo P: {self._params.pitch_mm:.1f} mm"
        )
        self.create_text(
            24, hud_y0 + 16,
            anchor="w",
            text=line1,
            fill=teeth_color,
            font=(THEME.FONT_MONO, 9, "bold"),
        )

        # Linha 2: Status individual da Metade A e Metade B na mesa (RN06)
        col_a = THEME.STATUS_OK if rep.half_a_nesting.fits_on_bed else THEME.STATUS_ERR
        col_b = THEME.STATUS_OK if rep.half_b_nesting.fits_on_bed else THEME.STATUS_ERR
        self.create_text(
            24, hud_y0 + 37,
            anchor="w",
            text=rep.half_a_nesting.status_summary,
            fill=col_a,
            font=(THEME.FONT_MONO, 8, "bold"),
        )
        self.create_text(
            w * 0.52, hud_y0 + 37,
            anchor="w",
            text=rep.half_b_nesting.status_summary,
            fill=col_b,
            font=(THEME.FONT_MONO, 8, "bold"),
        )

