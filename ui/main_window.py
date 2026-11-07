"""
Janela Principal do SnapTail3D — Dovetail Studio 3D (Seção 5 da Documentação).
Papel do Módulo: Orquestrar as 4 zonas da interface Dark CAD Studio, conectar eventos do usuário
aos motores geométrico e CAD 3D e exibir alertas de engenharia (RN06, RN07, RN08).
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from cad_engine.grip_tester import generate_grip_test_coupom
from cad_engine.solid_cutter import execute_3d_cut
from cad_engine.step_loader import create_demo_structural_part, load_part_from_file
from config.printer_profiles import DEFAULT_PRINTER, PRINTER_MAP, PRINTER_PROFILES, PrinterProfile
from exporters.file_exporter import export_cut_pieces
from geometry.auto_cutter import create_preset_cut_line, find_optimal_cut_line
from geometry.nesting_optimizer import evaluate_cut_solution
from models.cut_line import CutLine
from models.dovetail_params import DovetailParams
from models.part_model import PartModel
from models.validation_report import CutValidationReport
from ui.control_panel import ControlPanel
from ui.theme import THEME
from ui.viewport_canvas import ViewportCanvas


class DovetailStudioWindow(tk.Tk):
    """Aplicação Desktop Interativa Dovetail Studio 3D (Padrão Dark CAD Studio)."""

    def __init__(self) -> None:
        super().__init__()
        self.title("SnapTail3D — Dovetail Studio 3D | Corte Interativo com Encaixes Mecânicos")
        self.geometry("1260x780")
        self.minsize(1024, 680)
        self.configure(bg=THEME.BG_MAIN)

        # Estado de Domínio Ativo
        self._printer: PrinterProfile = DEFAULT_PRINTER
        self._params: DovetailParams = DovetailParams()
        self._part: PartModel = create_demo_structural_part("chassi_v")
        self._cut_line: CutLine = create_preset_cut_line(self._part, "vertical")
        self._report: CutValidationReport = evaluate_cut_solution(
            self._part, self._cut_line, self._params, self._printer
        )

        self._configure_ttk_styles()
        self._build_layout()
        self._refresh_all(reset_camera=True)

    def _configure_ttk_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Dark.TCombobox",
            fieldbackground=THEME.BG_CARD,
            background=THEME.BG_CARD,
            foreground=THEME.TEXT_PRIMARY,
            arrowcolor=THEME.ACCENT_CYAN,
        )

    def _build_layout(self) -> None:
        # =====================================================================
        # ZONA 1: TOP HEADER BAR
        # =====================================================================
        header = tk.Frame(
            self,
            bg=THEME.BG_PANEL,
            height=52,
            highlightthickness=1,
            highlightbackground=THEME.BORDER_SUBTLE,
            padx=14,
            pady=8,
        )
        header.pack(fill=tk.X, side=tk.TOP)

        # Logo & Título
        logo_badge = tk.Label(
            header,
            text=" ◆ SNAPTAIL 3D ",
            bg=THEME.ACCENT_CYAN,
            fg=THEME.BG_MAIN,
            font=(THEME.FONT_FAMILY, 10, "bold"),
            padx=6,
            pady=3,
        )
        logo_badge.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(
            header,
            text="DOVETAIL STUDIO 3D",
            bg=THEME.BG_PANEL,
            fg=THEME.TEXT_PRIMARY,
            font=(THEME.FONT_FAMILY, 11, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 18))

        # Botão Abrir .STEP / .STL
        btn_open = tk.Button(
            header,
            text="📂 Abrir .STEP / .STL",
            bg=THEME.ACCENT_BLUE,
            fg=THEME.TEXT_PRIMARY,
            activebackground=THEME.ACCENT_CYAN,
            activeforeground=THEME.BG_MAIN,
            relief=tk.FLAT,
            font=(THEME.FONT_FAMILY, 9, "bold"),
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._on_open_file,
        )
        btn_open.pack(side=tk.LEFT, padx=4)

        # Botão Alternar Peça Demo
        self._demo_variant = "chassi_v"
        btn_demo = tk.Button(
            header,
            text="⚙ Alternar Peça Demo",
            bg=THEME.BG_CARD,
            fg=THEME.TEXT_PRIMARY,
            activebackground=THEME.BORDER_SUBTLE,
            relief=tk.FLAT,
            font=(THEME.FONT_FAMILY, 9),
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._on_toggle_demo_part,
        )
        btn_demo.pack(side=tk.LEFT, padx=4)

        # Seletor de Impressora à direita
        printer_frame = tk.Frame(header, bg=THEME.BG_PANEL)
        printer_frame.pack(side=tk.RIGHT)

        self.lbl_global_badge = tk.Label(
            printer_frame,
            text="APROVADO NA MESA",
            bg=THEME.STATUS_OK_BG,
            fg=THEME.STATUS_OK,
            font=(THEME.FONT_FAMILY, 8, "bold"),
            padx=10,
            pady=4,
        )
        self.lbl_global_badge.pack(side=tk.RIGHT, padx=(10, 0))

        self.var_printer = tk.StringVar(value=self._printer.display_label)
        combo_printer = ttk.Combobox(
            printer_frame,
            textvariable=self.var_printer,
            values=[p.display_label for p in PRINTER_PROFILES],
            state="readonly",
            width=34,
            style="Dark.TCombobox",
            font=(THEME.FONT_FAMILY, 9),
        )
        combo_printer.pack(side=tk.RIGHT, padx=4)
        combo_printer.bind("<<ComboboxSelected>>", self._on_printer_changed)

        tk.Label(
            printer_frame,
            text="Impressora:",
            bg=THEME.BG_PANEL,
            fg=THEME.TEXT_SECONDARY,
            font=(THEME.FONT_FAMILY, 9, "bold"),
        ).pack(side=tk.RIGHT, padx=(0, 4))

        # =====================================================================
        # CORPO PRINCIPAL (ZONA ESQUERDA: PRESETS + VIEWPORT | ZONA DIREITA: PAINEL)
        # =====================================================================
        body = tk.Frame(self, bg=THEME.BG_MAIN, padx=10, pady=8)
        body.pack(fill=tk.BOTH, expand=True)

        # Zona Direita: Painel de Controle de Parâmetros e Exportação
        self.control_panel = ControlPanel(
            body,
            initial_params=self._params,
            on_params_changed=self._on_params_changed,
            on_export_mini_test=self._on_export_mini_test,
            on_export_cut_pieces=self._on_export_cut_pieces,
        )
        self.control_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # Zona Esquerda: Barra de Presets Rápidos + Viewport CAD + Rodapé de Dica
        left_zone = tk.Frame(body, bg=THEME.BG_MAIN)
        left_zone.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Barra de Presets Rápidos (1 Clique — Seção 5.3.2)
        presets_bar = tk.Frame(
            left_zone,
            bg=THEME.BG_PANEL,
            highlightthickness=1,
            highlightbackground=THEME.BORDER_SUBTLE,
            padx=10,
            pady=6,
        )
        presets_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            presets_bar,
            text="Presets de Linha:",
            bg=THEME.BG_PANEL,
            fg=THEME.TEXT_SECONDARY,
            font=(THEME.FONT_FAMILY, 9, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 8))

        preset_buttons = [
            ("| Vertical", lambda: self._apply_line_preset("vertical"), THEME.BG_CARD, THEME.TEXT_PRIMARY),
            ("— Horizontal", lambda: self._apply_line_preset("horizontal"), THEME.BG_CARD, THEME.TEXT_PRIMARY),
            ("/ Diagonal +45°", lambda: self._apply_line_preset("diagonal_pos"), THEME.BG_CARD, THEME.TEXT_PRIMARY),
            ("\\ Diagonal -45°", lambda: self._apply_line_preset("diagonal_neg"), THEME.BG_CARD, THEME.TEXT_PRIMARY),
            ("⇄ Inverter Lado Dentes", self._on_invert_teeth_side, THEME.BG_CARD, THEME.ACCENT_CYAN),
            ("✨ Auto-Corte Inteligente", self._on_auto_cut, THEME.ACCENT_BLUE_DARK, THEME.TEXT_PRIMARY),
            ("🔍 Centralizar", lambda: self.viewport.fit_view_to_scene(), THEME.BG_CARD, THEME.TEXT_SECONDARY),
        ]

        for btn_text, cmd, bg_col, fg_col in preset_buttons:
            b = tk.Button(
                presets_bar,
                text=btn_text,
                bg=bg_col,
                fg=fg_col,
                activebackground=THEME.ACCENT_BLUE,
                activeforeground=THEME.TEXT_PRIMARY,
                relief=tk.FLAT,
                font=(THEME.FONT_FAMILY, 8, "bold"),
                padx=9,
                pady=4,
                cursor="hand2",
                command=cmd,
            )
            b.pack(side=tk.LEFT, padx=3)

        # Viewport Canvas Interativo
        self.viewport = ViewportCanvas(
            left_zone,
            on_cut_line_changed=self._on_cut_line_changed,
        )
        self.viewport.pack(fill=tk.BOTH, expand=True)

        # Rodapé de Instruções do Viewport
        footer_bar = tk.Frame(left_zone, bg=THEME.BG_MAIN, pady=4)
        footer_bar.pack(fill=tk.X)

        self.lbl_part_info = tk.Label(
            footer_bar,
            text="",
            bg=THEME.BG_MAIN,
            fg=THEME.ACCENT_CYAN,
            font=(THEME.FONT_MONO, 8, "bold"),
            anchor="w",
        )
        self.lbl_part_info.pack(side=tk.LEFT)

        tk.Label(
            footer_bar,
            text="Dica: Clique e arraste na peça para traçar a linha de corte, arraste P1/P2 ou use o scroll para Zoom.",
            bg=THEME.BG_MAIN,
            fg=THEME.TEXT_SECONDARY,
            font=(THEME.FONT_FAMILY, 8),
            anchor="e",
        ).pack(side=tk.RIGHT)

    # =========================================================================
    # HANDLERS E ATUALIZAÇÃO REATIVA DO ESTADO
    # =========================================================================

    def _on_open_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Abrir Modelo 3D (.STEP, .STP, .STL)",
            filetypes=[
                ("Modelos CAD e Malha 3D", "*.step *.stp *.STEP *.STP *.stl *.STL"),
                ("Arquivos STEP B-Rep", "*.step *.stp *.STEP *.STP"),
                ("Arquivos STL", "*.stl *.STL"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not file_path:
            return
        self._part = load_part_from_file(file_path)
        self._cut_line = find_optimal_cut_line(self._part, self._params, self._printer)
        self._refresh_all(reset_camera=True)

        msg = f"Peça '{self._part.name}' carregada ({self._part.bbox.size_x:.1f}×{self._part.bbox.size_y:.1f}×{self._part.bbox.size_z:.1f} mm)."
        if self._part.scale_unit_warning:
            msg += f" {self._part.scale_unit_warning}"
        self.control_panel.set_status_message(msg, is_success=True)

    def _on_toggle_demo_part(self) -> None:
        self._demo_variant = (
            "gabarito_industrial" if self._demo_variant == "chassi_v" else "chassi_v"
        )
        self._part = create_demo_structural_part(self._demo_variant)
        self._cut_line = find_optimal_cut_line(self._part, self._params, self._printer)
        self._refresh_all(reset_camera=True)
        self.control_panel.set_status_message(
            f"Peça de demonstração alterada para: {self._part.name} ({len(self._part.holes)} furos protegidos).",
            is_success=True,
        )

    def _on_printer_changed(self, _event: tk.Event) -> None:
        selected = self.var_printer.get()
        if selected in PRINTER_MAP:
            self._printer = PRINTER_MAP[selected]
            self._refresh_all(reset_camera=True)

    def _apply_line_preset(self, preset_name: str) -> None:
        self._cut_line = create_preset_cut_line(
            self._part, preset_name, invert_normal=self._params.invert_side
        )
        self._refresh_all(reset_camera=False)

    def _on_invert_teeth_side(self) -> None:
        self._params.invert_side = not self._params.invert_side
        self._cut_line.invert_normal = self._params.invert_side
        self.control_panel.refresh_from_params(self._params)
        self._refresh_all(reset_camera=False)

    def _on_auto_cut(self) -> None:
        self._cut_line = find_optimal_cut_line(self._part, self._params, self._printer)
        self._refresh_all(reset_camera=False)
        self.control_panel.set_status_message(
            f"Auto-Corte Inteligente aplicado: {self._report.num_active_teeth} dentes ativos, "
            f"ângulo {self._cut_line.angle_deg:+.1f}°.",
            is_success=True,
        )

    def _on_cut_line_changed(self, new_line: CutLine) -> None:
        self._cut_line = new_line
        self._refresh_all(reset_camera=False)

    def _on_params_changed(self, new_params: DovetailParams) -> None:
        self._params = new_params
        self._refresh_all(reset_camera=False)

    def _refresh_all(self, reset_camera: bool = False) -> None:
        self._report = evaluate_cut_solution(
            self._part, self._cut_line, self._params, self._printer, use_3d_kernel=False
        )
        self.viewport.set_scene(
            part=self._part,
            cut_line=self._cut_line,
            params=self._params,
            printer=self._printer,
            report=self._report,
            reset_camera=reset_camera,
        )

        # Atualiza o Badge Global no Header e o rodapé da peça
        self.lbl_part_info.config(
            text=(
                f"Peça: {self._part.name}  |  Dimensões: "
                f"{self._part.bbox.size_x:.1f} × {self._part.bbox.size_y:.1f} × {self._part.bbox.size_z:.1f} mm  |  "
                f"Furos detectados: {len(self._part.holes)}"
            )
        )

        if self._report.num_active_teeth == 0:
            self.lbl_global_badge.config(
                text="SEM DENTES VÁLIDOS",
                bg=THEME.STATUS_ERR_BG,
                fg=THEME.STATUS_ERR,
            )
        elif self._report.has_fragmentation_warning:
            self.lbl_global_badge.config(
                text=f"ALERTA: {self._report.total_fragments} FRAGMENTOS (RN07)",
                bg=THEME.STATUS_WARN_BG,
                fg=THEME.STATUS_WARN,
            )
        elif not self._report.both_fit_on_bed:
            self.lbl_global_badge.config(
                text="EXCEDE MESA DA IMPRESSORA (RN06)",
                bg=THEME.STATUS_ERR_BG,
                fg=THEME.STATUS_ERR,
            )
        else:
            self.lbl_global_badge.config(
                text="✓ APROVADO PARA A IMPRESSORA",
                bg=THEME.STATUS_OK_BG,
                fg=THEME.STATUS_OK,
            )

    def _on_export_mini_test(self, output_dir: str) -> None:
        """RN10: Exporta o Corpo de Prova Rápido (Mini-Teste de Grip 28x22x5 mm)."""
        try:
            res = generate_grip_test_coupom(self._params)
            bundle = export_cut_pieces(
                cut_result=res,
                base_part_name="MiniTeste_Grip_Calibracao",
                output_dir_str=output_dir,
                params=self._params,
                source_path=None,
            )
            msg = (
                f"Mini-Teste de Grip (28×22×5 mm, folga {self._params.clearance_mm:.2f} mm) salvo em:\n"
                f"{bundle.stl_a_path.name} e {bundle.stl_b_path.name}"
            )
            self.control_panel.set_status_message(msg, is_success=True)
            messagebox.showinfo(
                "Mini-Teste de Grip Exportado (RN10)",
                f"Corpo de prova rápido (10 min) gerado com sucesso!\n\n"
                f"Pasta: {bundle.output_dir}\n"
                f"• {bundle.stl_a_path.name} / {bundle.step_a_path.name}\n"
                f"• {bundle.stl_b_path.name} / {bundle.step_b_path.name}\n\n"
                f"Folga aplicada: {self._params.clearance_mm:.2f} mm (±{self._params.delta_offset_mm:.2f} mm).",
            )
        except Exception as exc:
            self.control_panel.set_status_message(f"Erro ao gerar Mini-Teste: {exc}", is_error=True)

    def _on_export_cut_pieces(self, output_dir: str) -> None:
        """RN06, RN07, RN08, RN09: Executa o corte 3D e salva os arquivos .STL e .STEP."""
        if self._report.num_active_teeth == 0:
            messagebox.showwarning(
                "Corte Sem Dentes (RN01)",
                "A linha de corte atual não possui nenhum dente aprovado.\n"
                "Ajuste a posição da linha ou clique em '✨ Auto-Corte Inteligente'.",
            )
            return

        # RN07: Alerta de Fragmentação obrigatório antes de salvar
        if self._report.has_fragmentation_warning:
            proceed = messagebox.askyesno(
                "Alerta de Fragmentação Multi-Corpo (RN07)",
                f"ATENÇÃO: A linha traçada atravessa um vão aberto e divide a peça em "
                f"{self._report.total_fragments} pedaços desconectados:\n"
                f"• Metade A: {self._report.half_a_nesting.num_fragments} sólido(s)\n"
                f"• Metade B: {self._report.half_b_nesting.num_fragments} sólido(s)\n\n"
                f"Deseja prosseguir com a exportação mesmo assim?",
            )
            if not proceed:
                return

        # RN06: Alerta caso alguma metade exceda o limite útil da impressora
        if not self._report.both_fit_on_bed:
            proceed = messagebox.askyesno(
                "Alerta de Volume de Impressão (RN06)",
                f"Uma ou ambas as metades excedem a área útil da impressora {self._printer.name} "
                f"({self._printer.usable_x_mm:.0f}×{self._printer.usable_y_mm:.0f} mm):\n"
                f"• {self._report.half_a_nesting.status_summary}\n"
                f"• {self._report.half_b_nesting.status_summary}\n\n"
                f"Deseja exportar os arquivos mesmo assim?",
            )
            if not proceed:
                return

        try:
            self.control_panel.set_status_message("Executando corte booleano 3D e alinhando em Z=0...")
            self.update_idletasks()

            cut_res = execute_3d_cut(self._part, self._cut_line, self._params, self._printer)
            bundle = export_cut_pieces(
                cut_result=cut_res,
                base_part_name=self._part.name,
                output_dir_str=output_dir,
                params=self._params,
                source_path=self._part.source_path,
            )

            msg = (
                f"Peças salvas com sucesso em '{bundle.output_dir.name}':\n"
                f"{bundle.stl_a_path.name}, {bundle.stl_b_path.name} (.STL + .STEP)"
            )
            self.control_panel.set_status_message(msg, is_success=True)
            messagebox.showinfo(
                "Corte 3D Concluído (RN08 / RN09)",
                f"Pares sincronizados exportados com sucesso!\n\n"
                f"Pasta: {bundle.output_dir}\n"
                f"• {bundle.stl_a_path.name} (Rotação mesa: {cut_res.half_a.optimal_angle_deg:.0f}°, Z=0)\n"
                f"• {bundle.stl_b_path.name} (Rotação mesa: {cut_res.half_b.optimal_angle_deg:.0f}°, Z=0)\n"
                f"• {bundle.step_a_path.name}\n"
                f"• {bundle.step_b_path.name}\n"
                f"• {bundle.report_json_path.name}",
            )
        except Exception as exc:
            self.control_panel.set_status_message(f"Erro no corte 3D: {exc}", is_error=True)

