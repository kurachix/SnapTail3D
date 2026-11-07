"""
Card Lateral de Inspeção Microscópica de 1 Dente (Seção 5.3.3 da Documentação).
Papel do Módulo: Renderizar em tempo real o zoom de 1 dente Dovetail com as duas metades (Macho/Fêmea),
os fillets tangentes C1, os centros invariantes Ci (LF04) e a folga azul real (±δ, RN05).
"""

import tkinter as tk
from typing import List
from geometry.dovetail_math import construir_curva_offset
from models.cut_line import Point2D
from models.dovetail_params import DovetailParams
from ui.theme import THEME


class ToothPreviewCanvas(tk.Canvas):
    """
    Mini-canvas CAD que exibe o zoom de 1 dente rabo de andorinha, destacando:
    - Metade A (Macho inferior) e Metade B (Fêmea superior)
    - Canal da Folga Perpendicular Uniforme (RN05) em Ciano Técnico (#06B6D4)
    - Centros de curvatura invariantes Ci dos Fillets C1 (RN04, LF04)
    - Cotas dinâmicas (W_head, W_neck, H, Passo P e Folga)
    """

    def __init__(self, master: tk.Widget, width: int = 310, height: int = 165, **kwargs) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            bg=THEME.BG_CANVAS,
            highlightthickness=1,
            highlightbackground=THEME.BORDER_SUBTLE,
            **kwargs,
        )
        self._params = DovetailParams()
        self.bind("<Configure>", lambda _e: self.redraw(self._params))

    def redraw(self, params: DovetailParams) -> None:
        """Atualiza o desenho do dente com os parâmetros ativos."""
        self._params = params
        self.delete("all")

        w = max(220, self.winfo_width())
        h = max(130, self.winfo_height())

        # Parâmetros geométricos do dente único centrado em s = 0
        w_head = params.head_width_mm
        w_neck = params.neck_width_mm
        tooth_h = params.height_mm
        s_span = max(w_head * 0.95, 10.0)

        # Para que a folga de 0.14..0.25 mm seja nitidamente visível no card de inspeção CAD,
        # usamos amplificação visual proporcional ao slider de folga (mantendo a geometria analítica LF04)
        visual_delta = max(0.18, params.delta_offset_mm * 2.8)
        temp_params = DovetailParams(
            height_mm=params.height_mm,
            neck_width_mm=params.neck_width_mm,
            angle_deg=params.angle_deg,
            fillet_radius_mm=params.fillet_radius_mm,
            clearance_mm=params.clearance_mm,
            invert_side=False,
        )

        curve_center = construir_curva_offset(
            teeth_s=[0.0],
            s_start=-s_span,
            s_end=+s_span,
            params=temp_params,
            delta_offset=0.0,
            cut_line=None,
            subsegments_per_arc=16,
        )
        curve_a = construir_curva_offset(
            teeth_s=[0.0],
            s_start=-s_span,
            s_end=+s_span,
            params=temp_params,
            delta_offset=-visual_delta,
            cut_line=None,
            subsegments_per_arc=16,
        )
        curve_b = construir_curva_offset(
            teeth_s=[0.0],
            s_start=-s_span,
            s_end=+s_span,
            params=temp_params,
            delta_offset=+visual_delta,
            cut_line=None,
            subsegments_per_arc=16,
        )

        # Escala automática para caber com folga no mini-canvas
        model_w = 2.0 * s_span
        model_h = tooth_h + 7.0
        scale_x = (w - 36.0) / max(1.0, model_w)
        scale_y = (h - 52.0) / max(1.0, model_h)
        scale = min(scale_x, scale_y)

        cx = w * 0.5
        base_y = h - 32.0

        def to_px(pt: Point2D) -> Point2D:
            return (cx + pt[0] * scale, base_y - pt[1] * scale)

        # Grade técnica de fundo
        for gx in range(0, w, 24):
            self.create_line(gx, 0, gx, h, fill=THEME.GRID_MINOR)
        for gy in range(0, h, 24):
            self.create_line(0, gy, w, gy, fill=THEME.GRID_MINOR)

        # Polígono preenchido da Metade B (Superior — Fêmea)
        top_y_mm = tooth_h + 3.2
        poly_b_px: List[float] = []
        for pt in curve_b.polyline_points:
            px, py = to_px(pt)
            poly_b_px.extend([px, py])
        p_tr = to_px((+s_span, top_y_mm))
        p_tl = to_px((-s_span, top_y_mm))
        poly_b_px.extend([p_tr[0], p_tr[1], p_tl[0], p_tl[1]])
        if len(poly_b_px) >= 6:
            self.create_polygon(poly_b_px, fill="#152238", outline="")

        # Polígono preenchido da Metade A (Inferior — Macho)
        bot_y_mm = -2.8
        poly_a_px: List[float] = []
        for pt in curve_a.polyline_points:
            px, py = to_px(pt)
            poly_a_px.extend([px, py])
        p_br = to_px((+s_span, bot_y_mm))
        p_bl = to_px((-s_span, bot_y_mm))
        poly_a_px.extend([p_br[0], p_br[1], p_bl[0], p_bl[1]])
        if len(poly_a_px) >= 6:
            self.create_polygon(poly_a_px, fill="#1E293B", outline="")

        # Faixa da Folga Azul Real (RN05: Canal entre Curva A e Curva B)
        gap_poly_px: List[float] = []
        for pt in curve_a.polyline_points:
            px, py = to_px(pt)
            gap_poly_px.extend([px, py])
        for pt in reversed(curve_b.polyline_points):
            px, py = to_px(pt)
            gap_poly_px.extend([px, py])
        if len(gap_poly_px) >= 6:
            self.create_polygon(gap_poly_px, fill="#083344", outline="")

        # Traçado das curvas de parede A (Verde Esmeralda) e B (Ciano Técnico)
        line_b_px: List[float] = []
        for pt in curve_b.polyline_points:
            line_b_px.extend(to_px(pt))
        if len(line_b_px) >= 4:
            self.create_line(line_b_px, fill=THEME.ACCENT_CYAN, width=2, smooth=False)

        line_a_px: List[float] = []
        for pt in curve_a.polyline_points:
            line_a_px.extend(to_px(pt))
        if len(line_a_px) >= 4:
            self.create_line(line_a_px, fill=THEME.STATUS_OK, width=2, smooth=False)

        # Centros invariantes Ci dos Fillets C1 (LF04)
        for arc in curve_center.arcs:
            c_px, c_py = to_px(arc.center)
            self.create_oval(
                c_px - 2, c_py - 2, c_px + 2, c_py + 2,
                fill=THEME.ACCENT_CYAN, outline=""
            )

        # Cota de Largura da Cabeça (W_head) no topo
        head_l = to_px((-w_head * 0.5, tooth_h))
        head_r = to_px((+w_head * 0.5, tooth_h))
        dim_y = max(20.0, head_l[1] - 12.0)
        self.create_line(head_l[0], dim_y, head_r[0], dim_y, fill=THEME.TEXT_PRIMARY, width=1, arrow=tk.BOTH)
        self.create_text(
            cx,
            dim_y - 8,
            text=f"W_head = {w_head:.1f} mm",
            fill=THEME.TEXT_PRIMARY,
            font=(THEME.FONT_MONO, 8, "bold"),
        )

        # Cota de Largura do Pescoço (W_neck) na base
        neck_l = to_px((-w_neck * 0.5, 0.0))
        neck_r = to_px((+w_neck * 0.5, 0.0))
        dim_ny = min(h - 16.0, neck_l[1] + 13.0)
        self.create_line(neck_l[0], dim_ny, neck_r[0], dim_ny, fill=THEME.TEXT_SECONDARY, width=1, arrow=tk.BOTH)
        self.create_text(
            cx,
            dim_ny + 8,
            text=f"W_neck = {w_neck:.1f} mm | P = {params.pitch_mm:.1f} mm",
            fill=THEME.TEXT_SECONDARY,
            font=(THEME.FONT_MONO, 8),
        )

        # Badge superior de Folga Real e Raio Efetivo
        self.create_text(
            8,
            10,
            anchor="w",
            text=f"PREVIEW 1 DENTE (C1 R={params.effective_fillet_radius_mm:.2f}mm)",
            fill=THEME.TEXT_SECONDARY,
            font=(THEME.FONT_FAMILY, 8, "bold"),
        )
        self.create_text(
            w - 8,
            10,
            anchor="e",
            text=f"Folga 2δ: {params.clearance_mm:.2f} mm",
            fill=THEME.ACCENT_CYAN,
            font=(THEME.FONT_MONO, 8, "bold"),
        )

