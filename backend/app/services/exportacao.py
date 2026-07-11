import csv
import datetime as dt
import io
import re
import zipfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, joinedload

from app.models import (
    CondutorFerias,
    Frequencia,
    StatusAtendimentoDia,
    StatusCondutor,
    ViagemDia,
    ViagemDiaPassageiro,
)
from app.services.frequencia import intervalo_do_condutor
from app.services.recursos import fim_turno_condutor, fim_viagem

_ESTILOS = getSampleStyleSheet()
_ESTILO_CABECALHO_DIA = ParagraphStyle("CabecalhoDia", parent=_ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=16)
_ESTILO_CABECALHO_CONDUTOR = ParagraphStyle("CabecalhoCondutor", parent=_ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=13)

_DIAS_SEMANA_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}


def _nome_arquivo_seguro(nome: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", nome).strip("_") or "sem_nome"


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

    linhas: list[list[str]] = [["Hora", "Usuario", "Sentido", "Origem", "Destino", "Observacoes"]]
    linhas.append([hora_inicio, "--", "Acesso", empresa_garagem, "-", ""])

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
                    nome,
                    passageiro.sentido.value,
                    passageiro.origem or "-",
                    passageiro.destino.nome if passageiro.destino else "-",
                    observacoes,
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


def gerar_zip_agendamentos(db: Session, data: dt.date) -> bytes | None:
    viagens = (
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
        .all()
    )
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
            nome_arquivo = _nome_arquivo_seguro(f"{condutor.matricula}_{condutor.apelido or condutor.nome}")
            zip_file.writestr(f"{nome_arquivo}.pdf", _pdf_condutor_dia(pernas, intervalo))
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
        for v in db.query(ViagemDia).filter(
            ViagemDia.condutor_id.in_(condutor_ids), ViagemDia.data >= inicio, ViagemDia.data <= fim
        )
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
                intervalo = intervalo_do_condutor(db, condutor.id, d)
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
