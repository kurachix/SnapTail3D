# SnapTail3D (Dovetail Studio 3D)

**SnapTail3D** é um software de engenharia interativo projetado para dividir peças estruturais para impressão 3D (FDM) utilizando **encaixes mecânicos *rabo de andorinha* (*dovetail*) contínuos, com alívio de tensões e proteção de integridade funcional**.

O software resolve o problema físico de imprimir peças maiores que o volume útil da mesa (ex.: Bambu Lab A1/P1S/X1C, Ender 3, Prusa MK4), gerando juntas com travamento mecânico positivo (*undercut*), cantos arredondados tangentes ($C^1$), desvio inteligente de furos e exportação sincronizada `.STL` e `.STEP` para fabricação e CAD.

---

## Principais Funcionalidades

- **Proteção Automática de Furos e Bordas (RN01):** O software detecta furos de parafusos, buchas e bordas da peça, suprimindo dentes nessas posições e mantendo uma margem sólida segura.
- **Geometria Dovetail com Travamento Bidirecional (RN02/RN03):** Ângulo de inclinação travado entre $45^\circ$ e $65^\circ$ para retenção mecânica sob tração e cisalhamento, com dentes macho e fêmea isonômicos.
- **Fillets Tangentes $C^1$ Obrigatórios (RN04):** Arredondamento dos 4 cantos do trapezoide com cálculo dinâmico de raio máximo para eliminar concentração de tensão sem auto-interseção.
- **Offset Normal Paralelo Uniforme $\pm\delta$ (RN05):** Folga perpendicular constante em todas as paredes e arcos concêntricos, garantindo deslizamento firme em Z (*grip* calibrado para 0,18 mm).
- **Auto-Nesting e Validação de Volume de Mesa (RN06):** Otimizador rotacional $\theta \in [0^\circ, 180^\circ)$ que calcula as dimensões de cada metade na mesa e valida contra o limite útil da impressora selecionada.
- **Alerta de Fragmentação Multi-Corpo (RN07):** Identifica se a linha de corte cruza vãos abertos e geraria múltiplos pedaços soltos.
- **Apoio Automático em $Z=0$ e Normalização (RN08):** Conversão automática de arquivos em centímetros para milímetros e alinhamento das metades prontas para o fatiador.
- **Mini-Teste de Grip em 10 Minutos (RN10):** Exportação com 1 clique de um corpo de prova compacto ($28 \times 22 \times 5\text{ mm}$) com 1 único par macho/fêmea para calibrar folga na impressora antes de cortar a peça final.
- **Auto-Corte Inteligente (RN12):** Algoritmo de busca heurística que encontra a costura ótima avaliando número de dentes, aprovação na mesa e ausência de colisões.
- **Interface *Dark CAD Studio*:** Canvas interativo com *Click & Drag* ao vivo, manipuladores de extremidade $P_1$ e $P_2$, presets rápidos e mini-canvas de inspeção microscópica da folga.

---

## Arquitetura do Repositório

O projeto segue os princípios de separação estrita de responsabilidades (SoC), mantendo apenas o ponto de entrada na raiz:

```
SnapTail3D/
├── main.py                      # Ponto de entrada (GUI, testes e headless CLI)
├── Documentacao_Software_Corte_3D.md # Especificação técnica completa (RN01 a RN12, LF01 a LF07)
├── README.md                    # Manual do usuário e documentação de uso
├── .gitignore                   # Regras de exclusão de arquivos e diretórios
├── config/                      # Governança de parâmetros, limites e perfis de impressoras
│   ├── settings.py
│   └── printer_profiles.py
├── models/                      # Entidades de domínio (DovetailParams, CutLine, PartModel, etc.)
│   ├── dovetail_params.py
│   ├── cut_line.py
│   ├── part_model.py
│   └── validation_report.py
├── geometry/                    # Núcleo matemático e analítico (LF01 a LF07)
│   ├── coordinate_system.py
│   ├── dovetail_math.py
│   ├── tooth_placer.py
│   ├── nesting_optimizer.py
│   └── auto_cutter.py
├── cad_engine/                  # Kernel CAD 3D híbrido, importador STEP/STL e Mini-Teste
│   ├── step_loader.py
│   ├── solid_cutter.py
│   └── grip_tester.py
├── exporters/                   # Exportador sincronizado .STL, .STEP e JSON
│   └── file_exporter.py
├── ui/                          # Interface gráfica moderna Dark CAD Studio (Tkinter puro)
│   ├── theme.py
│   ├── tooth_preview_canvas.py
│   ├── viewport_canvas.py
│   ├── control_panel.py
│   └── main_window.py
└── tests/                       # Suíte de testes unitários das regras de negócio
    └── test_business_rules.py
```

---

## Requisitos e Instalação

O software foi construído de forma **híbrida e autocontida**:
- **Interface e Núcleo Geométrico:** Funciona nativamente com **Python 3.8+** (utilizando `tkinter`, biblioteca padrão).
- **Kernel CAD 3D Avançado (Opcional):** Se o pacote `cadquery` estiver instalado, o software utiliza o kernel B-Rep do OpenCASCADE para operações booleanas analíticas complexas e exportação `.step` nativa. Caso não esteja instalado, o gerador nativo do SnapTail3D assume com triangulação Ear-Clipping e conversor AP214 sem interromper o fluxo.

### Instalação rápida:

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/SnapTail3D.git
cd SnapTail3D

# (Opcional) Ambiente virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# (Opcional para recursos avançados B-Rep)
pip install cadquery
```

---

## Como Utilizar

### 1. Iniciar a Interface Gráfica (Studio)
```bash
python main.py
```

Na interface:
1. Clique em **"Abrir .STEP / .STL"** ou use a peça de demonstração já carregada (*Chassi Estrutural em V* ou *Gabarito Industrial*).
2. Selecione a sua impressora no topo (ex.: *Bambu Lab A1*, *Ender 3*, etc.).
3. Trace a linha de corte clicando e arrastando no canvas, utilize os botões de presets (`Vertical`, `Horizontal`, `Diagonal`) ou clique em **"✨ Auto-Corte Inteligente"**.
4. Ajuste os sliders de altura, pescoço, ângulo, raio e folga conforme seu filamento e observe a reação ao vivo no **Preview 1 Dente**.
5. Clique em **"🧪 Exportar Mini-Teste de Grip"** para calibrar a folga em 10 minutos ou **"✂ CORTAR E SALVAR PEÇAS"** para exportar as metades prontas para impressão apoiadas em $Z=0$.

### 2. Executar a Suíte de Testes (Validação das RNs)
Para verificar automaticamente a conformidade matemática das Regras de Negócio:
```bash
python main.py --test
```

### 3. Execução em Modo Linha de Comando (Headless Export)
Para rodar o algoritmo de auto-corte e exportar modelos diretamente via terminal:
```bash
python main.py --headless-export Cortes_Personalizados
```

