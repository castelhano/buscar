"""Relatorio Excel (.xlsx) da tela Resumos -- par do PDF (services/relatorio.py).

Nao tenta copiar o layout do PDF: aproveita o que planilha faz melhor --
numeros reais (somaveis, com formato pt-BR aplicado pelo proprio Excel),
totais por formula, cabecalhos congelados, filtro nas listas e formatacao
condicional (mapa de calor / barras) no lugar dos graficos.

Uma aba por tema (Resumo, Rodagem, Uso da frota, Atendimentos,
Cancelamentos, Regioes e locais) + uma aba "Dados" com uma linha por trecho
de atendimento do mes, pra analises livres (tabela dinamica, filtro por
usuario etc.).

Mesma fonte de dados dos endpoints JSON / PDF (funcoes de
app.routers.resumos), entao os numeros batem com a tela.
"""

import calendar
import datetime as dt
import io

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.orm import Session

from app import models
from app.routers.resumos import (
    _data_efetiva,
    _passageiros_periodo,
    _range_mes,
    _seis_meses,
    resumo_atendimentos,
    resumo_outros,
    resumo_rodagem,
)
from app.services.exportacao import _rotulo_detalhe_ponto

# --------------------------------------------------------------------------
# Paleta -- mesmas cores do PDF (services/relatorio.py) / css do frontend
# --------------------------------------------------------------------------

_PRIMARIA = "2D3748"
_TEXTO_SUAVE = "667085"
_ZEBRA = "F4F4F4"
_TOTAL = "EEF1F4"
_PERIGO = "C0392B"
_BORDA = "D0D5DD"
_FIM_DE_SEMANA = "F7F3EA"
_CARD = "F8FAFC"
_MAPA_CALOR_MAX = "7FA3C9"
_BARRA = "8FAADC"

_FONTE = "Calibri"
_F_TITULO = Font(name=_FONTE, size=16, bold=True, color=_PRIMARIA)
_F_SUBTITULO = Font(name=_FONTE, size=10, color=_TEXTO_SUAVE)
_F_SECAO = Font(name=_FONTE, size=12, bold=True, color=_PRIMARIA)
_F_CABECALHO = Font(name=_FONTE, size=10, bold=True, color="FFFFFF")
_F_NORMAL = Font(name=_FONTE, size=10)
_F_TOTAL = Font(name=_FONTE, size=10, bold=True)
_F_FIM_SEMANA = Font(name=_FONTE, size=10, color=_TEXTO_SUAVE)
_F_CARD_ROTULO = Font(name=_FONTE, size=9, color=_TEXTO_SUAVE)
_F_CARD_VALOR = Font(name=_FONTE, size=20, bold=True, color=_PRIMARIA)
_F_CARD_DETALHE = Font(name=_FONTE, size=9, color=_TEXTO_SUAVE)

_FILL_CABECALHO = PatternFill("solid", fgColor=_PRIMARIA)
_FILL_ZEBRA = PatternFill("solid", fgColor=_ZEBRA)
_FILL_TOTAL = PatternFill("solid", fgColor=_TOTAL)
_FILL_FIM_SEMANA = PatternFill("solid", fgColor=_FIM_DE_SEMANA)
_FILL_CARD = PatternFill("solid", fgColor=_CARD)

_LADO = Side(style="thin", color=_BORDA)
_BORDA_CELULA = Border(bottom=_LADO)
_BORDA_TOTAL = Border(top=Side(style="thin", color=_PRIMARIA), bottom=Side(style="thin", color=_PRIMARIA))
_BORDA_CARD = Border(left=_LADO, right=_LADO, top=_LADO, bottom=_LADO)

_INT = "#,##0"
_INT_SEM_ZERO = '#,##0;-#,##0;""'
_PCT = "0.0%"
_DEC = "#,##0.00"

_CENTRO = Alignment(horizontal="center", vertical="center")
_DIREITA = Alignment(horizontal="right", vertical="center")
_ESQUERDA = Alignment(horizontal="left", vertical="center")

_MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
_MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
_DIAS_SEMANA = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]

_LIMITE_PCT_CANCELAMENTO = 0.30


# --------------------------------------------------------------------------
# Helpers de layout
# --------------------------------------------------------------------------

def _cabecalho_aba(ws: Worksheet, titulo: str, subtitulo: str) -> int:
    """Titulo + linha de contexto (mes/empresa) no topo da aba. Devolve a
    primeira linha livre pro conteudo."""
    ws.sheet_view.showGridLines = False
    ws["A1"] = titulo
    ws["A1"].font = _F_TITULO
    ws["A2"] = subtitulo
    ws["A2"].font = _F_SUBTITULO
    ws.row_dimensions[1].height = 24
    return 4


def _titulo_secao(ws: Worksheet, linha: int, coluna: int, texto: str) -> int:
    c = ws.cell(row=linha, column=coluna, value=texto)
    c.font = _F_SECAO
    return linha + 1


def _linha_cabecalho(ws: Worksheet, linha: int, coluna: int, titulos: list[str], alinhamentos: list[Alignment]) -> None:
    for i, (t, al) in enumerate(zip(titulos, alinhamentos)):
        c = ws.cell(row=linha, column=coluna + i, value=t)
        c.font = _F_CABECALHO
        c.fill = _FILL_CABECALHO
        c.alignment = Alignment(horizontal=al.horizontal, vertical="center", wrap_text=True)
    ws.row_dimensions[linha].height = 20


def _celula(ws: Worksheet, linha: int, coluna: int, valor, formato: str | None, alinhamento: Alignment, fill=None, font=None):
    c = ws.cell(row=linha, column=coluna, value=valor)
    c.font = font or _F_NORMAL
    c.border = _BORDA_CELULA
    c.alignment = alinhamento
    if formato:
        c.number_format = formato
    if fill is not None:
        c.fill = fill
    return c


def _estilo_total(ws: Worksheet, linha: int, col_ini: int, col_fim: int) -> None:
    for col in range(col_ini, col_fim + 1):
        c = ws.cell(row=linha, column=col)
        c.font = _F_TOTAL
        c.fill = _FILL_TOTAL
        c.border = _BORDA_TOTAL


def _tabela(
    ws: Worksheet,
    linha: int,
    coluna: int,
    titulos: list[str],
    linhas: list[list],
    formatos: list[str | None],
    totais: list[str | None] | None = None,
    rotulo_total: str = "Total",
    filtro: bool = False,
) -> tuple[int, int, int]:
    """Tabela simples com cabecalho escuro, zebra e linha de total opcional.

    `totais[i]`: "soma" -> SUBTOTAL(109) da coluna (ignora linhas escondidas
    pelo filtro); None -> vazio; qualquer outra string e uma formula pronta,
    onde `{L}` vira a letra da propria coluna e `{ini}`/`{fim}` as linhas de
    dados (pra % calculado a partir dos totais).

    Devolve (linha_cabecalho, ultima_linha_dados, proxima_linha_livre).
    """
    alinhamentos = [_ESQUERDA if f is None else _DIREITA for f in formatos]
    _linha_cabecalho(ws, linha, coluna, titulos, alinhamentos)
    ini = linha + 1
    for i, valores in enumerate(linhas):
        fill = _FILL_ZEBRA if i % 2 == 1 else None
        for j, (v, f, al) in enumerate(zip(valores, formatos, alinhamentos)):
            _celula(ws, ini + i, coluna + j, v, f, al, fill)
    fim = ini + len(linhas) - 1
    proxima = fim + 1

    if filtro and linhas:
        ws.auto_filter.ref = f"{get_column_letter(coluna)}{linha}:{get_column_letter(coluna + len(titulos) - 1)}{fim}"

    if totais is not None:
        lt = proxima
        ws.cell(row=lt, column=coluna, value=rotulo_total)
        for j, (t, f) in enumerate(zip(totais, formatos)):
            if j == 0 or t is None:
                continue
            letra = get_column_letter(coluna + j)
            if not linhas:
                formula = 0
            elif t == "soma":
                formula = f"=SUBTOTAL(109,{letra}{ini}:{letra}{fim})"
            else:
                formula = "=" + t.format(L=letra, ini=ini, fim=fim, lt=lt)
            c = ws.cell(row=lt, column=coluna + j, value=formula)
            c.number_format = f or _INT
            c.alignment = _DIREITA
        _estilo_total(ws, lt, coluna, coluna + len(titulos) - 1)
        proxima = lt + 1

    return linha, fim, proxima


def _matriz(
    ws: Worksheet,
    linha: int,
    coluna: int,
    titulo_linha: list[str],
    rotulos_linha: list[list],
    titulos_coluna: list[str],
    valores: list[list[int]],
    formato_valor: str = _INT_SEM_ZERO,
    fim_de_semana: list[bool] | None = None,
    mapa_calor: bool = False,
) -> tuple[int, int, int]:
    """Matriz (linhas x colunas) com total por linha e por coluna em formula.
    `titulo_linha`/`rotulos_linha` permitem mais de uma coluna de rotulo
    (ex.: Dia + dia da semana). Devolve (linha_cabecalho, ultima_linha_dados,
    proxima_linha_livre)."""
    n_rot = len(titulo_linha)
    titulos = titulo_linha + titulos_coluna + ["Total"]
    _linha_cabecalho(ws, linha, coluna, titulos, [_CENTRO] * n_rot + [_DIREITA] * (len(titulos_coluna) + 1))

    ini = linha + 1
    col_val_ini = coluna + n_rot
    col_val_fim = col_val_ini + len(titulos_coluna) - 1
    col_total = col_val_fim + 1
    for i, (rotulos, vals) in enumerate(zip(rotulos_linha, valores)):
        ln = ini + i
        fds = bool(fim_de_semana and fim_de_semana[i])
        fill = _FILL_FIM_SEMANA if fds else None
        font = _F_FIM_SEMANA if fds else None
        for j, r in enumerate(rotulos):
            _celula(ws, ln, coluna + j, r, None, _CENTRO, fill, font)
        for j, v in enumerate(vals):
            _celula(ws, ln, col_val_ini + j, v, formato_valor, _DIREITA, None if mapa_calor else fill, font)
        if titulos_coluna:
            formula = f"=SUM({get_column_letter(col_val_ini)}{ln}:{get_column_letter(col_val_fim)}{ln})"
        else:
            formula = 0
        c = _celula(ws, ln, col_total, formula, _INT, _DIREITA, fill, _F_TOTAL)
    fim = ini + len(rotulos_linha) - 1

    lt = fim + 1
    ws.cell(row=lt, column=coluna, value="Total")
    for col in range(col_val_ini, col_total + 1):
        letra = get_column_letter(col)
        c = ws.cell(row=lt, column=col, value=f"=SUM({letra}{ini}:{letra}{fim})" if rotulos_linha else 0)
        c.number_format = _INT
        c.alignment = _DIREITA
    _estilo_total(ws, lt, coluna, col_total)

    if mapa_calor and rotulos_linha and titulos_coluna:
        faixa = f"{get_column_letter(col_val_ini)}{ini}:{get_column_letter(col_val_fim)}{fim}"
        ws.conditional_formatting.add(
            faixa, ColorScaleRule(start_type="num", start_value=0, start_color="FFFFFF", end_type="max", end_color=_MAPA_CALOR_MAX)
        )

    return linha, fim, lt + 1


def _larguras(ws: Worksheet, larguras: dict[str, float]) -> None:
    for letra, w in larguras.items():
        ws.column_dimensions[letra].width = w


def _impressao(ws: Worksheet, paisagem: bool = True, linhas_titulo: str | None = None) -> None:
    ws.page_setup.orientation = "landscape" if paisagem else "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.page_margins.top = ws.page_margins.bottom = 0.5
    if linhas_titulo:
        ws.print_title_rows = linhas_titulo


def _pct(valor_percentual: float) -> float:
    """Os endpoints devolvem percentual em escala 0-100; o Excel quer fracao."""
    return round(valor_percentual / 100, 6)


# --------------------------------------------------------------------------
# Abas
# --------------------------------------------------------------------------

def _aba_resumo(ws: Worksheet, subtitulo: str, gerado_em: str, rodagem, atendimentos, outros) -> None:
    ws.sheet_view.showGridLines = False
    ws.merge_cells("B2:I2")
    ws["B2"] = "RELATÓRIO DE INDICADORES"
    ws["B2"].font = Font(name=_FONTE, size=18, bold=True, color="FFFFFF")
    ws["B2"].fill = _FILL_CABECALHO
    ws["B2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    for col in range(2, 10):
        ws.cell(row=2, column=col).fill = _FILL_CABECALHO
    ws.row_dimensions[2].height = 36
    ws.merge_cells("B3:I3")
    ws["B3"] = f"{subtitulo}  ·  Gerado em {gerado_em}"
    ws["B3"].font = _F_SUBTITULO
    ws["B3"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[3].height = 20

    km_total = sum(e.km_total for e in rodagem.km_por_empresa)
    planejados = sum(c.quantidade for c in atendimentos.grade)
    cancelamentos = sum(c.cancelamentos for c in atendimentos.cancelamento_por_usuario)
    perdidas = sum(c.viagens_perdidas for c in atendimentos.cancelamento_por_usuario)
    ocio = outros.ociosidade_frota
    ocup = outros.taxa_ocupacao

    cards = [
        ("Km rodado", km_total, _INT + ' "km"', f"{len(rodagem.km_por_veiculo)} veículos com lançamento de km"),
        ("Atendimentos planejados", planejados, _INT, f"{perdidas} viagens perdidas"),
        ("Cancelamentos (pelo usuário)", cancelamentos, _INT,
         f"{cancelamentos / planejados:.1%} dos planejados".replace(".", ",") if planejados else "-"),
        ("Ociosidade da frota", _pct(ocio.percentual_ocioso), _PCT,
         f"{ocio.veiculos_utilizados} de {ocio.veiculos_ativos} veículos ativos utilizados"),
        ("Taxa de ocupação", _pct(ocup.percentual), _PCT,
         f"{ocup.passageiros:,} passageiros / {ocup.capacidade_total:,} lugares".replace(",", ".")),
        ("Km por atendimento", outros.km_por_atendimento if outros.km_por_atendimento is not None else "-", _DEC,
         "km rodado ÷ atendimentos realizados"),
    ]

    # Grade 3 x 2 de cards; cada card ocupa 2 colunas (B:C, E:F, H:I...) com
    # uma coluna estreita de respiro entre eles.
    colunas_card = [2, 5, 8]
    linha_base = 5
    for idx, (rotulo, valor, formato, detalhe) in enumerate(cards):
        col = colunas_card[idx % 3]
        lin = linha_base + (idx // 3) * 5
        letra_ini, letra_fim = get_column_letter(col), get_column_letter(col + 1)
        for r, (texto, fonte, altura) in enumerate(
            [(rotulo, _F_CARD_ROTULO, 18), (valor, _F_CARD_VALOR, 34), (detalhe, _F_CARD_DETALHE, 18)]
        ):
            ln = lin + r
            ws.merge_cells(f"{letra_ini}{ln}:{letra_fim}{ln}")
            c = ws.cell(row=ln, column=col, value=texto)
            c.font = fonte
            c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            if r == 1 and isinstance(valor, (int, float)):
                c.number_format = formato
            ws.row_dimensions[ln].height = altura
            for cc in (col, col + 1):
                cel = ws.cell(row=ln, column=cc)
                cel.fill = _FILL_CARD
                cel.border = Border(
                    left=_LADO if cc == col else None,
                    right=_LADO if cc == col + 1 else None,
                    top=_LADO if r == 0 else None,
                    bottom=_LADO if r == 2 else None,
                )

    nota = linha_base + 10
    ws.cell(row=nota, column=2, value="Detalhes em cada aba: Rodagem · Uso da frota · Atendimentos · Cancelamentos · Regiões e locais · Dados").font = _F_SUBTITULO

    _larguras(ws, {"A": 2, "B": 16, "C": 16, "D": 3, "E": 16, "F": 16, "G": 3, "H": 16, "I": 16})
    _impressao(ws)


def _aba_rodagem(ws: Worksheet, subtitulo: str, rodagem, ano: int, mes: int) -> None:
    linha = _cabecalho_aba(ws, "Rodagem", subtitulo)

    # Km por empresa
    linha = _titulo_secao(ws, linha, 1, "Km por empresa")
    empresas = sorted(rodagem.km_por_empresa, key=lambda e: -e.km_total)
    _, fim, prox = _tabela(
        ws, linha, 1,
        ["Empresa", "Km rodado", "% do contrato", "% do km do período"],
        [[e.empresa_nome, e.km_total, _pct(e.percentual_contrato), _pct(e.percentual_km_periodo)] for e in empresas],
        [None, _INT, _PCT, _PCT],
        totais=[None, "soma", "SUM({L}{ini}:{L}{fim})", "SUM({L}{ini}:{L}{fim})"],
    )
    if empresas:
        ws.conditional_formatting.add(f"B{linha + 1}:B{fim}", DataBarRule(start_type="num", start_value=0, end_type="max", color=_BARRA))
    linha = prox + 2

    # Km por veiculo
    linha = _titulo_secao(ws, linha, 1, "Km por veículo")
    veiculos = sorted(rodagem.km_por_veiculo, key=lambda v: -v.km_total)
    _, fim, prox = _tabela(
        ws, linha, 1,
        ["Prefixo", "Placa", "Empresa", "Km rodado"],
        [[v.prefixo, v.placa, v.empresa_nome, v.km_total] for v in veiculos],
        [None, None, None, _INT],
        totais=[None, None, None, "soma"],
    )
    if veiculos:
        ws.conditional_formatting.add(f"D{linha + 1}:D{fim}", DataBarRule(start_type="num", start_value=0, end_type="max", color=_BARRA))
    linha = prox + 2

    # Evolucao 6 meses (empresa x mes) -- substitui o grafico de linhas do PDF
    linha = _titulo_secao(ws, linha, 1, "Evolução do km rodado (6 meses)")
    meses = _seis_meses(ano, mes)
    nomes = sorted({e.empresa_nome for e in rodagem.evolucao_km_empresa})
    km = {(e.empresa_nome, e.ano, e.mes): e.km_total for e in rodagem.evolucao_km_empresa}
    _matriz(
        ws, linha, 1, ["Empresa"], [[n] for n in nomes],
        [f"{_MESES_ABREV[m - 1]}/{str(a)[2:]}" for a, m in meses],
        [[km.get((n, a, m), 0) for a, m in meses] for n in nomes],
        formato_valor=_INT, mapa_calor=True,
    )
    # rotulo de empresa alinhado a esquerda (a matriz centraliza por padrao)
    for r in range(linha + 1, linha + 1 + len(nomes)):
        ws.cell(row=r, column=1).alignment = _ESQUERDA

    _larguras(ws, {"A": 22, "B": 14, "C": 16, "D": 18, "E": 12, "F": 12, "G": 12, "H": 12})
    _impressao(ws, paisagem=False)


def _dias_do_mes(ano: int, mes: int) -> list[dt.date]:
    return [dt.date(ano, mes, d) for d in range(1, calendar.monthrange(ano, mes)[1] + 1)]


def _aba_uso_frota(ws: Worksheet, subtitulo: str, rodagem, ano: int, mes: int) -> None:
    linha = _cabecalho_aba(ws, "Uso diário da frota", subtitulo)
    ws.cell(row=3, column=1, value="Veículos distintos utilizados por dia, por empresa").font = _F_SUBTITULO

    empresas = sorted(rodagem.km_por_empresa, key=lambda e: e.empresa_nome)
    por_dia = {d.data: d.por_empresa for d in rodagem.uso_frota_diario}
    dias = _dias_do_mes(ano, mes)
    cab, _, _ = _matriz(
        ws, linha, 1, ["Dia", "Sem"],
        [[d.day, _DIAS_SEMANA[d.weekday()]] for d in dias],
        [e.empresa_nome for e in empresas],
        [[por_dia.get(d, {}).get(str(e.empresa_id), 0) for e in empresas] for d in dias],
        fim_de_semana=[d.weekday() >= 5 for d in dias],
    )
    ws.freeze_panes = ws.cell(row=cab + 1, column=3)
    _larguras(ws, {"A": 6, "B": 6} | {get_column_letter(3 + i): 13 for i in range(len(empresas) + 1)})
    _impressao(ws, paisagem=False, linhas_titulo=f"{cab}:{cab}")


def _aba_atendimentos(ws: Worksheet, subtitulo: str, atendimentos, ano: int, mes: int) -> None:
    linha = _cabecalho_aba(ws, "Atendimentos planejados por dia x horário", subtitulo)
    ws.cell(row=3, column=1, value="Todos os trechos planejados (inclui cancelados), pela hora do passageiro").font = _F_SUBTITULO

    horas = sorted({c.hora for c in atendimentos.grade})
    contagem = {(c.data, c.hora): c.quantidade for c in atendimentos.grade}
    dias = _dias_do_mes(ano, mes)
    cab, _, _ = _matriz(
        ws, linha, 1, ["Dia", "Sem"],
        [[d.day, _DIAS_SEMANA[d.weekday()]] for d in dias],
        [h.strftime("%H:%M") for h in horas],
        [[contagem.get((d, h), 0) for h in horas] for d in dias],
        fim_de_semana=[d.weekday() >= 5 for d in dias],
        mapa_calor=True,
    )
    ws.freeze_panes = ws.cell(row=cab + 1, column=3)
    _larguras(ws, {"A": 6, "B": 6} | {get_column_letter(3 + i): 8 for i in range(len(horas))} | {get_column_letter(3 + len(horas)): 10})
    _impressao(ws, linhas_titulo=f"{cab}:{cab}")


def _aba_cancelamentos(ws: Worksheet, subtitulo: str, atendimentos) -> None:
    linha = _cabecalho_aba(ws, "Cancelamentos e viagens perdidas por usuário", subtitulo)
    ws.cell(row=3, column=1, value="Cancelamentos feitos pelo usuário (não inclui cancelados pela empresa). Use o filtro do cabeçalho para ordenar.").font = _F_SUBTITULO

    itens = atendimentos.cancelamento_por_usuario
    cab, fim, _ = _tabela(
        ws, linha, 1,
        ["Usuário", "Planejados", "Cancelamentos", "% cancelamento", "Viagens perdidas"],
        [[c.usuario_nome, c.planejados, c.cancelamentos, _pct(c.percentual_cancelamento), c.viagens_perdidas] for c in itens],
        [None, _INT, _INT, _PCT, _INT],
        totais=[None, "soma", "soma", "IF(B{lt}=0,0,C{lt}/B{lt})", "soma"],
        filtro=True,
    )
    if itens:
        ws.conditional_formatting.add(
            f"D{cab + 1}:D{fim}",
            CellIsRule(operator="greaterThanOrEqual", formula=[str(_LIMITE_PCT_CANCELAMENTO)],
                       font=Font(name=_FONTE, size=10, bold=True, color=_PERIGO)),
        )
    ws.freeze_panes = ws.cell(row=cab + 1, column=1)
    _larguras(ws, {"A": 40, "B": 13, "C": 15, "D": 16, "E": 17})
    _impressao(ws, paisagem=False, linhas_titulo=f"{cab}:{cab}")


def _aba_regioes_locais(ws: Worksheet, subtitulo: str, outros) -> None:
    linha = _cabecalho_aba(ws, "Regiões e locais", subtitulo)

    _titulo_secao(ws, linha, 1, "Ranking de cancelamento por região")
    regioes = outros.ranking_cancelamento_regiao
    _, fim_r, _ = _tabela(
        ws, linha + 1, 1, ["Região", "Cancelamentos"],
        [[r.regiao_nome, r.cancelamentos] for r in regioes],
        [None, _INT], totais=[None, "soma"],
    )
    if regioes:
        ws.conditional_formatting.add(f"B{linha + 2}:B{fim_r}", DataBarRule(start_type="num", start_value=0, end_type="max", color=_BARRA))

    _titulo_secao(ws, linha, 4, "Atendimentos por local")
    locais = outros.atendimentos_por_local
    _, fim_l, _ = _tabela(
        ws, linha + 1, 4, ["Local", "Atendimentos", "%"],
        [[a.local_nome, a.atendimentos, _pct(a.percentual)] for a in locais],
        [None, _INT, _PCT], totais=[None, "soma", "SUM({L}{ini}:{L}{fim})"],
    )
    if locais:
        ws.conditional_formatting.add(f"E{linha + 2}:E{fim_l}", DataBarRule(start_type="num", start_value=0, end_type="max", color=_BARRA))
    ws.cell(row=max(fim_r, fim_l) + 3, column=4,
            value="Ida e volta do mesmo usuário ao mesmo local no mesmo dia contam como 1 atendimento.").font = _F_SUBTITULO

    ws.freeze_panes = ws.cell(row=linha + 2, column=1)
    _larguras(ws, {"A": 28, "B": 15, "C": 4, "D": 40, "E": 14, "F": 10})
    _impressao(ws, paisagem=False)


def _aba_dados(ws: Worksheet, subtitulo: str, passageiros: list[models.ViagemDiaPassageiro]) -> None:
    linha = _cabecalho_aba(ws, "Dados – um registro por trecho de atendimento", subtitulo)
    ws.cell(row=3, column=1, value="Base para filtros e tabela dinâmica. Inclui trechos cancelados e sem vaga.").font = _F_SUBTITULO

    # Origem em branco = herda o destino do trecho anterior do mesmo usuario
    # no mesmo dia (mesma regra das exportacoes do dia -- ver exportacao._dados_origem).
    destino_por_trecho: dict[tuple[dt.date, int, int], str] = {}
    for p in passageiros:
        if p.status != models.StatusAtendimentoDia.CANCELADO:
            destino_por_trecho[(_data_efetiva(p), p.usuario_id, p.ordem_trecho)] = _rotulo_detalhe_ponto(
                p.destino_tipo, p.destino, p.usuario, p.destino_texto, p.destino_detalhe
            )[0]

    def origem(p: models.ViagemDiaPassageiro) -> str:
        if p.origem_tipo is None:
            return destino_por_trecho.get((_data_efetiva(p), p.usuario_id, p.ordem_trecho - 1), "-")
        return _rotulo_detalhe_ponto(p.origem_tipo, p.origem_local, p.usuario, p.origem_texto, p.origem_detalhe)[0]

    def cancelado_por(p: models.ViagemDiaPassageiro) -> str:
        if p.status != models.StatusAtendimentoDia.CANCELADO:
            return ""
        return "Empresa" if p.cancelado_pela_empresa else "Usuário"

    ordenados = sorted(passageiros, key=lambda p: (_data_efetiva(p), p.hora, p.usuario.nome, p.ordem_trecho))
    linhas = []
    for p in ordenados:
        v = p.viagem_dia
        data = _data_efetiva(p)
        linhas.append([
            data,
            _DIAS_SEMANA[data.weekday()],
            p.hora,
            p.usuario.nome,
            "Fixo" if p.fixo else "Eventual",
            "Sim" if p.acompanhante else "Não",
            origem(p),
            _rotulo_detalhe_ponto(p.destino_tipo, p.destino, p.usuario, p.destino_texto, p.destino_detalhe)[0],
            p.regiao_origem.nome if p.regiao_origem else "",
            v.empresa.nome if v is not None and v.empresa is not None else "",
            v.veiculo.prefixo if v is not None and v.veiculo is not None else "",
            v.condutor.nome if v is not None and v.condutor is not None else "",
            p.status.value,
            cancelado_por(p),
            "Sim" if p.viagem_perdida else "Não",
            "Sim" if v is None else "Não",
        ])

    titulos = [
        "Data", "Sem", "Hora", "Usuário", "Tipo", "Acompanhante", "Origem", "Destino", "Região origem",
        "Empresa", "Veículo", "Condutor", "Status", "Cancelado por", "Viagem perdida", "Sem vaga",
    ]
    formatos = ["DD/MM/YYYY", None, "HH:MM"] + [None] * 13
    cab, fim, _ = _tabela(ws, linha, 1, titulos, linhas, formatos, filtro=True)
    # data/hora/flags centralizadas (o helper alinha a direita tudo que tem formato)
    centralizar = [1, 2, 3, 5, 6, 11, 13, 14, 15, 16]
    for col in centralizar:
        ws.cell(row=cab, column=col).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for r in range(cab + 1, fim + 1):
            ws.cell(row=r, column=col).alignment = _CENTRO

    ws.freeze_panes = ws.cell(row=cab + 1, column=5)
    _larguras(ws, {
        "A": 11, "B": 6, "C": 7, "D": 32, "E": 10, "F": 14, "G": 26, "H": 26, "I": 16,
        "J": 14, "K": 9, "L": 22, "M": 12, "N": 14, "O": 15, "P": 10,
    })
    _impressao(ws, linhas_titulo=f"{cab}:{cab}")


# --------------------------------------------------------------------------
# Montagem final
# --------------------------------------------------------------------------

def gerar_xlsx_relatorio_resumos(db: Session, ano: int, mes: int, empresa_id: int | None) -> bytes:
    rodagem = resumo_rodagem(ano, mes, empresa_id, db)
    atendimentos = resumo_atendimentos(ano, mes, empresa_id, db)
    outros = resumo_outros(ano, mes, empresa_id, db)
    inicio, fim = _range_mes(ano, mes)
    passageiros = _passageiros_periodo(db, inicio, fim, empresa_id)

    if empresa_id is not None:
        empresa = db.get(models.Empresa, empresa_id)
        empresa_nome = empresa.nome if empresa is not None else "Empresa não encontrada"
    else:
        empresa_nome = "Todas as empresas"
    subtitulo = f"{_MESES_PT[mes - 1]}/{ano}  ·  {empresa_nome}"
    gerado_em = dt.datetime.now().strftime("%d/%m/%Y às %H:%M")

    wb = Workbook()
    ws_resumo = wb.active
    ws_resumo.title = "Resumo"
    _aba_resumo(ws_resumo, subtitulo, gerado_em, rodagem, atendimentos, outros)
    _aba_rodagem(wb.create_sheet("Rodagem"), subtitulo, rodagem, ano, mes)
    _aba_uso_frota(wb.create_sheet("Uso da frota"), subtitulo, rodagem, ano, mes)
    _aba_atendimentos(wb.create_sheet("Atendimentos"), subtitulo, atendimentos, ano, mes)
    _aba_cancelamentos(wb.create_sheet("Cancelamentos"), subtitulo, atendimentos)
    _aba_regioes_locais(wb.create_sheet("Regiões e locais"), subtitulo, outros)
    _aba_dados(wb.create_sheet("Dados"), subtitulo, passageiros)

    cores_abas = [_PRIMARIA, "4A6FA5", "4A6FA5", "2E7D32", "C0392B", "8E44AD", _TEXTO_SUAVE]
    for ws, cor in zip(wb.worksheets, cores_abas):
        ws.sheet_properties.tabColor = cor

    wb.properties.title = "Relatório de Indicadores"
    wb.properties.creator = "Buscar - Gestão de Transporte"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
