"""Relatorio PDF consolidado da tela Resumos (Rodagem/Atendimentos/Outros).

Nao replica o layout HTML -- reestrutura o mesmo conteudo em secoes de
documento (capa, resumo executivo, secoes por tema), pensado pra ser
encaminhado a uma gestora. Reaproveita a mesma fonte de dados dos endpoints
JSON (chama as funcoes de app.routers.resumos direto), garantindo que o PDF
sempre bate com o que a tela mostra.

Tudo em retrato (A4) -- testado tambem em paisagem pra secao Atendimentos
(tabelas mais largas), mas retrato coube melhor: a pagina mais alta compensa
a largura menor (o mes inteiro da grade dia x horario cabe numa unica pagina
em retrato, contra 5 em paisagem), entao ficou mais compacto sem perder
legibilidade.
"""

import datetime as dt
import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app import models
from app.routers.resumos import _seis_meses, resumo_atendimentos, resumo_outros, resumo_rodagem

# --------------------------------------------------------------------------
# Paleta / estilos -- mesma convencao ja usada nos outros PDFs do sistema
# (ver services/exportacao.py) e nas mesmas cores das variaveis css do
# frontend (--cor-primaria, --cor-perigo, --cor-sucesso, --cor-texto-suave).
# --------------------------------------------------------------------------

_COR_PRIMARIA = colors.HexColor("#2d3748")
_COR_TEXTO_SUAVE = colors.HexColor("#667085")
_COR_ZEBRA = colors.HexColor("#f4f4f4")
_COR_TOTAL_FUNDO = colors.HexColor("#eef1f4")
_COR_PERIGO = colors.HexColor("#c0392b")
_COR_SUCESSO = colors.HexColor("#2e7d32")
_PALETA_GRAFICOS = [
    _COR_PRIMARIA,
    _COR_SUCESSO,
    _COR_PERIGO,
    colors.HexColor("#f0a500"),
    colors.HexColor("#3b82f6"),
    colors.HexColor("#8e44ad"),
]

_MESES_PT = [
    "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
_DIAS_SEMANA_PT = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]

_ESTILOS = getSampleStyleSheet()
_ESTILO_TITULO_CAPA = ParagraphStyle("TituloCapa", parent=_ESTILOS["Title"], fontSize=28, leading=34, alignment=TA_CENTER)
_ESTILO_SUBTITULO_CAPA = ParagraphStyle(
    "SubtituloCapa", parent=_ESTILOS["Normal"], fontSize=14, leading=18, alignment=TA_CENTER, textColor=_COR_TEXTO_SUAVE
)
_ESTILO_RODAPE_CAPA = ParagraphStyle(
    "RodapeCapa", parent=_ESTILOS["Normal"], fontSize=9, alignment=TA_CENTER, textColor=_COR_TEXTO_SUAVE
)
_ESTILO_SECAO = ParagraphStyle("Secao", parent=_ESTILOS["Heading1"], textColor=_COR_PRIMARIA)
_ESTILO_SUBSECAO = ParagraphStyle("Subsecao", parent=_ESTILOS["Heading3"])

_MARGEM = 1.5 * cm
_LARGURA_UTIL = A4[0] - 2 * _MARGEM


def _fmt(valor: int) -> str:
    """Separador de milhar no padrao pt-BR (ponto), mesma convencao do frontend (utils/numero.ts)."""
    return f"{valor:,}".replace(",", ".")


# --------------------------------------------------------------------------
# Helpers de tabela
# --------------------------------------------------------------------------

def _tabela_padrao(dados, col_widths=None, estilos_extra=None, linha_total=True, tamanho_fonte=8):
    """Tabela no padrao visual do sistema: cabecalho escuro, zebra, linha de
    total em negrito com regua acima (mesma convencao de services/exportacao.py).
    """
    tabela = Table(dados, colWidths=col_widths, repeatRows=1)
    ultima_linha = len(dados) - 1
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), _COR_PRIMARIA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), tamanho_fonte),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _COR_ZEBRA]),
    ]
    if linha_total and ultima_linha >= 1:
        estilo += [
            ("FONTNAME", (0, ultima_linha), (-1, ultima_linha), "Helvetica-Bold"),
            ("LINEABOVE", (0, ultima_linha), (-1, ultima_linha), 1.2, _COR_PRIMARIA),
            ("BACKGROUND", (0, ultima_linha), (-1, ultima_linha), _COR_TOTAL_FUNDO),
        ]
    if estilos_extra:
        estilo.extend(estilos_extra)
    tabela.setStyle(TableStyle(estilo))
    return tabela


def _secao_com_tabela(titulo: str, tabela: Table) -> KeepTogether:
    """Titulo + tabela como bloco atomico -- evita o titulo ficar orfao no
    fim da pagina (Platypus so quebra o grupo se ele nem cabe inteiro numa
    pagina em branco; nesse caso a Table de dentro ainda pagina normalmente
    via repeatRows, entao tabelas longas continuam se dividindo direito).
    """
    return KeepTogether([Paragraph(titulo, _ESTILO_SUBSECAO), Spacer(1, 0.2 * cm), tabela])


def _barra_cor(largura=6 * cm, altura=0.22 * cm, cor=_COR_PRIMARIA):
    desenho = Drawing(largura, altura)
    desenho.add(Rect(0, 0, largura, altura, fillColor=cor, strokeColor=None))
    desenho.hAlign = "CENTER"
    return desenho


def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(_COR_TEXTO_SUAVE)
    canvas.drawRightString(A4[0] - _MARGEM, 1 * cm, f"Pagina {doc.page}")
    canvas.drawString(_MARGEM, 1 * cm, "Buscar - Relatorio de Indicadores")
    canvas.restoreState()


# --------------------------------------------------------------------------
# Capa + resumo executivo
# --------------------------------------------------------------------------

def _pagina_capa(ano: int, mes: int, empresa_nome: str) -> list:
    gerado_em = dt.datetime.now().strftime("%d/%m/%Y as %H:%M")
    return [
        Spacer(1, 7 * cm),
        _barra_cor(),
        Spacer(1, 1 * cm),
        Paragraph("Relatorio de Indicadores", _ESTILO_TITULO_CAPA),
        Spacer(1, 0.4 * cm),
        Paragraph(f"{_MESES_PT[mes - 1]} de {ano}", _ESTILO_SUBTITULO_CAPA),
        Spacer(1, 0.15 * cm),
        Paragraph(empresa_nome, _ESTILO_SUBTITULO_CAPA),
        Spacer(1, 5 * cm),
        Paragraph(f"Gerado em {gerado_em}", _ESTILO_RODAPE_CAPA),
        Paragraph("Buscar - Gestao de Transporte", _ESTILO_RODAPE_CAPA),
        PageBreak(),
    ]


def _secao_resumo_executivo(rodagem, atendimentos, outros) -> list:
    km_total = sum(e.km_total for e in rodagem.km_por_empresa)
    atendimentos_planejados = sum(c.quantidade for c in atendimentos.grade)
    cancelamentos_totais = sum(c.cancelamentos for c in atendimentos.cancelamento_por_usuario)
    pct_cancelamento = round(cancelamentos_totais / atendimentos_planejados * 100, 1) if atendimentos_planejados else 0.0

    dados = [
        ["Indicador", "Valor"],
        ["Km total rodado", f"{_fmt(km_total)} km"],
        ["Atendimentos planejados", _fmt(atendimentos_planejados)],
        ["Cancelamentos", f"{_fmt(cancelamentos_totais)} ({pct_cancelamento}%)"],
        ["Ociosidade de frota", f"{outros.ociosidade_frota.percentual_ocioso}%"],
        ["Taxa de ocupacao", f"{outros.taxa_ocupacao.percentual}%"],
        ["Km por atendimento", f"{outros.km_por_atendimento}" if outros.km_por_atendimento is not None else "-"],
    ]
    return [
        Paragraph("Resumo executivo", _ESTILO_SECAO),
        Spacer(1, 0.3 * cm),
        _tabela_padrao(dados, col_widths=[10 * cm, 6 * cm], linha_total=False),
        Spacer(1, 0.6 * cm),
    ]


# --------------------------------------------------------------------------
# Secao Rodagem
# --------------------------------------------------------------------------

def _tabela_km_veiculo(rodagem) -> Table:
    veiculos = sorted(rodagem.km_por_veiculo, key=lambda v: -v.km_total)
    dados = [["Veiculo", "Empresa", "Km rodado"]]
    for v in veiculos:
        dados.append([v.prefixo, v.empresa_nome, _fmt(v.km_total)])
    dados.append(["Total", "", _fmt(sum(v.km_total for v in veiculos))])
    return _tabela_padrao(dados, col_widths=[4 * cm, 8 * cm, 4 * cm])


def _grafico_barras_km_empresa(km_por_empresa) -> Drawing:
    desenho = Drawing(16 * cm, 8 * cm)
    grafico = VerticalBarChart()
    grafico.x, grafico.y, grafico.width, grafico.height = 1.5 * cm, 1.3 * cm, 13 * cm, 6 * cm
    grafico.data = [[e.km_total for e in km_por_empresa]]
    grafico.categoryAxis.categoryNames = [e.empresa_nome for e in km_por_empresa]
    grafico.categoryAxis.labels.fontSize = 7
    grafico.categoryAxis.labels.angle = 20
    grafico.categoryAxis.labels.dx = -6
    grafico.valueAxis.valueMin = 0
    grafico.bars[0].fillColor = _COR_PRIMARIA
    grafico.barWidth = 10
    desenho.add(grafico)
    return desenho


def _tabela_km_empresa(km_por_empresa) -> Table:
    dados = [["Empresa", "Km no periodo", "% do km total", "% contrato", "Variacao"]]
    estilos_extra = []
    for i, e in enumerate(km_por_empresa, start=1):
        variacao = e.percentual_km_periodo - e.percentual_contrato
        sinal = "+" if variacao > 0 else ""
        dados.append([e.empresa_nome, _fmt(e.km_total), f"{e.percentual_km_periodo}%", f"{e.percentual_contrato}%", f"{sinal}{variacao:.1f} p.p."])
        cor = _COR_PERIGO if variacao > 0 else _COR_SUCESSO
        estilos_extra.append(("TEXTCOLOR", (4, i), (4, i), cor))
        estilos_extra.append(("FONTNAME", (4, i), (4, i), "Helvetica-Bold"))

    total_km = sum(e.km_total for e in km_por_empresa)
    total_pct_km = sum(e.percentual_km_periodo for e in km_por_empresa)
    total_pct_contrato = sum(e.percentual_contrato for e in km_por_empresa)
    total_variacao = sum(e.percentual_km_periodo - e.percentual_contrato for e in km_por_empresa)
    sinal_total = "+" if total_variacao > 0 else ""
    dados.append(["Total", _fmt(total_km), f"{total_pct_km:.1f}%", f"{total_pct_contrato:.1f}%", f"{sinal_total}{total_variacao:.1f} p.p."])
    return _tabela_padrao(dados, estilos_extra=estilos_extra)


def _grafico_evolucao_km(evolucao_km_empresa, ano: int, mes: int) -> Drawing:
    meses = _seis_meses(ano, mes)
    labels = [f"{m:02d}/{a}" for a, m in meses]
    empresas_nomes = []
    for item in evolucao_km_empresa:
        if item.empresa_nome not in empresas_nomes:
            empresas_nomes.append(item.empresa_nome)
    serie_por_empresa = {nome: [0] * len(labels) for nome in empresas_nomes}
    for item in evolucao_km_empresa:
        chave = f"{item.mes:02d}/{item.ano}"
        if chave in labels:
            serie_por_empresa[item.empresa_nome][labels.index(chave)] = item.km_total

    desenho = Drawing(16 * cm, 8 * cm)
    grafico = HorizontalLineChart()
    grafico.x, grafico.y, grafico.width, grafico.height = 1.5 * cm, 1.5 * cm, 11 * cm, 6 * cm
    grafico.data = [serie_por_empresa[nome] for nome in empresas_nomes]
    grafico.categoryAxis.categoryNames = labels
    grafico.categoryAxis.labels.fontSize = 7
    grafico.valueAxis.valueMin = 0
    for i in range(len(empresas_nomes)):
        grafico.lines[i].strokeColor = _PALETA_GRAFICOS[i % len(_PALETA_GRAFICOS)]
        grafico.lines[i].strokeWidth = 1.5
    desenho.add(grafico)

    legenda = Legend()
    legenda.x, legenda.y = 13.3 * cm, 5.5 * cm
    legenda.dx, legenda.dy = 8, 8
    legenda.fontSize = 7
    legenda.deltay = 10
    legenda.colorNamePairs = [(_PALETA_GRAFICOS[i % len(_PALETA_GRAFICOS)], nome) for i, nome in enumerate(empresas_nomes)]
    desenho.add(legenda)
    return desenho


def _tabela_uso_frota(rodagem) -> Table:
    empresas = rodagem.km_por_empresa
    dados = [["Dia", "Sem"] + [e.empresa_nome for e in empresas] + ["Total"]]
    total_por_empresa = {e.empresa_id: 0 for e in empresas}
    total_geral = 0
    for dia in rodagem.uso_frota_diario:
        valores = [dia.por_empresa.get(str(e.empresa_id), 0) for e in empresas]
        total_dia = sum(valores)
        dados.append([dia.data.strftime("%d"), dia.dia_semana] + [_fmt(v) for v in valores] + [_fmt(total_dia)])
        for e, v in zip(empresas, valores):
            total_por_empresa[e.empresa_id] += v
        total_geral += total_dia
    dados.append(["Total", ""] + [_fmt(total_por_empresa[e.empresa_id]) for e in empresas] + [_fmt(total_geral)])
    return _tabela_padrao(dados)


def _secao_rodagem(rodagem, ano: int, mes: int) -> list:
    elementos = [Paragraph("Rodagem", _ESTILO_SECAO), Spacer(1, 0.3 * cm)]

    if rodagem.km_por_veiculo:
        elementos.append(_secao_com_tabela("Km por veiculo", _tabela_km_veiculo(rodagem)))
        elementos.append(Spacer(1, 0.6 * cm))

    if rodagem.km_por_empresa:
        elementos.append(KeepTogether([Paragraph("Km por empresa", _ESTILO_SUBSECAO), Spacer(1, 0.2 * cm), _grafico_barras_km_empresa(rodagem.km_por_empresa)]))
        elementos.append(Spacer(1, 0.3 * cm))
        elementos.append(_tabela_km_empresa(rodagem.km_por_empresa))
        elementos.append(Spacer(1, 0.6 * cm))

    if rodagem.evolucao_km_empresa:
        elementos.append(
            KeepTogether(
                [Paragraph("Evolucao do km rodado (6 meses)", _ESTILO_SUBSECAO), Spacer(1, 0.2 * cm), _grafico_evolucao_km(rodagem.evolucao_km_empresa, ano, mes)]
            )
        )
        elementos.append(Spacer(1, 0.6 * cm))

    if rodagem.uso_frota_diario:
        elementos.append(_secao_com_tabela("Uso diario de frota", _tabela_uso_frota(rodagem)))

    return elementos


# --------------------------------------------------------------------------
# Secao Atendimentos
# --------------------------------------------------------------------------

def _tabela_grade_atendimentos(atendimentos) -> Table:
    datas = sorted({c.data for c in atendimentos.grade})
    horas = sorted({c.hora for c in atendimentos.grade})
    contagem = {(c.data, c.hora): c.quantidade for c in atendimentos.grade}
    total_por_data: dict = {}
    total_por_hora: dict = {}
    total_geral = 0
    for (data_c, hora_c), qtd in contagem.items():
        total_por_data[data_c] = total_por_data.get(data_c, 0) + qtd
        total_por_hora[hora_c] = total_por_hora.get(hora_c, 0) + qtd
        total_geral += qtd

    dados = [["Dia", "DDD"] + [h.strftime("%H:%M") for h in horas] + ["Total"]]
    for data_d in datas:
        linha = [data_d.strftime("%d"), _DIAS_SEMANA_PT[data_d.weekday()]]
        linha += [str(contagem.get((data_d, h), 0) or "") for h in horas]
        linha.append(_fmt(total_por_data.get(data_d, 0)))
        dados.append(linha)
    dados.append(["Total", ""] + [_fmt(total_por_hora.get(h, 0)) for h in horas] + [_fmt(total_geral)])

    # Largura calculada dinamicamente pro numero de horarios distintos do
    # periodo caber na largura util da pagina em retrato (a quantidade de
    # colunas varia mes a mes, dependendo de quantos horarios distintos de
    # saida existem na escala).
    dia_w, ddd_w, total_w = 1.0 * cm, 0.9 * cm, 1.3 * cm
    hora_w = max(0.7 * cm, (_LARGURA_UTIL - dia_w - ddd_w - total_w) / max(1, len(horas)))
    col_widths = [dia_w, ddd_w] + [hora_w] * len(horas) + [total_w]
    return _tabela_padrao(dados, col_widths=col_widths, tamanho_fonte=6)


def _tabela_cancelamento_usuario(atendimentos) -> Table:
    dados = [["Usuario", "Planejados", "Cancelamentos", "%", "Viagens perdidas"]]
    for c in atendimentos.cancelamento_por_usuario:
        dados.append([c.usuario_nome, _fmt(c.planejados), _fmt(c.cancelamentos), f"{c.percentual_cancelamento:.1f}%", _fmt(c.viagens_perdidas)])

    total_planejados = sum(c.planejados for c in atendimentos.cancelamento_por_usuario)
    total_cancelamentos = sum(c.cancelamentos for c in atendimentos.cancelamento_por_usuario)
    total_perdidas = sum(c.viagens_perdidas for c in atendimentos.cancelamento_por_usuario)
    pct_total = round(total_cancelamentos / total_planejados * 100, 1) if total_planejados else 0.0
    dados.append(["Total", _fmt(total_planejados), _fmt(total_cancelamentos), f"{pct_total}%", _fmt(total_perdidas)])
    return _tabela_padrao(dados, col_widths=[7.5 * cm, 3 * cm, 3.2 * cm, 2 * cm, 3.3 * cm])


def _secao_atendimentos(atendimentos) -> list:
    elementos = [Paragraph("Atendimentos", _ESTILO_SECAO), Spacer(1, 0.3 * cm)]

    if atendimentos.grade:
        elementos.append(_secao_com_tabela("Atendimentos planejados por dia x horario", _tabela_grade_atendimentos(atendimentos)))
        elementos.append(Spacer(1, 0.6 * cm))

    if atendimentos.cancelamento_por_usuario:
        elementos.append(_secao_com_tabela("Cancelamentos e viagens perdidas por usuario", _tabela_cancelamento_usuario(atendimentos)))

    return elementos


# --------------------------------------------------------------------------
# Secao Outros
# --------------------------------------------------------------------------

def _tabela_ranking_regiao(outros) -> Table:
    dados = [["Regiao", "Cancelamentos"]]
    for r in outros.ranking_cancelamento_regiao:
        dados.append([r.regiao_nome, _fmt(r.cancelamentos)])
    dados.append(["Total", _fmt(sum(r.cancelamentos for r in outros.ranking_cancelamento_regiao))])
    return _tabela_padrao(dados, col_widths=[10 * cm, 4 * cm])


def _tabela_atendimentos_local(outros) -> Table:
    dados = [["Local", "Atendimentos", "%"]]
    for a in outros.atendimentos_por_local:
        dados.append([a.local_nome, _fmt(a.atendimentos), f"{a.percentual:.1f}%"])
    total_at = sum(a.atendimentos for a in outros.atendimentos_por_local)
    total_pct = sum(a.percentual for a in outros.atendimentos_por_local)
    dados.append(["Total", _fmt(total_at), f"{total_pct:.1f}%"])
    return _tabela_padrao(dados, col_widths=[9 * cm, 3.5 * cm, 2.5 * cm])


def _secao_outros(outros) -> list:
    elementos = [Paragraph("Outros indicadores", _ESTILO_SECAO), Spacer(1, 0.3 * cm)]

    if outros.ranking_cancelamento_regiao:
        elementos.append(_secao_com_tabela("Ranking de cancelamento por regiao", _tabela_ranking_regiao(outros)))
        elementos.append(Spacer(1, 0.6 * cm))

    if outros.atendimentos_por_local:
        elementos.append(_secao_com_tabela("Atendimentos por local", _tabela_atendimentos_local(outros)))

    return elementos


# --------------------------------------------------------------------------
# Montagem final
# --------------------------------------------------------------------------

def gerar_pdf_relatorio_resumos(db: Session, ano: int, mes: int, empresa_id: int | None) -> bytes:
    rodagem = resumo_rodagem(ano, mes, empresa_id, db)
    atendimentos = resumo_atendimentos(ano, mes, empresa_id, db)
    outros = resumo_outros(ano, mes, empresa_id, db)

    if empresa_id is not None:
        empresa = db.get(models.Empresa, empresa_id)
        empresa_nome = empresa.nome if empresa is not None else "Empresa nao encontrada"
    else:
        empresa_nome = "Todas as empresas"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, title="Relatorio de Indicadores",
        topMargin=_MARGEM, bottomMargin=_MARGEM, leftMargin=_MARGEM, rightMargin=_MARGEM,
    )

    elementos = []
    elementos += _pagina_capa(ano, mes, empresa_nome)
    elementos += _secao_resumo_executivo(rodagem, atendimentos, outros)
    elementos += _secao_rodagem(rodagem, ano, mes)
    elementos.append(PageBreak())
    elementos += _secao_atendimentos(atendimentos)
    elementos.append(PageBreak())
    elementos += _secao_outros(outros)

    doc.build(elementos, onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()
