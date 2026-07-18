import csv
import datetime as dt
import io
import re
import zipfile
from dataclasses import dataclass
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models import (
    CondutorFerias,
    DiaSemana,
    Frequencia,
    GrupoRevezamento,
    GrupoRevezamentoCondutor,
    Sentido,
    StatusAtendimentoDia,
    StatusCondutor,
    ViagemDia,
    ViagemDiaPassageiro,
)
from app.services.base import montar_estrutura_base
from app.services.frequencia import INTERVALO_PADRAO_POR_PERIODO, intervalo_do_condutor
from app.services.geracao import CORTE_PERIODO_TARDE
from app.services.recursos import fim_turno_condutor, fim_viagem

_ESTILOS = getSampleStyleSheet()
_ESTILO_CABECALHO_DIA = ParagraphStyle("CabecalhoDia", parent=_ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=16, leading=19)
_ESTILO_CABECALHO_CONDUTOR = ParagraphStyle("CabecalhoCondutor", parent=_ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=16)
# Celulas de texto longo (Usuario/Origem/Destino/Observacoes) usam Paragraph em
# vez de string pura -- string pura e desenhada com drawString (uma linha so,
# sem quebra), o texto longo vazava da celula. Com Paragraph o ReportLab quebra
# respeitando a largura da coluna e a Table recalcula a altura da linha sozinha.
_ESTILO_CELULA = ParagraphStyle("Celula", parent=_ESTILOS["Normal"], fontName="Helvetica", fontSize=11, leading=13)
# Endereco detalhado (Usuario.detalhe / Local.observacao) e um complemento do
# texto principal da celula, exibido menor pra nao competir com ele.
_TAMANHO_FONTE_DETALHE = 9

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


def _com_detalhe(texto: str, detalhe: str | None) -> Paragraph:
    """Texto principal da celula + endereco detalhado numa linha extra, menor."""
    html = escape(texto)
    if detalhe:
        html += f'<br/><font size="{_TAMANHO_FONTE_DETALHE}">{escape(detalhe)}</font>'
    return Paragraph(html, _ESTILO_CELULA)


def _dados_origem(passageiro: ViagemDiaPassageiro) -> tuple[str, str | None]:
    if passageiro.sentido == Sentido.RETORNO:
        destino = passageiro.destino
        return (destino.nome if destino else "-", destino.observacao if destino else None)
    return (passageiro.origem or "-", passageiro.usuario.detalhe)


def _dados_destino(passageiro: ViagemDiaPassageiro) -> tuple[str, str | None]:
    if passageiro.sentido == Sentido.RETORNO:
        return (passageiro.origem or "-", passageiro.usuario.detalhe)
    destino = passageiro.destino
    return (destino.nome if destino else "-", destino.observacao if destino else None)


def _hora_referencia(viagem: ViagemDia) -> dt.time:
    horas = [p.hora for p in viagem.passageiros if p.status != StatusAtendimentoDia.CANCELADO]
    return min(horas) if horas else viagem.horario_saida


# Celula generica: texto principal + detalhe opcional (endereco/observacao,
# exibido menor). Linha do intervalo usa uma unica celula (texto, None) na
# coluna 0 e o resto vazio -- quem renderiza (PDF ou PNG) faz o merge visual.
_Celula = tuple[str, str | None]


@dataclass
class _DadosCondutorDia:
    titulo_dia: str
    titulo_condutor: str
    linhas: list[list[_Celula]]
    limites_leg: list[int]
    linha_intervalo: int | None


def _montar_dados_condutor_dia(
    viagens: list[ViagemDia], intervalo: tuple[dt.time, dt.time] | None = None
) -> _DadosCondutorDia:
    """Monta o conteudo da tabela de agendamento (cabecalhos + linhas) de um
    condutor/dia, com todas as viagens (legs) dele numa unica tabela continua,
    na ordem cronologica -- reflete o mesmo agrupamento por condutor usado na
    tela de agendamento do dia. Usado tanto pelo PDF quanto pelo PNG.

    A primeira linha da tabela e o "Acesso" (saida da garagem, uma unica vez
    no dia); as legs seguintes emendam direto, sem nova saida de garagem --
    uma borda mais grossa so marca a troca de horario/leg. O intervalo do
    condutor entra como uma linha mesclada na posicao cronologica correta.
    """
    pernas = sorted(viagens, key=_hora_referencia)
    primeira = pernas[0]
    ultima = pernas[-1]
    condutor = primeira.condutor
    veiculo = primeira.veiculo
    regiao = primeira.regiao

    hora_inicio = primeira.horario_saida.strftime("%H:%M")
    hora_fim = fim_turno_condutor(ultima).strftime("%H:%M")
    dia_semana_nome = _DIAS_SEMANA_PT[primeira.data.weekday()]

    titulo_dia = f"{primeira.data.strftime('%d/%m/%Y')} ({dia_semana_nome}) - {regiao.nome if regiao else '-'}"
    titulo_condutor = (
        f"{condutor.matricula if condutor else '-'} {condutor.nome if condutor else '-'} "
        f"{hora_inicio} - {hora_fim} | VEICULO: {veiculo.prefixo if veiculo else '-'}"
    )

    empresa_garagem = veiculo.empresa.nome if veiculo and veiculo.empresa else (primeira.empresa.nome if primeira.empresa else "-")

    linhas: list[list[_Celula]] = [
        [("Hora", None), ("Usuario", None), ("Sentido", None), ("Origem", None), ("Destino", None), ("Observacoes", None)]
    ]
    linhas.append([(hora_inicio, None), ("--", None), ("Acesso", None), (empresa_garagem, None), ("-", None), ("", None)])

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
            nome = passageiro.usuario.abbr or passageiro.usuario.nome
            if passageiro.acompanhante:
                nome = f"{nome} + ACOMP"
            linhas.append(
                [
                    (passageiro.hora.strftime("%H:%M"), None),
                    (nome, None),
                    (passageiro.sentido.value, None),
                    _dados_origem(passageiro),
                    _dados_destino(passageiro),
                    (observacoes, None),
                ]
            )

        if not intervalo_inserido:
            proxima = pernas[indice + 1] if indice + 1 < len(pernas) else None
            cabe_antes_da_proxima = proxima is None or intervalo[1] <= proxima.horario_saida
            if intervalo[0] >= fim_viagem(viagem) and cabe_antes_da_proxima:
                linha_intervalo = len(linhas)
                texto_intervalo = f"INTERVALO {intervalo[0].strftime('%H:%M')} as {intervalo[1].strftime('%H:%M')}"
                linhas.append([(texto_intervalo, None), ("", None), ("", None), ("", None), ("", None), ("", None)])
                intervalo_inserido = True

    if not intervalo_inserido:
        linha_intervalo = len(linhas)
        texto_intervalo = f"INTERVALO {intervalo[0].strftime('%H:%M')} as {intervalo[1].strftime('%H:%M')}"
        linhas.append([(texto_intervalo, None), ("", None), ("", None), ("", None), ("", None), ("", None)])

    # Caixa alta em tudo -- facilita a leitura rapida do condutor durante a viagem.
    return _DadosCondutorDia(
        titulo_dia=titulo_dia.upper(),
        titulo_condutor=titulo_condutor.upper(),
        linhas=[[(texto.upper(), detalhe.upper() if detalhe else detalhe) for texto, detalhe in linha] for linha in linhas],
        limites_leg=limites_leg,
        linha_intervalo=linha_intervalo,
    )


def _pdf_condutor_dia(viagens: list[ViagemDia], intervalo: tuple[dt.time, dt.time] | None = None) -> bytes:
    """Renderiza os dados de `_montar_dados_condutor_dia` como PDF (reportlab)."""
    dados = _montar_dados_condutor_dia(viagens, intervalo)

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
    elementos.append(Paragraph(dados.titulo_dia, _ESTILO_CABECALHO_DIA))
    elementos.append(Paragraph(dados.titulo_condutor, _ESTILO_CABECALHO_CONDUTOR))
    elementos.append(Spacer(1, 0.4 * cm))

    limites_leg = dados.limites_leg
    linha_intervalo = dados.linha_intervalo

    linhas: list[list] = [[texto for texto, _ in dados.linhas[0]]]
    for indice, linha in enumerate(dados.linhas[1:], start=1):
        if indice == linha_intervalo:
            linhas.append([texto for texto, _ in linha])
        else:
            linhas.append([_com_detalhe(texto, detalhe) if texto or detalhe else "" for texto, detalhe in linha])

    tabela = Table(linhas, colWidths=[2 * cm, 6.5 * cm, 2.3 * cm, 5.4 * cm, 5.4 * cm, 5.1 * cm], repeatRows=1)
    estilos = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
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


# --------------------------------------------------------------------------
# PNG (mesma tabela do PDF, mas so a area de interesse, com margem pequena --
# util pra colar num chat/WhatsApp sem o "papel" A4 em volta).
# --------------------------------------------------------------------------

_PNG_COL_LARGURAS = [90, 300, 105, 245, 245, 235]  # px, mesma proporcao das colWidths do PDF
_PNG_MARGEM = 14
_PNG_PADDING_CELULA = 6
_PNG_COR_CABECALHO_BG = (45, 55, 72)  # #2d3748
_PNG_COR_CABECALHO_TXT = (255, 255, 255)
_PNG_COR_LINHA_PAR = (244, 244, 244)  # #f4f4f4
_PNG_COR_LINHA_IMPAR = (255, 255, 255)
_PNG_COR_INTERVALO_BG = (226, 232, 240)  # #e2e8f0
_PNG_COR_GRADE = (128, 128, 128)
_PNG_COR_TEXTO = (0, 0, 0)


def _fonte_png(negrito: bool, tamanho: int) -> ImageFont.FreeTypeFont:
    caminhos = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if negrito
        else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for caminho in caminhos:
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default(size=tamanho)


def _quebrar_texto(texto: str, fonte: ImageFont.FreeTypeFont, largura_max: float) -> list[str]:
    linhas: list[str] = []
    for paragrafo in texto.splitlines() or [""]:
        palavras = paragrafo.split(" ")
        atual = ""
        for palavra in palavras:
            candidata = f"{atual} {palavra}".strip()
            if fonte.getlength(candidata) <= largura_max or not atual:
                atual = candidata
            else:
                linhas.append(atual)
                atual = palavra
        linhas.append(atual)
    return linhas or [""]


def _png_condutor_dia(viagens: list[ViagemDia], intervalo: tuple[dt.time, dt.time] | None = None) -> bytes:
    """Renderiza os dados de `_montar_dados_condutor_dia` como PNG, recortado
    so na area da tabela (sem margem de pagina A4 como no PDF)."""
    dados = _montar_dados_condutor_dia(viagens, intervalo)

    fonte_titulo_dia = _fonte_png(True, 24)
    fonte_titulo_condutor = _fonte_png(True, 20)
    fonte_cabecalho = _fonte_png(True, 18)
    fonte_celula = _fonte_png(False, 18)
    fonte_detalhe = _fonte_png(False, 14)

    largura_tabela = sum(_PNG_COL_LARGURAS)
    largura_total = largura_tabela + 2 * _PNG_MARGEM

    def altura_texto(fonte: ImageFont.FreeTypeFont) -> int:
        bbox = fonte.getbbox("Ag")
        return bbox[3] - bbox[1]

    linha_intervalo = dados.linha_intervalo
    linhas_layout: list[tuple[int, list[list[str]], list[list[str]]]] = []
    for indice, linha in enumerate(dados.linhas):
        if indice == linha_intervalo:
            texto0 = linha[0][0]
            n_linhas = max(1, len(_quebrar_texto(texto0, fonte_celula, largura_tabela - 2 * _PNG_PADDING_CELULA)))
            altura = 2 * _PNG_PADDING_CELULA + n_linhas * (altura_texto(fonte_celula) + 4)
            linhas_layout.append((altura, [], []))
            continue
        if indice == 0:
            fonte = fonte_cabecalho
            maior_altura = 0
            linhas_texto_cabecalho: list[list[str]] = []
            for coluna, (texto, _detalhe) in enumerate(linha):
                largura_util = _PNG_COL_LARGURAS[coluna] - 2 * _PNG_PADDING_CELULA
                texto_quebrado = _quebrar_texto(texto, fonte, largura_util)
                linhas_texto_cabecalho.append(texto_quebrado)
                maior_altura = max(maior_altura, 2 * _PNG_PADDING_CELULA + len(texto_quebrado) * (altura_texto(fonte) + 3))
            linhas_layout.append((maior_altura, linhas_texto_cabecalho, []))
            continue
        linhas_texto: list[list[str]] = []
        linhas_detalhe: list[list[str]] = []
        maior_altura = 0
        for coluna, (texto, detalhe) in enumerate(linha):
            largura_util = _PNG_COL_LARGURAS[coluna] - 2 * _PNG_PADDING_CELULA
            texto_quebrado = _quebrar_texto(texto, fonte_celula, largura_util) if texto else [""]
            detalhe_quebrado = _quebrar_texto(detalhe, fonte_detalhe, largura_util) if detalhe else []
            linhas_texto.append(texto_quebrado)
            linhas_detalhe.append(detalhe_quebrado)
            altura_coluna = (
                2 * _PNG_PADDING_CELULA
                + len(texto_quebrado) * (altura_texto(fonte_celula) + 3)
                + len(detalhe_quebrado) * (altura_texto(fonte_detalhe) + 3)
            )
            maior_altura = max(maior_altura, altura_coluna)
        linhas_layout.append((maior_altura, linhas_texto, linhas_detalhe))

    altura_titulos = (
        altura_texto(fonte_titulo_dia) + 6 + altura_texto(fonte_titulo_condutor) + 16
    )
    altura_tabela = sum(altura for altura, _, _ in linhas_layout)
    altura_total = 2 * _PNG_MARGEM + altura_titulos + altura_tabela

    imagem = Image.new("RGB", (largura_total, altura_total), (255, 255, 255))
    desenho = ImageDraw.Draw(imagem)

    y = _PNG_MARGEM
    desenho.text((_PNG_MARGEM, y), dados.titulo_dia, font=fonte_titulo_dia, fill=_PNG_COR_TEXTO)
    y += altura_texto(fonte_titulo_dia) + 6
    desenho.text((_PNG_MARGEM, y), dados.titulo_condutor, font=fonte_titulo_condutor, fill=_PNG_COR_TEXTO)
    y += altura_texto(fonte_titulo_condutor) + 16

    for indice, (linha, (altura, linhas_texto, linhas_detalhe)) in enumerate(zip(dados.linhas, linhas_layout)):
        eh_cabecalho = indice == 0
        eh_intervalo = indice == linha_intervalo
        x0 = _PNG_MARGEM
        if eh_cabecalho:
            desenho.rectangle([x0, y, x0 + largura_tabela, y + altura], fill=_PNG_COR_CABECALHO_BG)
        elif eh_intervalo:
            desenho.rectangle([x0, y, x0 + largura_tabela, y + altura], fill=_PNG_COR_INTERVALO_BG)
        else:
            cor_fundo = _PNG_COR_LINHA_IMPAR if indice % 2 == 1 else _PNG_COR_LINHA_PAR
            desenho.rectangle([x0, y, x0 + largura_tabela, y + altura], fill=cor_fundo)

        if eh_intervalo:
            texto0 = linha[0][0]
            largura_linha = fonte_celula.getlength(texto0)
            xc = x0 + (largura_tabela - largura_linha) / 2
            desenho.text((xc, y + _PNG_PADDING_CELULA), texto0, font=fonte_celula, fill=_PNG_COR_TEXTO)
        elif eh_cabecalho:
            x = x0
            for coluna, largura_col in enumerate(_PNG_COL_LARGURAS):
                ty = y + _PNG_PADDING_CELULA
                for texto_linha in linhas_texto[coluna]:
                    desenho.text((x + _PNG_PADDING_CELULA, ty), texto_linha, font=fonte_cabecalho, fill=_PNG_COR_CABECALHO_TXT)
                    ty += altura_texto(fonte_cabecalho) + 3
                x += largura_col
        else:
            x = x0
            for coluna, largura_col in enumerate(_PNG_COL_LARGURAS):
                ty = y + _PNG_PADDING_CELULA
                for texto_linha in linhas_texto[coluna]:
                    desenho.text((x + _PNG_PADDING_CELULA, ty), texto_linha, font=fonte_celula, fill=_PNG_COR_TEXTO)
                    ty += altura_texto(fonte_celula) + 3
                for detalhe_linha in linhas_detalhe[coluna]:
                    desenho.text((x + _PNG_PADDING_CELULA, ty), detalhe_linha, font=fonte_detalhe, fill=(90, 90, 90))
                    ty += altura_texto(fonte_detalhe) + 3
                x += largura_col

        # grade vertical entre colunas -- na linha do intervalo as colunas sao
        # mescladas visualmente (igual ao SPAN do PDF), so a borda externa fica.
        x = x0
        if eh_intervalo:
            desenho.line([(x0, y), (x0, y + altura)], fill=_PNG_COR_GRADE, width=1)
        else:
            for largura_col in _PNG_COL_LARGURAS:
                desenho.line([(x, y), (x, y + altura)], fill=_PNG_COR_GRADE, width=1)
                x += largura_col
        desenho.line([(x0 + largura_tabela, y), (x0 + largura_tabela, y + altura)], fill=_PNG_COR_GRADE, width=1)

        borda_grossa = indice in dados.limites_leg
        desenho.line([(x0, y), (x0 + largura_tabela, y)], fill=_PNG_COR_CABECALHO_BG if borda_grossa else _PNG_COR_GRADE, width=2 if borda_grossa else 1)
        y += altura

    desenho.line([(_PNG_MARGEM, y), (_PNG_MARGEM + largura_tabela, y)], fill=_PNG_COR_GRADE, width=1)

    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    return buffer.getvalue()


def _viagens_do_dia(
    db: Session, data: dt.date, condutor_id: int | None = None, bloco_id: int | None = None
) -> list[ViagemDia]:
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
        .filter(ViagemDia.data == data)
    )
    if condutor_id is not None:
        query = query.filter(ViagemDia.condutor_id == condutor_id)
    elif bloco_id is not None:
        query = query.filter(
            or_(ViagemDia.id == bloco_id, ViagemDia.grupo_viagem_id == bloco_id)
        )
    return query.all()


def _bloco_do_carro(viagem: ViagemDia) -> int:
    """Ancora do bloco (carro) que a leg pertence -- mesma chave usada na tela
    do dia (`agruparPorBloco` no frontend) pra emendar as pernas de um mesmo
    carro independente de condutor/veiculo estarem atribuidos.
    """
    return viagem.grupo_viagem_id if viagem.grupo_viagem_id is not None else viagem.id


def _agrupar_para_exportacao(viagens: list[ViagemDia]) -> list[list[ViagemDia]]:
    """Uma leg com condutor atribuido agrupa por condutor (todas as legs dele
    no dia, mesmo que em carros diferentes, viram um so PDF); sem condutor,
    agrupa pelas legs do mesmo carro (bloco), um PDF por carro "Indefinido".
    """
    grupos: dict[str, list[ViagemDia]] = {}
    ordem: list[str] = []
    for viagem in viagens:
        chave = f"c{viagem.condutor_id}" if viagem.condutor_id is not None else f"b{_bloco_do_carro(viagem)}"
        if chave not in grupos:
            grupos[chave] = []
            ordem.append(chave)
        grupos[chave].append(viagem)
    return [grupos[chave] for chave in ordem]


def gerar_zip_agendamentos(db: Session, data: dt.date) -> bytes | None:
    viagens = _viagens_do_dia(db, data)
    if not viagens:
        return None

    buffer = io.BytesIO()
    indefinido_seq = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for pernas in _agrupar_para_exportacao(viagens):
            condutor = pernas[0].condutor
            if condutor is not None:
                intervalo = intervalo_do_condutor(db, condutor.id, data)
                nome_arquivo = nome_arquivo_seguro(f"{condutor.matricula}_{condutor.apelido or condutor.nome}")
            else:
                intervalo = None
                indefinido_seq += 1
                nome_arquivo = f"Indefinido_{indefinido_seq}"
            zip_file.writestr(f"{nome_arquivo}.pdf", _pdf_condutor_dia(pernas, intervalo))
    return buffer.getvalue()


def gerar_pdf_agendamento_condutor(db: Session, data: dt.date, condutor_id: int) -> bytes | None:
    viagens = _viagens_do_dia(db, data, condutor_id=condutor_id)
    if not viagens:
        return None
    intervalo = intervalo_do_condutor(db, condutor_id, data)
    return _pdf_condutor_dia(viagens, intervalo)


def gerar_pdf_agendamento_bloco(db: Session, data: dt.date, bloco_id: int) -> bytes | None:
    """Carro sem condutor atribuido -- exporta pelas legs do bloco em vez de
    condutor_id (ver `_bloco_do_carro`).
    """
    viagens = _viagens_do_dia(db, data, bloco_id=bloco_id)
    if not viagens:
        return None
    return _pdf_condutor_dia(viagens, None)


def gerar_zip_agendamentos_png(db: Session, data: dt.date) -> bytes | None:
    viagens = _viagens_do_dia(db, data)
    if not viagens:
        return None

    buffer = io.BytesIO()
    indefinido_seq = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for pernas in _agrupar_para_exportacao(viagens):
            condutor = pernas[0].condutor
            if condutor is not None:
                intervalo = intervalo_do_condutor(db, condutor.id, data)
                nome_arquivo = nome_arquivo_seguro(f"{condutor.matricula}_{condutor.apelido or condutor.nome}")
            else:
                intervalo = None
                indefinido_seq += 1
                nome_arquivo = f"Indefinido_{indefinido_seq}"
            zip_file.writestr(f"{nome_arquivo}.png", _png_condutor_dia(pernas, intervalo))
    return buffer.getvalue()


def gerar_png_agendamento_condutor(db: Session, data: dt.date, condutor_id: int) -> bytes | None:
    viagens = _viagens_do_dia(db, data, condutor_id=condutor_id)
    if not viagens:
        return None
    intervalo = intervalo_do_condutor(db, condutor_id, data)
    return _png_condutor_dia(viagens, intervalo)


def gerar_png_agendamento_bloco(db: Session, data: dt.date, bloco_id: int) -> bytes | None:
    """Carro sem condutor atribuido -- ver `gerar_pdf_agendamento_bloco`."""
    viagens = _viagens_do_dia(db, data, bloco_id=bloco_id)
    if not viagens:
        return None
    return _png_condutor_dia(viagens, None)


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
# Ocupacao do modo Base (perfil de ocupacao por carro/horario)
# --------------------------------------------------------------------------

CAPACIDADE_VIAGEM_BASE = 4

_DIA_SEMANA_LABEL_PT = {
    DiaSemana.SEG: "Segunda",
    DiaSemana.TER: "Terca",
    DiaSemana.QUA: "Quarta",
    DiaSemana.QUI: "Quinta",
    DiaSemana.SEX: "Sexta",
    DiaSemana.SAB: "Sabado",
    DiaSemana.DOM: "Domingo",
}

_COR_OCUPACAO_LIVRE = colors.HexColor("#e6f4ea")
_COR_OCUPACAO_LOTADO = colors.HexColor("#e2e5ea")
_COR_OCUPACAO_ACIMA = colors.HexColor("#f3dcda")
_COR_OCUPACAO_VAZIA = colors.HexColor("#fafafb")

_ESTILO_OCUPACAO_CABECALHO = ParagraphStyle(
    "OcupacaoCabecalho",
    parent=_ESTILOS["Normal"],
    fontName="Helvetica-Bold",
    fontSize=8.5,
    leading=10,
    alignment=1,
    textColor=colors.white,
)
_ESTILO_OCUPACAO_CELULA = ParagraphStyle(
    "OcupacaoCelula", parent=_ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=11, alignment=1
)
_ESTILO_OCUPACAO_HORA = ParagraphStyle(
    "OcupacaoHora", parent=_ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11
)
_ESTILO_OCUPACAO_TOTAL = ParagraphStyle(
    "OcupacaoTotal", parent=_ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=11, alignment=1
)
_ESTILO_OCUPACAO_PERCENTUAL = ParagraphStyle(
    "OcupacaoPercentual",
    parent=_ESTILOS["Normal"],
    fontName="Helvetica-Oblique",
    fontSize=8.5,
    leading=10,
    alignment=1,
    textColor=colors.HexColor("#667085"),
)
_ESTILO_OCUPACAO_TITULO = ParagraphStyle("OcupacaoTitulo", parent=_ESTILOS["Title"], alignment=0)
_ESTILO_OCUPACAO_CABECALHO_SECAO = ParagraphStyle(
    "OcupacaoCabecalhoSecao", parent=_ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=13
)


def _status_ocupacao_base(ocupados: int, capacidade: int) -> str:
    if ocupados > capacidade:
        return "acima"
    if ocupados == capacidade:
        return "lotado"
    return "livre"


def _cor_status_ocupacao(status: str):
    return {"livre": _COR_OCUPACAO_LIVRE, "lotado": _COR_OCUPACAO_LOTADO, "acima": _COR_OCUPACAO_ACIMA}[status]


def _ocupados_viagem_base(viagem: dict) -> int:
    return sum((2 if m["acompanhante"] else 1) for m in viagem["membros"] if m["usuario_ativo"])


def _formatar_hora(hora: dt.time) -> str:
    return hora.strftime("%H:%M")


def _percentual(parte: int, total: int) -> str:
    if total <= 0:
        return "–"
    return f"{round(parte / total * 100)}%"


def _horas_dos_grupos(grupos: list[dict]) -> list[dt.time]:
    return sorted({v["hora"] for g in grupos for v in g["viagens"]})


def _periodo_da_hora_base(hora: dt.time) -> str:
    return "Tarde" if hora >= CORTE_PERIODO_TARDE else "Manha"


def _montar_matriz_dia_simples(grupos: list[dict], periodo: str | None = None) -> dict:
    """Linhas = horario, colunas = carro (posicao no dia) -- visao de um dia so.

    Quando `periodo` e informado, restringe carros/horarios aquele periodo --
    carros sem viagem nele nao entram como coluna, evitando colunas/linhas em
    branco quando o dia mistura carros de manha e de tarde.
    """
    grupos_periodo = (
        grupos
        if periodo is None
        else [g for g in grupos if any(_periodo_da_hora_base(v["hora"]) == periodo for v in g["viagens"])]
    )
    horas = [h for h in _horas_dos_grupos(grupos_periodo) if periodo is None or _periodo_da_hora_base(h) == periodo]
    linhas = []
    for hora in horas:
        por_carro = []
        total_ocupados = 0
        for grupo in grupos_periodo:
            viagens_na_hora = [v for v in grupo["viagens"] if v["hora"] == hora]
            if not viagens_na_hora:
                por_carro.append(None)
                continue
            ocupados = sum(_ocupados_viagem_base(v) for v in viagens_na_hora)
            total_ocupados += ocupados
            por_carro.append({"ocupados": ocupados, "status": _status_ocupacao_base(ocupados, CAPACIDADE_VIAGEM_BASE)})
        linhas.append({"hora": hora, "por_carro": por_carro, "total_ocupados": total_ocupados})

    total_por_carro = [
        sum(linha["por_carro"][i]["ocupados"] for linha in linhas if linha["por_carro"][i] is not None)
        for i in range(len(grupos_periodo))
    ]
    return {
        "total_carros": len(grupos_periodo),
        "linhas": linhas,
        "total_por_carro": total_por_carro,
        "total_geral": sum(total_por_carro),
    }


def _montar_matriz_semana(estruturas: list[tuple[DiaSemana, dict]]) -> dict:
    """Linhas = horario, colunas = dia da semana -- os carros de cada dia sao
    somados (ocupado/capacidade), ja que nao tem identidade estavel entre
    dias diferentes."""
    todos_grupos = [g for _, estrutura in estruturas for g in estrutura["grupos"]]
    horas = _horas_dos_grupos(todos_grupos)
    linhas = []
    for hora in horas:
        total_ocupados = 0
        total_capacidade = 0
        por_dia = []
        for _, estrutura in estruturas:
            ocupados = 0
            n_carros = 0
            for grupo in estrutura["grupos"]:
                viagens_na_hora = [v for v in grupo["viagens"] if v["hora"] == hora]
                if not viagens_na_hora:
                    continue
                n_carros += 1
                ocupados += sum(_ocupados_viagem_base(v) for v in viagens_na_hora)
            if n_carros == 0:
                por_dia.append(None)
                continue
            capacidade = n_carros * CAPACIDADE_VIAGEM_BASE
            total_ocupados += ocupados
            total_capacidade += capacidade
            por_dia.append({"ocupados": ocupados, "capacidade": capacidade, "status": _status_ocupacao_base(ocupados, capacidade)})
        linhas.append({"hora": hora, "por_dia": por_dia, "total_ocupados": total_ocupados, "total_capacidade": total_capacidade})

    total_por_dia = []
    for i in range(len(estruturas)):
        ocupados = sum(linha["por_dia"][i]["ocupados"] for linha in linhas if linha["por_dia"][i] is not None)
        capacidade = sum(linha["por_dia"][i]["capacidade"] for linha in linhas if linha["por_dia"][i] is not None)
        total_por_dia.append({"ocupados": ocupados, "capacidade": capacidade})
    total_geral = {
        "ocupados": sum(t["ocupados"] for t in total_por_dia),
        "capacidade": sum(t["capacidade"] for t in total_por_dia),
    }
    return {"linhas": linhas, "total_por_dia": total_por_dia, "total_geral": total_geral}


def gerar_pdf_ocupacao_base(db: Session, dias: list[DiaSemana], modo_semana: bool) -> bytes | None:
    """PDF da matriz de ocupacao do modo Base, pensado pra apresentacao formal
    (orgao gestor): linhas = horario, colunas = carro (visao de um dia) ou dia
    da semana com os carros agregados (visao da semana toda). Cada celula
    mostra a ocupacao colorida (verde = com vaga, cinza = lotado, vermelho
    suave = acima da capacidade assumida de `CAPACIDADE_VIAGEM_BASE` lugares
    por viagem); horarios sem viagem cadastrada ficam neutros. Dias sem
    nenhum carro sao descartados (evita colunas em branco no relatorio).
    """
    estruturas = [(dia, montar_estrutura_base(db, dia)) for dia in dias]
    estruturas = [(dia, estrutura) for dia, estrutura in estruturas if estrutura["grupos"]]
    if not estruturas:
        return None

    margem = 1.2 * cm
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=margem, bottomMargin=margem, leftMargin=margem, rightMargin=margem)
    largura_util = A4[0] - 2 * margem

    gerado_em = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    elementos: list = [
        Paragraph("Perfil de Ocupação - Sistema Buscar", _ESTILO_OCUPACAO_TITULO),
        Paragraph(
            f"Gerado em {gerado_em} -- capacidade assumida de {CAPACIDADE_VIAGEM_BASE} lugares por viagem", _ESTILO_CELULA
        ),
        Spacer(1, 0.4 * cm),
    ]

    linhas: list = []
    cores_celulas: list[tuple[int, int, object]] = []
    largura_horario = 2.2 * cm
    largura_total = 1.7 * cm
    largura_percentual = 1.3 * cm

    def _tabela_ocupacao(linhas: list, cores_celulas: list, n_colunas_dado: int) -> Table:
        linha_idx_total = len(linhas) - 1
        largura_dado = min(1.7 * cm, (largura_util - largura_horario - largura_total - largura_percentual) / n_colunas_dado)
        col_widths = [largura_horario] + [largura_dado] * n_colunas_dado + [largura_total, largura_percentual]

        tabela = Table(linhas, colWidths=col_widths, repeatRows=1)
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3d4d63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEABOVE", (0, linha_idx_total), (-1, linha_idx_total), 1.2, colors.HexColor("#2d3748")),
            ("BACKGROUND", (0, linha_idx_total), (-1, linha_idx_total), colors.HexColor("#eef1f4")),
        ]
        for linha_idx, col_idx, cor in cores_celulas:
            estilo.append(("BACKGROUND", (col_idx, linha_idx), (col_idx, linha_idx), cor))
        tabela.setStyle(TableStyle(estilo))
        return tabela

    if modo_semana:
        matriz = _montar_matriz_semana(estruturas)
        n_colunas_dado = len(estruturas)

        cabecalho = [Paragraph("Horario", _ESTILO_OCUPACAO_CABECALHO)]
        cabecalho += [Paragraph(_DIA_SEMANA_LABEL_PT[dia], _ESTILO_OCUPACAO_CABECALHO) for dia, _ in estruturas]
        cabecalho += [Paragraph("Total", _ESTILO_OCUPACAO_CABECALHO), Paragraph("%", _ESTILO_OCUPACAO_CABECALHO)]
        linhas.append(cabecalho)

        for linha_matriz in matriz["linhas"]:
            linha: list = [Paragraph(_formatar_hora(linha_matriz["hora"]), _ESTILO_OCUPACAO_HORA)]
            for celula in linha_matriz["por_dia"]:
                if celula is None:
                    linha.append("")
                    cores_celulas.append((len(linhas), len(linha) - 1, _COR_OCUPACAO_VAZIA))
                else:
                    texto = f"{celula['ocupados']}/{celula['capacidade']}"
                    linha.append(Paragraph(texto, _ESTILO_OCUPACAO_CELULA))
                    cores_celulas.append((len(linhas), len(linha) - 1, _cor_status_ocupacao(celula["status"])))
            linha.append(
                Paragraph(f"{linha_matriz['total_ocupados']}/{linha_matriz['total_capacidade']}", _ESTILO_OCUPACAO_TOTAL)
            )
            linha.append(
                Paragraph(
                    _percentual(linha_matriz["total_ocupados"], linha_matriz["total_capacidade"]), _ESTILO_OCUPACAO_PERCENTUAL
                )
            )
            linhas.append(linha)

        linha_total: list = [Paragraph("Total", _ESTILO_OCUPACAO_TOTAL)]
        for total_dia in matriz["total_por_dia"]:
            linha_total.append(Paragraph(f"{total_dia['ocupados']}/{total_dia['capacidade']}", _ESTILO_OCUPACAO_TOTAL))
        linha_total.append(
            Paragraph(f"{matriz['total_geral']['ocupados']}/{matriz['total_geral']['capacidade']}", _ESTILO_OCUPACAO_TOTAL)
        )
        linha_total.append(
            Paragraph(
                _percentual(matriz["total_geral"]["ocupados"], matriz["total_geral"]["capacidade"]), _ESTILO_OCUPACAO_PERCENTUAL
            )
        )
        linhas.append(linha_total)
        elementos.append(_tabela_ocupacao(linhas, cores_celulas, n_colunas_dado))
    else:
        _, estrutura = estruturas[0]
        for titulo_periodo, periodo in (("Manha", "Manha"), ("Tarde", "Tarde")):
            matriz = _montar_matriz_dia_simples(estrutura["grupos"], periodo)
            if matriz["total_carros"] == 0:
                continue
            n_colunas_dado = matriz["total_carros"]

            linhas_periodo: list = []
            cores_celulas_periodo: list[tuple[int, int, object]] = []

            cabecalho = [Paragraph("Horario", _ESTILO_OCUPACAO_CABECALHO)]
            cabecalho += [Paragraph(f"{i + 1:02d}", _ESTILO_OCUPACAO_CABECALHO) for i in range(matriz["total_carros"])]
            cabecalho += [Paragraph("Total", _ESTILO_OCUPACAO_CABECALHO), Paragraph("%", _ESTILO_OCUPACAO_CABECALHO)]
            linhas_periodo.append(cabecalho)

            for linha_matriz in matriz["linhas"]:
                linha: list = [Paragraph(_formatar_hora(linha_matriz["hora"]), _ESTILO_OCUPACAO_HORA)]
                for celula in linha_matriz["por_carro"]:
                    if celula is None:
                        linha.append("")
                        cores_celulas_periodo.append((len(linhas_periodo), len(linha) - 1, _COR_OCUPACAO_VAZIA))
                    else:
                        linha.append(Paragraph(str(celula["ocupados"]), _ESTILO_OCUPACAO_CELULA))
                        cores_celulas_periodo.append(
                            (len(linhas_periodo), len(linha) - 1, _cor_status_ocupacao(celula["status"]))
                        )
                linha.append(Paragraph(str(linha_matriz["total_ocupados"]), _ESTILO_OCUPACAO_TOTAL))
                linha.append(
                    Paragraph(_percentual(linha_matriz["total_ocupados"], matriz["total_geral"]), _ESTILO_OCUPACAO_PERCENTUAL)
                )
                linhas_periodo.append(linha)

            linha_total = [Paragraph("Total", _ESTILO_OCUPACAO_TOTAL)]
            linha_total += [Paragraph(str(total_carro), _ESTILO_OCUPACAO_TOTAL) for total_carro in matriz["total_por_carro"]]
            linha_total.append(Paragraph(str(matriz["total_geral"]), _ESTILO_OCUPACAO_TOTAL))
            linha_total.append("")
            linhas_periodo.append(linha_total)

            elementos.append(Paragraph(titulo_periodo, _ESTILO_OCUPACAO_CABECALHO_SECAO))
            elementos.append(Spacer(1, 0.15 * cm))
            elementos.append(_tabela_ocupacao(linhas_periodo, cores_celulas_periodo, n_colunas_dado))
            elementos.append(Spacer(1, 0.4 * cm))

    elementos.append(Spacer(1, 0.2 * cm))
    legenda = Table(
        [
            [
                "",
                Paragraph("Com vaga", _ESTILO_CELULA),
                "",
                Paragraph("Lotado", _ESTILO_CELULA),
                "",
                Paragraph("Acima da capacidade", _ESTILO_CELULA),
                "",
                Paragraph("Sem viagem cadastrada", _ESTILO_CELULA),
            ]
        ],
        colWidths=[0.5 * cm, 2.2 * cm, 0.5 * cm, 2 * cm, 0.5 * cm, 3.4 * cm, 0.5 * cm, 3.6 * cm],
    )
    legenda.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), _COR_OCUPACAO_LIVRE),
                ("BACKGROUND", (2, 0), (2, 0), _COR_OCUPACAO_LOTADO),
                ("BACKGROUND", (4, 0), (4, 0), _COR_OCUPACAO_ACIMA),
                ("BACKGROUND", (6, 0), (6, 0), _COR_OCUPACAO_VAZIA),
                ("GRID", (0, 0), (0, 0), 0.5, colors.grey),
                ("GRID", (2, 0), (2, 0), 0.5, colors.grey),
                ("GRID", (4, 0), (4, 0), 0.5, colors.grey),
                ("GRID", (6, 0), (6, 0), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ]
        )
    )
    elementos.append(legenda)

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


def gerar_csv_grupos_revezamento(db: Session, dia_semana: DiaSemana) -> bytes:
    """Uma coluna por grupo de revezamento (Grupo 1, Grupo 2, ...) e, abaixo,
    a fila de condutores desse grupo na ordem cadastrada -- espelha o layout
    da barra de grupos na tela Base, so que em planilha.
    """
    revezamentos = (
        db.query(GrupoRevezamento)
        .options(joinedload(GrupoRevezamento.condutores).joinedload(GrupoRevezamentoCondutor.condutor))
        .filter(GrupoRevezamento.dia_semana == dia_semana)
        .order_by(GrupoRevezamento.id)
        .all()
    )
    colunas = [
        [condutor.condutor.apelido or condutor.condutor.nome for condutor in revezamento.condutores]
        for revezamento in revezamentos
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([f"Grupo {indice + 1}" for indice in range(len(colunas))])
    max_linhas = max((len(coluna) for coluna in colunas), default=0)
    for linha in range(max_linhas):
        writer.writerow([coluna[linha] if linha < len(coluna) else "" for coluna in colunas])
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
