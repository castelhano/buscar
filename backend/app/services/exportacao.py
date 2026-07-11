import csv
import datetime as dt
import io
import re
import zipfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
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

_ESTILOS = getSampleStyleSheet()


def _nome_arquivo_seguro(nome: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", nome).strip("_") or "sem_nome"


def _hora_referencia(viagem: ViagemDia) -> dt.time:
    horas = [p.hora for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO]
    return min(horas) if horas else viagem.horario_saida


def _pdf_condutor_dia(viagens: list[ViagemDia]) -> bytes:
    """Um PDF por condutor/dia, com todas as viagens (legs) dele agrupadas
    em secoes, na ordem cronologica -- reflete o mesmo agrupamento por
    condutor usado na tela de agendamento do dia."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    elementos = []

    pernas = sorted(viagens, key=_hora_referencia)
    primeira = pernas[0]
    condutor = primeira.condutor
    veiculo = primeira.veiculo
    empresa = primeira.empresa

    elementos.append(Paragraph(f"Agendamento do dia {primeira.data.strftime('%d/%m/%Y')}", _ESTILOS["Title"]))
    dados_carro = [
        ["Empresa", empresa.nome if empresa else "-"],
        ["Veiculo", f"{veiculo.prefixo} ({veiculo.placa})" if veiculo else "-"],
        ["Condutor", condutor.nome if condutor else "-"],
    ]
    tabela_carro = Table(dados_carro, colWidths=[4 * cm, 10 * cm])
    tabela_carro.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elementos.append(tabela_carro)
    elementos.append(Spacer(1, 0.6 * cm))

    for viagem in pernas:
        sentido_ref = next(
            (p.sentido.value for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO), "-"
        )
        elementos.append(
            Paragraph(
                f"{sentido_ref} · {_hora_referencia(viagem).strftime('%H:%M')} "
                f"(regiao {viagem.regiao.nome if viagem.regiao else '-'}, "
                f"saida da garagem {viagem.horario_saida.strftime('%H:%M')})",
                _ESTILOS["Heading3"],
            )
        )

        linhas = [["Hora", "Sentido", "Origem", "Destino", "Observacoes"]]
        passageiros = sorted(
            (p for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO),
            key=lambda p: (p.hora, p.usuario.nome),
        )
        for passageiro in passageiros:
            observacoes = passageiro.observacoes or ""
            if passageiro.status == StatusAtendimentoDia.EM_ANALISE:
                observacoes = (f"[EM ANALISE] {observacoes}").strip()
            linhas.append(
                [
                    passageiro.hora.strftime("%H:%M"),
                    passageiro.sentido.value,
                    passageiro.origem or "-",
                    passageiro.destino.nome if passageiro.destino else "-",
                    observacoes,
                ]
            )

        tabela = Table(linhas, colWidths=[2 * cm, 2.3 * cm, 4.5 * cm, 4.5 * cm, 4.5 * cm], repeatRows=1)
        tabela.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f4")]),
                ]
            )
        )
        elementos.append(tabela)
        elementos.append(Spacer(1, 0.6 * cm))

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
            nome_arquivo = _nome_arquivo_seguro(f"{condutor.matricula}_{condutor.apelido or condutor.nome}")
            zip_file.writestr(f"{nome_arquivo}.pdf", _pdf_condutor_dia(pernas))
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
        d = inicio
        while d <= fim:
            frequencia = frequencias.get((condutor.id, d))
            if frequencia is not None:
                linhas.append(
                    {
                        "condutor": condutor.nome,
                        "data": d,
                        "tipo": frequencia.tipo.value,
                        "hora_entrada": frequencia.hora_entrada,
                        "intervalo_inicio": frequencia.intervalo_inicio,
                        "intervalo_fim": frequencia.intervalo_fim,
                        "hora_saida": frequencia.hora_saida,
                        "observacao": frequencia.observacao or "",
                    }
                )
            elif d in dias_ferias.get(condutor.id, set()):
                linhas.append(
                    {
                        "condutor": condutor.nome,
                        "data": d,
                        "tipo": "Ferias",
                        "hora_entrada": None,
                        "intervalo_inicio": None,
                        "intervalo_fim": None,
                        "hora_saida": None,
                        "observacao": "",
                    }
                )
            elif (condutor.id, d) in viagens_por_condutor_dia:
                viagem = viagens_por_condutor_dia[(condutor.id, d)]
                linhas.append(
                    {
                        "condutor": condutor.nome,
                        "data": d,
                        "tipo": "Trabalhado",
                        "hora_entrada": viagem.horario_saida,
                        "intervalo_inicio": None,
                        "intervalo_fim": None,
                        "hora_saida": None,
                        "observacao": "",
                    }
                )
            else:
                linhas.append(
                    {
                        "condutor": condutor.nome,
                        "data": d,
                        "tipo": "PENDENTE",
                        "hora_entrada": None,
                        "intervalo_inicio": None,
                        "intervalo_fim": None,
                        "hora_saida": None,
                        "observacao": "",
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
    writer.writerow(["Condutor", "Data", "Tipo", "Entrada", "Intervalo inicio", "Intervalo fim", "Saida", "Observacao"])
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
                linha["observacao"],
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def gerar_pdf_escalas(db: Session, condutores: list, inicio: dt.date, fim: dt.date) -> bytes:
    linhas = _linhas_escala(db, condutores, inicio, fim)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    elementos = [
        Paragraph(
            f"Escala de {inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}", _ESTILOS["Title"]
        ),
        Spacer(1, 0.5 * cm),
    ]

    cabecalho = ["Condutor", "Data", "Tipo", "Entrada", "Interv. inicio", "Interv. fim", "Saida", "Observacao"]
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
                linha["observacao"],
            ]
        )

    tabela = Table(
        dados,
        colWidths=[3 * cm, 2 * cm, 2.2 * cm, 1.8 * cm, 2.2 * cm, 1.8 * cm, 1.8 * cm, 4 * cm],
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
