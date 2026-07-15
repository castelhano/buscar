import csv
import datetime as dt
import io
import re
import zipfile
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, joinedload

from app.models import (
    CondutorFerias,
    Frequencia,
    Sentido,
    StatusAtendimentoDia,
    StatusCondutor,
    ViagemDia,
    ViagemDiaPassageiro,
)
from app.services.frequencia import INTERVALO_PADRAO_POR_PERIODO, intervalo_do_condutor
from app.services.geracao import CORTE_PERIODO_TARDE
from app.services.recursos import fim_turno_condutor, fim_viagem

_ESTILOS = getSampleStyleSheet()
_ESTILO_CABECALHO_DIA = ParagraphStyle("CabecalhoDia", parent=_ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=16)
_ESTILO_CABECALHO_CONDUTOR = ParagraphStyle("CabecalhoCondutor", parent=_ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=13)
# Celulas de texto longo (Usuario/Origem/Destino/Observacoes) usam Paragraph em
# vez de string pura -- string pura e desenhada com drawString (uma linha so,
# sem quebra), o texto longo vazava da celula. Com Paragraph o ReportLab quebra
# respeitando a largura da coluna e a Table recalcula a altura da linha sozinha.
_ESTILO_CELULA = ParagraphStyle("Celula", parent=_ESTILOS["Normal"], fontName="Helvetica", fontSize=9, leading=11)
# Endereco detalhado (Usuario.detalhe / Local.observacao) e um complemento do
# texto principal da celula, exibido menor pra nao competir com ele.
_TAMANHO_FONTE_DETALHE = 7

_DIAS_SEMANA_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}


def nome_arquivo_seguro(nome: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", nome).strip("_") or "sem_nome"


def _celula(texto: str) -> Paragraph:
    return Paragraph(escape(texto), _ESTILO_CELULA)


def _com_detalhe(texto: str, detalhe: str | None) -> Paragraph:
    """Texto principal da celula + endereco detalhado numa linha extra, menor."""
    html = escape(texto)
    if detalhe:
        html += f'<br/><font size="{_TAMANHO_FONTE_DETALHE}">{escape(detalhe)}</font>'
    return Paragraph(html, _ESTILO_CELULA)


def _celula_origem(passageiro: ViagemDiaPassageiro) -> Paragraph:
    detalhe = passageiro.usuario.detalhe if passageiro.sentido == Sentido.IDA else None
    return _com_detalhe(passageiro.origem or "-", detalhe)


def _celula_destino(passageiro: ViagemDiaPassageiro) -> Paragraph:
    destino = passageiro.destino
    detalhe = destino.observacao if destino and passageiro.sentido == Sentido.IDA else None
    return _com_detalhe(destino.nome if destino else "-", detalhe)


def _hora_referencia(viagem: ViagemDia) -> dt.time:
    horas = [p.hora for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO]
    return min(horas) if horas else viagem.horario_saida


def _pdf_condutor_dia(viagens: list[ViagemDia], intervalo: tuple[dt.time, dt.time] | None = None) -> bytes:
    """Um PDF por condutor/dia, com todas as viagens (legs) dele numa unica
    tabela continua, na ordem cronologica -- reflete o mesmo agrupamento por
    condutor usado na tela de agendamento do dia.

    A primeira linha da tabela e o "Acesso" (saida da garagem, uma unica vez
    no dia); as legs seguintes emendam direto, sem nova saida de garagem --
    uma borda mais grossa so marca a troca de horario/leg. O intervalo do
    condutor entra como uma linha mesclada na posicao cronologica correta.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )
    elementos = []

    pernas = sorted(viagens, key=_hora_referencia)
    primeira = pernas[0]
    ultima = pernas[-1]
    condutor = primeira.condutor
    veiculo = primeira.veiculo
    regiao = primeira.regiao

    hora_inicio = primeira.horario_saida.strftime("%H:%M")
    hora_fim = fim_turno_condutor(ultima).strftime("%H:%M")
    dia_semana_nome = _DIAS_SEMANA_PT[primeira.data.weekday()]

    elementos.append(
        Paragraph(
            f"{primeira.data.strftime('%d/%m/%Y')} ({dia_semana_nome}) - {regiao.nome if regiao else '-'}",
            _ESTILO_CABECALHO_DIA,
        )
    )
    elementos.append(
        Paragraph(
            f"{condutor.matricula if condutor else '-'} {condutor.nome if condutor else '-'} "
            f"{hora_inicio} - {hora_fim} | VEICULO: {veiculo.prefixo if veiculo else '-'}",
            _ESTILO_CABECALHO_CONDUTOR,
        )
    )
    elementos.append(Spacer(1, 0.4 * cm))

    empresa_garagem = veiculo.empresa.nome if veiculo and veiculo.empresa else (primeira.empresa.nome if primeira.empresa else "-")

    linhas: list[list] = [["Hora", "Usuario", "Sentido", "Origem", "Destino", "Observacoes"]]
    linhas.append([hora_inicio, "--", "Acesso", _celula(empresa_garagem), "-", ""])

    limites_leg: list[int] = []
    linha_intervalo: int | None = None
    intervalo_inserido = intervalo is None

    for indice, viagem in enumerate(pernas):
        limites_leg.append(len(linhas))
        passageiros = sorted(
            (p for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO),
            key=lambda p: (p.hora, p.usuario.nome),
        )
        for passageiro in passageiros:
            observacoes = passageiro.observacoes or ""
            if passageiro.status == StatusAtendimentoDia.EM_ANALISE:
                observacoes = (f"[EM ANALISE] {observacoes}").strip()
            nome = passageiro.usuario.nome
            if passageiro.acompanhante:
                nome = f"{nome} + ACOMP"
            linhas.append(
                [
                    passageiro.hora.strftime("%H:%M"),
                    _celula(nome),
                    passageiro.sentido.value,
                    _celula_origem(passageiro),
                    _celula_destino(passageiro),
                    _celula(observacoes) if observacoes else "",
                ]
            )

        if not intervalo_inserido:
            proxima = pernas[indice + 1] if indice + 1 < len(pernas) else None
            cabe_antes_da_proxima = proxima is None or intervalo[1] <= proxima.horario_saida
            if intervalo[0] >= fim_viagem(viagem) and cabe_antes_da_proxima:
                linha_intervalo = len(linhas)
                linhas.append(
                    [f"INTERVALO {intervalo[0].strftime('%H:%M')} as {intervalo[1].strftime('%H:%M')}", "", "", "", "", ""]
                )
                intervalo_inserido = True

    if not intervalo_inserido:
        linha_intervalo = len(linhas)
        linhas.append([f"INTERVALO {intervalo[0].strftime('%H:%M')} as {intervalo[1].strftime('%H:%M')}", "", "", "", "", ""])

    tabela = Table(linhas, colWidths=[2 * cm, 6.5 * cm, 2.3 * cm, 5.4 * cm, 5.4 * cm, 5.1 * cm], repeatRows=1)
    estilos = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")]),
    ]
    for linha_idx in limites_leg[1:]:
        estilos.append(("LINEABOVE", (0, linha_idx), (-1, linha_idx), 1.5, colors.HexColor("#2d3748")))
    if linha_intervalo is not None:
        estilos.append(("SPAN", (0, linha_intervalo), (-1, linha_intervalo)))
        estilos.append(("BACKGROUND", (0, linha_intervalo), (-1, linha_intervalo), colors.HexColor("#e2e8f0")))
        estilos.append(("FONTNAME", (0, linha_intervalo), (-1, linha_intervalo), "Helvetica-Bold"))
        estilos.append(("ALIGN", (0, linha_intervalo), (-1, linha_intervalo), "CENTER"))
    tabela.setStyle(TableStyle(estilos))
    elementos.append(tabela)

    doc.build(elementos)
    return buffer.getvalue()


def _viagens_do_dia_com_condutor(db: Session, data: dt.date, condutor_id: int | None = None) -> list[ViagemDia]:
    query = (
        db.query(ViagemDia)
        .options(
            joinedload(ViagemDia.condutor),
            joinedload(ViagemDia.veiculo),
            joinedload(ViagemDia.empresa),
            joinedload(ViagemDia.regiao),
            joinedload(ViagemDia.passageiros).joinedload(ViagemDiaPassageiro.usuario),
            joinedload(ViagemDia.passageiros).joinedload(ViagemDiaPassageiro.destino),
        )
        .filter(ViagemDia.data == data, ViagemDia.condutor_id.isnot(None))
    )
    if condutor_id is not None:
        query = query.filter(ViagemDia.condutor_id == condutor_id)
    return query.all()


def gerar_zip_agendamentos(db: Session, data: dt.date) -> bytes | None:
    viagens = _viagens_do_dia_com_condutor(db, data)
    if not viagens:
        return None

    viagens_por_condutor: dict[int, list[ViagemDia]] = {}
    for viagem in viagens:
        viagens_por_condutor.setdefault(viagem.condutor_id, []).append(viagem)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for pernas in viagens_por_condutor.values():
            condutor = pernas[0].condutor
            intervalo = intervalo_do_condutor(db, condutor.id, data)
            nome_arquivo = nome_arquivo_seguro(f"{condutor.matricula}_{condutor.apelido or condutor.nome}")
            zip_file.writestr(f"{nome_arquivo}.pdf", _pdf_condutor_dia(pernas, intervalo))
    return buffer.getvalue()


def gerar_pdf_agendamento_condutor(db: Session, data: dt.date, condutor_id: int) -> bytes | None:
    viagens = _viagens_do_dia_com_condutor(db, data, condutor_id)
    if not viagens:
        return None
    intervalo = intervalo_do_condutor(db, condutor_id, data)
    return _pdf_condutor_dia(viagens, intervalo)


# --------------------------------------------------------------------------
# Resumo do dia (visao geral compacta, uma folha, Manha/Tarde)
# --------------------------------------------------------------------------

def _periodo_da_leg(viagem: ViagemDia) -> str:
    return "Tarde" if _hora_referencia(viagem) >= CORTE_PERIODO_TARDE else "Manha"


def _agrupar_por_condutor(viagens: list[ViagemDia]) -> list[list[ViagemDia]]:
    """Agrupa legs do mesmo condutor (ou, se sem condutor, cada carro isolado),
    na ordem cronologica -- mesmo agrupamento usado na tela de agendamento do dia.
    """
    grupos: dict[str, list[ViagemDia]] = {}
    ordem: list[str] = []
    for viagem in viagens:
        chave = f"c{viagem.condutor_id}" if viagem.condutor_id is not None else f"v{viagem.id}"
        if chave not in grupos:
            grupos[chave] = []
            ordem.append(chave)
        grupos[chave].append(viagem)

    grupos_ordenados = [grupos[chave] for chave in ordem]
    for grupo in grupos_ordenados:
        grupo.sort(key=_hora_referencia)
    grupos_ordenados.sort(key=lambda g: _hora_referencia(g[0]))
    return grupos_ordenados


_RESUMO_COL_NOME_CM = 3.3
_RESUMO_COL_HORA_CM = 0.9
_RESUMO_CARD_PADDING_PT = 3  # left/right de cada celula do mini-quadro
_RESUMO_GRID_GUTTER_CM = 0.3  # espaco entre um card e o proximo no grid


def _truncar_texto(texto: str, largura_max_pt: float, fonte: str = "Helvetica", tamanho: float = 8) -> str:
    """Corta o texto e acrescenta "..." se ele estourar `largura_max_pt`,
    pra nunca vazar pra celula vizinha do grid do resumo.
    """
    if stringWidth(texto, fonte, tamanho) <= largura_max_pt:
        return texto
    reticencias = "..."
    largura_reticencias = stringWidth(reticencias, fonte, tamanho)
    cortado = texto
    while cortado and stringWidth(cortado, fonte, tamanho) + largura_reticencias > largura_max_pt:
        cortado = cortado[:-1]
    return f"{cortado}{reticencias}" if cortado else reticencias


def _primeiro_atendimento_por_usuario(grupo: list[ViagemDia]) -> dict[int, ViagemDiaPassageiro]:
    """Um usuario pode aparecer em mais de uma leg do mesmo periodo (ex: ida e
    volta ambas de manha) -- pro resumo (enxuto) so mostra o primeiro horario.
    """
    primeiro: dict[int, ViagemDiaPassageiro] = {}
    for viagem in grupo:
        for passageiro in viagem.passageiros:
            if passageiro.status == StatusAtendimentoDia.CANCELADO:
                continue
            atual = primeiro.get(passageiro.usuario_id)
            if atual is None or passageiro.hora < atual.hora:
                primeiro[passageiro.usuario_id] = passageiro
    return primeiro


def _card_grupo_resumo(grupo: list[ViagemDia]) -> Table:
    # largura util de cada celula = largura da coluna menos padding dos dois lados
    largura_nome_pt = _RESUMO_COL_NOME_CM * cm - 2 * _RESUMO_CARD_PADDING_PT
    largura_cabecalho_pt = (_RESUMO_COL_NOME_CM + _RESUMO_COL_HORA_CM) * cm - 2 * _RESUMO_CARD_PADDING_PT

    primeira = grupo[0]
    condutor = primeira.condutor
    veiculo = primeira.veiculo
    apelido_condutor = (condutor.apelido or condutor.nome) if condutor else "Sem condutor"
    cabecalho = _truncar_texto(
        f"{veiculo.prefixo if veiculo else '-'} - {apelido_condutor}", largura_cabecalho_pt, "Helvetica-Bold"
    )

    atendimentos = sorted(_primeiro_atendimento_por_usuario(grupo).values(), key=lambda p: p.hora)
    linhas = [[cabecalho, ""]]
    for passageiro in atendimentos:
        nome = _truncar_texto(passageiro.usuario.abbr or passageiro.usuario.nome, largura_nome_pt)
        linhas.append([nome, passageiro.hora.strftime("%H:%M")])

    tabela = Table(linhas, colWidths=[_RESUMO_COL_NOME_CM * cm, _RESUMO_COL_HORA_CM * cm])
    tabela.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (-1, 0)),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), _RESUMO_CARD_PADDING_PT),
                ("RIGHTPADDING", (0, 0), (-1, -1), _RESUMO_CARD_PADDING_PT),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tabela


def _secao_periodo(elementos: list, titulo: str, grupos: list[list[ViagemDia]]) -> None:
    elementos.append(Paragraph(f"{titulo} ({len(grupos)} carro{'s' if len(grupos) != 1 else ''})", _ESTILOS["Heading3"]))
    if not grupos:
        elementos.append(Paragraph("Nenhum carro nesse periodo.", _ESTILOS["Normal"]))
        elementos.append(Spacer(1, 0.3 * cm))
        return

    colunas = 4
    cards = [_card_grupo_resumo(grupo) for grupo in grupos]
    linhas_grid = [cards[i : i + colunas] for i in range(0, len(cards), colunas)]
    for linha in linhas_grid:
        while len(linha) < colunas:
            linha.append("")

    # largura da coluna = largura do card + gutter -- com LEFTPADDING 0 e
    # RIGHTPADDING = gutter, o card cabe exatamente sem invadir a proxima
    # coluna (a causa do "um em cima do outro" era o card ficar mais largo
    # que a coluna que o continha)
    largura_coluna_cm = _RESUMO_COL_NOME_CM + _RESUMO_COL_HORA_CM + _RESUMO_GRID_GUTTER_CM
    grid = Table(linhas_grid, colWidths=[largura_coluna_cm * cm] * colunas)
    grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), _RESUMO_GRID_GUTTER_CM * cm),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elementos.append(grid)


def gerar_pdf_resumo_dia(db: Session, data: dt.date) -> bytes | None:
    """PDF enxuto (uma folha) com todo o atendimento do dia: um mini-quadro por
    carro/condutor (prefixo + apelido no cabecalho, usuario abbr + hora nas
    linhas), separado em secoes Manha/Tarde, com um resumo de contagem no final.
    """
    viagens = (
        db.query(ViagemDia)
        .options(
            joinedload(ViagemDia.condutor),
            joinedload(ViagemDia.veiculo),
            joinedload(ViagemDia.passageiros).joinedload(ViagemDiaPassageiro.usuario),
        )
        .filter(ViagemDia.data == data)
        .all()
    )
    if not viagens:
        return None

    grupos = _agrupar_por_condutor(viagens)
    grupos_manha = [g for g in grupos if _periodo_da_leg(g[0]) == "Manha"]
    grupos_tarde = [g for g in grupos if _periodo_da_leg(g[0]) == "Tarde"]

    atendimentos_manha = sum(len(_primeiro_atendimento_por_usuario(g)) for g in grupos_manha)
    atendimentos_tarde = sum(len(_primeiro_atendimento_por_usuario(g)) for g in grupos_tarde)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=1 * cm, bottomMargin=1 * cm, leftMargin=1 * cm, rightMargin=1 * cm
    )
    dia_semana_nome = _DIAS_SEMANA_PT[data.weekday()]
    elementos: list = [
        Paragraph(f"Resumo do dia {data.strftime('%d/%m/%Y')} ({dia_semana_nome})", _ESTILOS["Title"]),
        Spacer(1, 0.3 * cm),
    ]

    _secao_periodo(elementos, "Manha", grupos_manha)
    elementos.append(Spacer(1, 0.4 * cm))
    _secao_periodo(elementos, "Tarde", grupos_tarde)
    elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(Paragraph("Resumo", _ESTILOS["Heading3"]))
    tabela_resumo = Table(
        [
            ["", "Manha", "Tarde"],
            ["Carros utilizados", str(len(grupos_manha)), str(len(grupos_tarde))],
            ["Atendimentos", str(atendimentos_manha), str(atendimentos_tarde)],
        ],
        colWidths=[4 * cm, 3 * cm, 3 * cm],
    )
    tabela_resumo.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    elementos.append(tabela_resumo)

    doc.build(elementos)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Exportar escalas (jornada dos condutores no periodo)
# --------------------------------------------------------------------------

def _linhas_escala(db: Session, condutores: list, inicio: dt.date, fim: dt.date) -> list[dict]:
    condutor_ids = [c.id for c in condutores]
    frequencias = {
        (f.condutor_id, f.data): f
        for f in db.query(Frequencia).filter(
            Frequencia.condutor_id.in_(condutor_ids), Frequencia.data >= inicio, Frequencia.data <= fim
        )
    }
    ferias = list(
        db.query(CondutorFerias).filter(
            CondutorFerias.condutor_id.in_(condutor_ids),
            CondutorFerias.data_inicio <= fim,
            CondutorFerias.data_fim >= inicio,
        )
    )
    dias_ferias: dict[int, set[dt.date]] = {}
    for f in ferias:
        dias = dias_ferias.setdefault(f.condutor_id, set())
        d = max(f.data_inicio, inicio)
        limite = min(f.data_fim, fim)
        while d <= limite:
            dias.add(d)
            d += dt.timedelta(days=1)

    viagens_por_condutor_dia: dict[tuple[int, dt.date], ViagemDia] = {
        (v.condutor_id, v.data): v
        for v in db.query(ViagemDia)
        .options(joinedload(ViagemDia.passageiros))
        .filter(ViagemDia.condutor_id.in_(condutor_ids), ViagemDia.data >= inicio, ViagemDia.data <= fim)
    }

    linhas = []
    for condutor in condutores:
        condutor_label = f"{condutor.matricula} - {condutor.apelido or condutor.nome}"
        d = inicio
        while d <= fim:
            frequencia = frequencias.get((condutor.id, d))
            if frequencia is not None:
                linhas.append(
                    {
                        "condutor": condutor_label,
                        "data": d,
                        "tipo": frequencia.tipo.value,
                        "hora_entrada": frequencia.hora_entrada,
                        "intervalo_inicio": frequencia.intervalo_inicio,
                        "intervalo_fim": frequencia.intervalo_fim,
                        "hora_saida": frequencia.hora_saida,
                    }
                )
            elif d in dias_ferias.get(condutor.id, set()):
                linhas.append(
                    {
                        "condutor": condutor_label,
                        "data": d,
                        "tipo": "Ferias",
                        "hora_entrada": None,
                        "intervalo_inicio": None,
                        "intervalo_fim": None,
                        "hora_saida": None,
                    }
                )
            elif (condutor.id, d) in viagens_por_condutor_dia:
                viagem = viagens_por_condutor_dia[(condutor.id, d)]
                # sem Frequencia lancada pra esse (condutor, dia) -- ja
                # confirmado pelo "if frequencia is not None" acima -- entao
                # intervalo_do_condutor so cairia no padrao do periodo mesmo;
                # evita reconsultar Frequencia por condutor x dia no loop.
                intervalo = INTERVALO_PADRAO_POR_PERIODO.get(condutor.periodo)
                linhas.append(
                    {
                        "condutor": condutor_label,
                        "data": d,
                        "tipo": "Trabalhado",
                        "hora_entrada": viagem.horario_saida,
                        "intervalo_inicio": intervalo[0] if intervalo else None,
                        "intervalo_fim": intervalo[1] if intervalo else None,
                        "hora_saida": fim_turno_condutor(viagem),
                    }
                )
            else:
                linhas.append(
                    {
                        "condutor": condutor_label,
                        "data": d,
                        "tipo": "PENDENTE",
                        "hora_entrada": None,
                        "intervalo_inicio": None,
                        "intervalo_fim": None,
                        "hora_saida": None,
                    }
                )
            d += dt.timedelta(days=1)
    return linhas


def _formatar_hora(hora: dt.time | None) -> str:
    return hora.strftime("%H:%M") if hora else ""


def gerar_csv_escalas(db: Session, condutores: list, inicio: dt.date, fim: dt.date) -> bytes:
    linhas = _linhas_escala(db, condutores, inicio, fim)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Condutor", "Data", "Tipo", "Entrada", "Intervalo inicio", "Intervalo fim", "Saida"])
    for linha in linhas:
        writer.writerow(
            [
                linha["condutor"],
                linha["data"].strftime("%d/%m/%Y"),
                linha["tipo"],
                _formatar_hora(linha["hora_entrada"]),
                _formatar_hora(linha["intervalo_inicio"]),
                _formatar_hora(linha["intervalo_fim"]),
                _formatar_hora(linha["hora_saida"]),
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def gerar_pdf_escalas(db: Session, condutores: list, inicio: dt.date, fim: dt.date) -> bytes:
    linhas = _linhas_escala(db, condutores, inicio, fim)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm
    )
    elementos = [
        Paragraph(
            f"Escala de {inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}", _ESTILOS["Title"]
        ),
        Spacer(1, 0.5 * cm),
    ]

    cabecalho = ["Condutor", "Data", "Tipo", "Entrada", "Interv. inicio", "Interv. fim", "Saida"]
    dados = [cabecalho]
    for linha in linhas:
        dados.append(
            [
                linha["condutor"],
                linha["data"].strftime("%d/%m/%Y"),
                linha["tipo"],
                _formatar_hora(linha["hora_entrada"]),
                _formatar_hora(linha["intervalo_inicio"]),
                _formatar_hora(linha["intervalo_fim"]),
                _formatar_hora(linha["hora_saida"]),
            ]
        )

    tabela = Table(
        dados,
        colWidths=[6 * cm, 2.2 * cm, 2.3 * cm, 1.8 * cm, 2.1 * cm, 1.9 * cm, 1.7 * cm],
        repeatRows=1,
    )
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")]),
            ]
        )
    )
    elementos.append(tabela)
    doc.build(elementos)
    return buffer.getvalue()
