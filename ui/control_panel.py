"""
Painel Lateral de Engenharia, Sliders de Precisão, Presets de Folga e Exportação (Seções 5.2 e 5.3).
Papel do Módulo: Permitir controle paramétrico em tempo real com travas automáticas das Regras de Negócio
(RN02, RN03, RN04, RN05) e acionar o Mini-Teste de Grip (RN10) ou Corte Completo (RN09).
"""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from typing import Callable
from config.settings import CLEARANCE_PRESETS, DEFAULT_OUTPUT_FOLDER_NAME, LIMITS
from models.dovetail_params import DovetailParams
from ui.theme import THEME
from ui.tooth_preview_canvas import ToothPreviewCanvas


class ControlPanel(tk.Frame):
    """Painel direito do Dovetail Studio 3D contendo preview do dente, sliders e ações de exportação."""

    def __init__(
        self,
        master: tk.Widget,
        initial_params: DovetailParams,
        on_params_changed: Callable[[DovetailParams], None],
        on_export_mini_test: Callable[[str], None],
        on_export_cut_pieces: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            bg=THEME.BG_PANEL,
             width=350,
            highlightthickness=1,
            highlightbackground=THEME.BORDER_SUBTLE,
            padx=12,
            pady=10,
            **kwargs,
        )
        self.pack_propagate(False)

        self._params = initial_params
        self._on_params_changed = on_params_changed
        self._on_export_mini_test = on_export_mini_test
        self._on_export_cut_pieces = on_export_cut_pieces
        self._updating_ui = False

        # Variáveis reativas dos sliders
        self.var_height = tk.DoubleVar(value=self._params.height_mm)
        self.var_neck = tk.DoubleVar(value=self._params.neck_width_mm)
        self.var_angle = tk.DoubleVar(value=self._params.angle_deg)
        self.var_radius = tk.DoubleVar(value=self._params.fillet_radius_mm)
        self.var_clearance = tk.DoubleVar(value=self._params.clearance_mm)
        self.var_output_dir = tk.StringVar(
            value=str((Path.cwd() / DEFAULT_OUTPUT_FOLDER_NAME).resolve())
        )

        self._build_widgets()
        self.refresh_from_params(self._params)

    def _build_widgets(self) -> None:
        # Título da Seção 1
        lbl_title = tk.Label(
            self,
            text="PARÂMETROS DO ENCAIXE (DOVETAIL)",
            bg=THEME.BG_PANEL,
            fg=THEME.TEXT_PRIMARY,
            font=(THEME.FONT_FAMILY, 10, "bold"),
            anchor="w",
        )
        lbl_title.pack(fill=tk.X, pady=(0, 6))

        # Mini-Canvas de Preview Zoom 1 Dente
        self.tooth_preview = ToothPreviewCanvas(self, width=320, height=160)
        self.tooth_preview.pack(fill=tk.X, pady=(0, 8))

        # Container de Sliders
        sliders_frame = tk.Frame(self, bg=THEME.BG_PANEL)
        sliders_frame.pack(fill=tk.X)

        self.lbl_val_height = self._create_slider_row(
            sliders_frame,
            "Altura do Dente (H)",
            self.var_height,
            LIMITS.ALTURA_DENTE_MIN_MM,
            LIMITS.ALTURA_DENTE_MAX_MM,
            0.2,
            "mm",
        )
        self.lbl_val_neck = self._create_slider_row(
            sliders_frame,
            "Largura Pescoço (W_neck)",
            self.var_neck,
            LIMITS.LARGURA_PESCOCO_MIN_MM,
            LIMITS.LARGURA_PESCOCO_MAX_MM,
            0.5,
            "mm",
        )
        self.lbl_val_angle = self._create_slider_row(
            sliders_frame,
            "Ângulo Dovetail (β — RN02)",
            self.var_angle,
            LIMITS.ANGULO_DOVETAIL_MIN_DEG,
            LIMITS.ANGULO_DOVETAIL_MAX_DEG,
            1.0,
            "°",
        )
        self.lbl_val_radius = self._create_slider_row(
            sliders_frame,
            "Raio do Canto (Fillet C1 — RN04)",
            self.var_radius,
            LIMITS.RAIO_CANTO_MIN_MM,
            2.4,
            0.05,
            "mm",
        )
        self.lbl_val_clearance = self._create_slider_row(
            sliders_frame,
            "Folga Normal 2δ (Grip — RN05)",
            self.var_clearance,
            LIMITS.FOLGA_MIN_MM,
            0.35,
            0.01,
            "mm",
        )

        # Presets de Folga (RN05)
        presets_row = tk.Frame(self, bg=THEME.BG_PANEL)
        presets_row.pack(fill=tk.X, pady=(4, 8))
        tk.Label(
            presets_row,
            text="Presets:",
            bg=THEME.BG_PANEL,
            fg=THEME.TEXT_SECONDARY,
            font=(THEME.FONT_FAMILY, 8, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 4))

        for label, val in CLEARANCE_PRESETS.items():
            btn = tk.Button(
                presets_row,
                text=label,
                bg=THEME.BG_CARD,
                fg=THEME.ACCENT_CYAN,
                activebackground=THEME.ACCENT_BLUE,
                activeforeground=THEME.TEXT_PRIMARY,
                relief=tk.FLAT,
                font=(THEME.FONT_FAMILY, 8, "bold"),
                padx=6,
                pady=3,
                cursor="hand2",
                command=lambda v=val: self._apply_clearance_preset(v),
            )
            btn.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        # Separador
        tk.Frame(self, bg=THEME.BORDER_SUBTLE, height=1).pack(fill=tk.X, pady=6)

        # Seção Pasta de Saída (RN09)
        tk.Label(
            self,
            text="PASTA DE SAÍDA (.STL + .STEP SINCRONIZADOS)",
            bg=THEME.BG_PANEL,
            fg=THEME.TEXT_PRIMARY,
            font=(THEME.FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 4))

        folder_row = tk.Frame(self, bg=THEME.BG_PANEL)
        folder_row.pack(fill=tk.X, pady=(0, 8))

        self.entry_folder = tk.Entry(
            folder_row,
            textvariable=self.var_output_dir,
            bg=THEME.BG_CARD,
            fg=THEME.TEXT_PRIMARY,
            insertbackground=THEME.TEXT_PRIMARY,
            relief=tk.FLAT,
            font=(THEME.FONT_MONO, 8),
        )
        self.entry_folder.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 4))

        btn_browse = tk.Button(
            folder_row,
            text="[...]",
            bg=THEME.BG_CARD,
            fg=THEME.TEXT_PRIMARY,
            activebackground=THEME.ACCENT_BLUE,
            relief=tk.FLAT,
            font=(THEME.FONT_MONO, 8, "bold"),
            padx=8,
             pady=3,
            cursor="hand2",
            command=self._choose_folder,
        )
        btn_browse.pack(side=tk.RIGHT)

        # Botão RN10: Corpo de Prova Rápido (Mini-Teste de Grip 10 min)
        self.btn_mini_test = tk.Button(
            self,
            text="🧪 Exportar Mini-Teste de Grip (10 min — 28×22×5 mm)",
            bg=THEME.BG_CARD,
            fg=THEME.ACCENT_CYAN,
            activebackground=THEME.ACCENT_BLUE_DARK,
            activeforeground=THEME.TEXT_PRIMARY,
            relief=tk.FLAT,
            font=(THEME.FONT_FAMILY, 9, "bold"),
            pady=7,
            cursor="hand2",
            command=lambda: self._on_export_mini_test(self.var_output_dir.get()),
        )
        self.btn_mini_test.pack(fill=tk.X, pady=(0, 6))

        # Botão Principal RN09: Cortar e Salvar Peças
        self.btn_cut_save = tk.Button(
            self,
            text="✂ CORTAR E SALVAR PEÇAS (.STL + .STEP)",
            bg=THEME.ACCENT_BLUE,
            fg=THEME.TEXT_PRIMARY,
            activebackground=THEME.ACCENT_CYAN,
            activeforeground=THEME.BG_MAIN,
            relief=tk.FLAT,
            font=(THEME.FONT_FAMILY, 10, "bold"),
            pady=9,
            cursor="hand2",
            command=lambda: self._on_export_cut_pieces(self.var_output_dir.get()),
        )
        self.btn_cut_save.pack(fill=tk.X, pady=(0, 6))

        # Caixa de Feedback / Log de Status
        self.lbl_status_box = tk.Label(
            self,
            text="Pronto. Arraste P1/P2 ou clique no desenho para traçar a linha de corte.",
            bg=THEME.BG_CARD,
            fg=THEME.TEXT_SECONDARY,
            font=(THEME.FONT_FAMILY, 8),
            justify=tk.LEFT,
            anchor="w",
            wraplength=315,
            padx=8,
            pady=6,
        )
        self.lbl_status_box.pack(fill=tk.X, pady=(2, 0))

    def _create_slider_row(
        self,
        parent: tk.Widget,
        title: str,
        variable: tk.DoubleVar,
        min_val: float,
        max_val: float,
        resolution: float,
        unit: str,
    ) -> tk.Label:
        container = tk.Frame(parent, bg=THEME.BG_PANEL)
        container.pack(fill=tk.X, pady=2)

        top = tk.Frame(container, bg=THEME.BG_PANEL)
        top.pack(fill=tk.X)
        tk.Label(
            top,
            text=title,
            bg=THEME.BG_PANEL,
            fg=THEME.TEXT_SECONDARY,
            font=(THEME.FONT_FAMILY, 8),
            anchor="w",
        ).pack(side=tk.LEFT)

        val_lbl = tk.Label(
            top,
            text=f"[{variable.get():.2f} {unit}]",
            bg=THEME.BG_PANEL,
            fg=THEME.ACCENT_CYAN,
            font=(THEME.FONT_MONO, 8, "bold"),
            anchor="e",
        )
        val_lbl.pack(side=tk.RIGHT)

        scale = tk.Scale(
            container,
            variable=variable,
            from_=min_val,
            to=max_val,
            resolution=resolution,
            orient=tk.HORIZONTAL,
            showvalue=False,
            bg=THEME.BG_PANEL,
            fg=THEME.TEXT_PRIMARY,
            troughcolor=THEME.BG_CARD,
            activebackground=THEME.ACCENT_CYAN,
            highlightthickness=0,
            bd=0,
            sliderlength=16,
            width=10,
            command=lambda _v: self._on_slider_moved(),
        )
        scale.pack(fill=tk.X)
        return val_lbl

    def _apply_clearance_preset(self, val: float) -> None:
        self.var_clearance.set(val)
        self._on_slider_moved()

    def _choose_folder(self) -> None:
        chosen = filedialog.askdirectory(
            initialdir=self.var_output_dir.get(),
            title="Escolher Pasta de Saída para Peças Cortadas (.STL / .STEP)",
        )
        if chosen:
            self.var_output_dir.set(chosen)

    def _on_slider_moved(self) -> None:
        if self._updating_ui:
            return
        new_params = DovetailParams(
            height_mm=self.var_height.get(),
            neck_width_mm=self.var_neck.get(),
            angle_deg=self.var_angle.get(),
            fillet_radius_mm=self.var_radius.get(),
            clearance_mm=self.var_clearance.get(),
            invert_side=self._params.invert_side,
        )
        self.refresh_from_params(new_params)
        self._on_params_changed(new_params)

    def refresh_from_params(self, params: DovetailParams) -> None:
        """Atualiza textos das cotas e o preview de 1 dente respeitando os limites das RNs."""
        self._updating_ui = True
        self._params = params
        self.lbl_val_height.config(text=f"[{params.height_mm:.1f} mm]")
        self.lbl_val_neck.config(text=f"[{params.neck_width_mm:.1f} mm]")
        self.lbl_val_angle.config(text=f"[{params.angle_deg:.1f}°]")
        self.lbl_val_radius.config(
            text=f"[{params.effective_fillet_radius_mm:.2f} mm (máx {params.max_allowed_fillet_radius_mm:.2f})]"
        )
        self.lbl_val_clearance.config(text=f"[{params.clearance_mm:.2f} mm]")
        self.tooth_preview.redraw(params)
        self._updating_ui = False

    def set_status_message(self, message: str, is_error: bool = False, is_success: bool = False) -> None:
        if is_error:
            fg = "#FCA5A5"
            bg = THEME.STATUS_ERR_BG
        elif is_success:
            fg = "#6EE7B7"
            bg = THEME.STATUS_OK_BG
        else:
            fg = THEME.TEXT_SECONDARY
            bg = THEME.BG_CARD
        self.lbl_status_box.config(text=message, fg=fg, bg=bg)

