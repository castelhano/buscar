"""Popula usuario / agenda semanal a partir dos CSVs em app/seed_data/.

Uso:
    python -m app.seed
"""

import csv
import datetime as dt
import os
import re

from app.database import Base, SessionLocal, engine
from app.models import (
    Condutor,
    DiaSemana,
    Empresa,
    Local,
    PeriodoCondutor,
    Regiao,
    StatusCondutor,
    TipoAtendimento,
    TipoLocal,
    Usuario,
    UsuarioAgendaSemanal,
    Veiculo,
)

EMPRESAS = ["AMTU", "VPAR", "RAPIDO", "CARIBUS", "INTEGRACAO"]

CSV_USUARIOS_PATH = os.path.join(os.path.dirname(__file__), "seed_data", "usuarios.csv")
CSV_AGENDAMENTO_PATH = os.path.join(os.path.dirname(__file__), "seed_data", "usuario_agendamento.csv")
CSV_LOCAIS_PATH = os.path.join(os.path.dirname(__file__), "seed_data", "locais.csv")
CSV_VEICULOS_PATH = os.path.join(os.path.dirname(__file__), "seed_data", "veiculos.csv")
CSV_CONDUTORES_PATH = os.path.join(os.path.dirname(__file__), "seed_data", "condutores.csv")

_PERIODO_POR_DIGITO = {
    "1": PeriodoCondutor.MANHA,
    "2": PeriodoCondutor.TARDE,
}

_CONECTIVOS = {"de", "da", "do", "das", "dos", "e"}
_ROMANOS = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}

_DIA_POR_DIGITO = {
    "1": DiaSemana.DOM,
    "2": DiaSemana.SEG,
    "3": DiaSemana.TER,
    "4": DiaSemana.QUA,
    "5": DiaSemana.QUI,
    "6": DiaSemana.SEX,
    "7": DiaSemana.SAB,
}

_REGIAO_PLACEHOLDER = "A definir"

_TIPO_LOCAL_ALIASES = {
    "ecoterapia": TipoLocal.EQUOTERAPIA,
}


def _parse_tipo_local(valor: str) -> TipoLocal:
    valor = valor.strip()
    alias = _TIPO_LOCAL_ALIASES.get(valor.lower())
    return alias if alias is not None else TipoLocal(valor)

_BAIRRO_BLACKLIST = (
    "deixar", "vizinh", "creche", "endere", "retorno", "numero", "mesma rua",
    "apto", "bloco", "condom", "horas", "s/n", "distrito n",
)
_BAIRRO_CODE_RE = re.compile(
    r"^\s*(qd|qdra|q|cs|c|lt|n|apt|apto|bl|bloco|res|casa|lote|km|rod)\.?\s*\d",
    re.IGNORECASE,
)


def _nome_proprio(nome_bruto: str) -> str:
    palavras = nome_bruto.strip().lower().split()
    resultado = []
    for i, palavra in enumerate(palavras):
        if i > 0 and palavra in _CONECTIVOS:
            resultado.append(palavra)
        elif palavra in _ROMANOS:
            resultado.append(palavra.upper())
        else:
            resultado.append(palavra[:1].upper() + palavra[1:])
    return " ".join(resultado)


def _bairro_valido(segmento: str) -> bool:
    limpo = segmento.strip()
    if len(limpo) < 3:
        return False
    if re.match(r"^\d", limpo):
        return False
    if _BAIRRO_CODE_RE.match(limpo):
        return False
    baixo = limpo.lower()
    return not any(kw in baixo for kw in _BAIRRO_BLACKLIST)


def _extrair_bairro(detalhe: str | None) -> str | None:
    """Melhor esforco para achar o bairro dentro do endereco cru do CSV
    original. Quando nao da pra confiar, retorna None (fica em branco)."""

    if not detalhe:
        return None

    tokens = [t for t in re.split(r"[,.\-:]", detalhe) if t.strip()]
    for token in reversed(tokens):
        if _bairro_valido(token):
            return _nome_proprio(token.strip())
    return None


def _gerar_abbrs(nomes: list[str]) -> list[str]:
    """Gera um abbr por nome: primeiro nome, desempatando com partes do
    sobrenome quando ha colisao entre pessoas diferentes."""

    palavras_por_nome = [nome.split() for nome in nomes]
    grupos: dict[str, list[int]] = {}
    for i, palavras in enumerate(palavras_por_nome):
        grupos.setdefault(palavras[0], []).append(i)

    abbrs = [""] * len(nomes)
    for primeiro_nome, indices in grupos.items():
        if len(indices) == 1:
            abbrs[indices[0]] = primeiro_nome
            continue

        # tenta ir acrescentando palavras do sobrenome ate desempatar
        pendentes = list(indices)
        n_palavras = 1
        while True:
            candidatos: dict[str, list[int]] = {}
            for i in pendentes:
                palavras = palavras_por_nome[i]
                candidato = " ".join(palavras[:n_palavras]) if len(palavras) >= n_palavras else " ".join(palavras)
                candidatos.setdefault(candidato, []).append(i)

            novos_pendentes = []
            for candidato, idxs in candidatos.items():
                if len(idxs) == 1:
                    abbrs[idxs[0]] = candidato
                else:
                    novos_pendentes.extend(idxs)

            if not novos_pendentes:
                break

            n_palavras += 1
            max_palavras = max(len(palavras_por_nome[i]) for i in novos_pendentes)
            if n_palavras > max_palavras:
                # nomes identicos (mesma pessoa repetida no csv): desempata com sufixo numerico
                for ordem, i in enumerate(novos_pendentes, start=1):
                    base = " ".join(palavras_por_nome[i])
                    abbrs[i] = base if ordem == 1 else f"{base} ({ordem})"
                break

            pendentes = novos_pendentes

    return abbrs


def _ler_csv_usuarios() -> list[tuple[str, str, str, str]]:
    """Retorna (nome_chave, nome_formatado, regiao, endereco_bruto) por linha
    do CSV original. nome_chave e o valor cru da coluna NOME (mesma grafia
    usada em usuario_agendamento.csv), usado para casar os dois CSVs pelo
    nome.

    O endereco bruto nao e persistido em Usuario.detalhe (fica em branco);
    serve apenas de insumo pra tentar extrair o bairro no seed da agenda.
    """
    linhas = []
    with open(CSV_USUARIOS_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nome_chave = row["NOME"].strip()
            nome = _nome_proprio(nome_chave)
            regiao = row["REGIAO"].strip()
            endereco = (row.get("DETALHE") or "").strip()
            linhas.append((nome_chave, nome, regiao, endereco))
    return linhas


def seed_usuarios() -> dict[str, int]:
    """Cria um usuario por nome unico do CSV e devolve {nome_chave: id}.

    Uma mesma pessoa pode aparecer mais de uma vez no CSV de usuarios (ex:
    enderecos de origem diferentes pra dias diferentes da semana); isso vira
    um unico Usuario, casado com varias linhas de usuario_agendamento.csv
    pelo nome (ver seed_agenda_semanal)."""

    linhas = _ler_csv_usuarios()
    nomes_chave_unicos = list(dict.fromkeys(chave for chave, _, _, _ in linhas))
    nome_formatado_por_chave = {chave: nome for chave, nome, _, _ in linhas}
    nomes_formatados = [nome_formatado_por_chave[chave] for chave in nomes_chave_unicos]
    abbrs = _gerar_abbrs(nomes_formatados)

    db = SessionLocal()
    try:
        existentes = db.query(Usuario).count()
        if existentes > 0:
            print("Tabela usuario ja possui dados, seed nao executado.")
            return {u.nome: u.id for u in db.query(Usuario)}

        usuarios = [
            Usuario(nome=nome, abbr=abbr, detalhe=None) for nome, abbr in zip(nomes_formatados, abbrs)
        ]
        db.add_all(usuarios)
        db.commit()
        for u in usuarios:
            db.refresh(u)
        print(f"{len(usuarios)} usuarios inseridos.")
        return dict(zip(nomes_chave_unicos, (u.id for u in usuarios)))
    finally:
        db.close()


def seed_empresas() -> int:
    db = SessionLocal()
    try:
        if db.query(Empresa).count() > 0:
            print("Tabela empresa ja possui dados, seed nao executado.")
            return 0

        db.add_all(Empresa(nome=nome) for nome in EMPRESAS)
        db.commit()
        print(f"{len(EMPRESAS)} empresas inseridas.")
        return len(EMPRESAS)
    finally:
        db.close()


def seed_veiculos() -> int:
    db = SessionLocal()
    try:
        if db.query(Veiculo).count() > 0:
            print("Tabela veiculo ja possui dados, seed nao executado.")
            return 0

        empresas_por_nome = {e.nome: e.id for e in db.query(Empresa)}

        total = 0
        with open(CSV_VEICULOS_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                prefixo = row["prefixo"].strip()
                empresa_nome = row["empresa"].strip()
                placa = row["placa"].strip()
                if not prefixo:
                    continue

                empresa_id = empresas_por_nome.get(empresa_nome)
                if empresa_id is None:
                    print(f"AVISO: empresa {empresa_nome!r} nao encontrada, veiculo {placa!r} ignorado.")
                    continue

                db.add(Veiculo(empresa_id=empresa_id, prefixo=prefixo, placa=placa))
                total += 1

        db.commit()
        print(f"{total} veiculos inseridos.")
        return total
    finally:
        db.close()


def seed_condutores() -> int:
    db = SessionLocal()
    try:
        if db.query(Condutor).count() > 0:
            print("Tabela condutor ja possui dados, seed nao executado.")
            return 0

        empresas_por_nome = {e.nome: e.id for e in db.query(Empresa)}
        # global (nao filtrado por empresa): condutores de uma empresa podem
        # ter veiculo preferencial de outra (ex: AMTU nao tem frota propria)
        veiculos_por_prefixo = {v.prefixo: v.id for v in db.query(Veiculo)}

        total = 0
        with open(CSV_CONDUTORES_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                matricula = row["matricula"].strip()
                if not matricula:
                    continue

                empresa_nome = row["empresa"].strip()
                empresa_id = empresas_por_nome.get(empresa_nome)
                if empresa_id is None:
                    print(f"AVISO: empresa {empresa_nome!r} nao encontrada, condutor {matricula!r} ignorado.")
                    continue

                nome = _nome_proprio(row["nome"])
                apelido_bruto = (row.get("apelido") or "").strip()
                apelido = _nome_proprio(apelido_bruto) if apelido_bruto else None
                status = StatusCondutor(row["status"].strip().capitalize())
                periodo = _PERIODO_POR_DIGITO.get(row["periodo"].strip(), PeriodoCondutor.MANHA)

                prefixo_pref = (row.get("veiculo_preferencial") or "").strip()
                veiculo_preferencial_id = veiculos_por_prefixo.get(prefixo_pref) if prefixo_pref else None
                if prefixo_pref and veiculo_preferencial_id is None:
                    print(
                        f"AVISO: veiculo prefixo {prefixo_pref!r} nao encontrado, "
                        f"condutor {matricula!r} ficou sem veiculo preferencial."
                    )

                db.add(
                    Condutor(
                        empresa_id=empresa_id,
                        matricula=matricula,
                        nome=nome,
                        apelido=apelido,
                        status=status,
                        periodo=periodo,
                        veiculo_preferencial_id=veiculo_preferencial_id,
                    )
                )
                total += 1

        db.commit()
        print(f"{total} condutores inseridos.")
        return total
    finally:
        db.close()


def _get_or_create_regiao(db, nome: str) -> Regiao:
    regiao = db.query(Regiao).filter_by(nome=nome).first()
    if regiao is None:
        regiao = Regiao(nome=nome)
        db.add(regiao)
        db.flush()
    return regiao


def seed_locais() -> int:
    db = SessionLocal()
    try:
        if db.query(Local).count() > 0:
            print("Tabela local ja possui dados, seed nao executado.")
            return 0

        regiao_placeholder = _get_or_create_regiao(db, _REGIAO_PLACEHOLDER)

        total = 0
        with open(CSV_LOCAIS_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                nome = row["nome"].strip()
                if not nome:
                    continue
                tipo = _parse_tipo_local(row["tipo"])
                observacao = (row.get("detalhe") or "").strip() or None
                db.add(Local(nome=nome, tipo=tipo, regiao_id=regiao_placeholder.id, observacao=observacao))
                total += 1

        db.commit()
        print(f"{total} locais inseridos.")
        return total
    finally:
        db.close()


def _get_or_create_local(db, nome: str, regiao_id: int) -> Local:
    """Busca o Local ja criado por seed_locais(); cria um fallback generico
    (tipo Outros) se o destino nao constar em locais.csv."""

    local = db.query(Local).filter_by(nome=nome).first()
    if local is None:
        print(f"AVISO: destino {nome!r} nao encontrado em locais.csv, criando como Outros.")
        local = Local(nome=nome, tipo=TipoLocal.OUTROS, regiao_id=regiao_id)
        db.add(local)
        db.flush()
    return local


def _agrupar_por_nome(pares: list[tuple[str, object]]) -> dict[str, list]:
    """Agrupa preservando a ordem de aparicao, pra casar a k-esima ocorrencia
    de um nome num CSV com a k-esima ocorrencia do mesmo nome no outro."""

    grupos: dict[str, list] = {}
    for nome, valor in pares:
        grupos.setdefault(nome, []).append(valor)
    return grupos


def _valor_por_indice(valores: list[str], i: int, nome: str, rotulo: str) -> str | None:
    """Casa a i-esima linha de agendamento com a i-esima linha de
    usuarios.csv daquele nome; reaproveita o ultimo valor conhecido se
    houver mais linhas de agendamento do que de usuarios.csv pra esse nome."""

    if i < len(valores):
        return valores[i]
    if valores:
        print(
            f"AVISO: {nome!r} tem mais linhas de agendamento do que de {rotulo}, "
            f"reaproveitando o ultimo {rotulo} conhecido."
        )
        return valores[-1]
    return None


def seed_agenda_semanal(usuario_ids: dict[str, int]) -> int:
    """Casa usuarios.csv com usuario_agendamento.csv pelo nome (coluna NOME /
    nome), nao pela posicao da linha. Uma pessoa pode ter mais de uma linha
    em usuario_agendamento.csv (ex: atendimento seg-qua num destino e sex
    noutro); nesse caso a k-esima linha de agendamento com aquele nome usa o
    endereco/regiao da k-esima linha de usuarios.csv com o mesmo nome (e
    repete o ultimo endereco/regiao conhecido se houver mais linhas de
    agendamento do que de endereco pra aquele nome)."""

    linhas_usuarios = _ler_csv_usuarios()
    enderecos_por_nome = _agrupar_por_nome([(chave, endereco) for chave, _, _, endereco in linhas_usuarios])
    regioes_por_nome = _agrupar_por_nome([(chave, regiao) for chave, _, regiao, _ in linhas_usuarios])

    with open(CSV_AGENDAMENTO_PATH, encoding="utf-8-sig") as f:
        linhas_agendamento = [(row["nome"].strip(), row) for row in csv.DictReader(f)]
    agendamentos_por_nome = _agrupar_por_nome(linhas_agendamento)

    for nome in agendamentos_por_nome:
        if nome not in usuario_ids:
            print(f"AVISO: {nome!r} aparece em usuario_agendamento.csv mas nao em usuarios.csv, ignorado.")
    for nome in enderecos_por_nome:
        if nome not in agendamentos_por_nome:
            print(f"AVISO: {nome!r} aparece em usuarios.csv mas nao tem nenhuma linha em usuario_agendamento.csv.")

    db = SessionLocal()
    try:
        if db.query(UsuarioAgendaSemanal).count() > 0:
            print("Tabela usuario_agenda_semanal ja possui dados, seed nao executado.")
            return 0

        regiao_placeholder = _get_or_create_regiao(db, _REGIAO_PLACEHOLDER)

        total = 0
        for nome, linhas in agendamentos_por_nome.items():
            usuario_id = usuario_ids.get(nome)
            if usuario_id is None:
                continue

            enderecos = enderecos_por_nome.get(nome, [])
            regioes = regioes_por_nome.get(nome, [])
            for i, linha in enumerate(linhas):
                endereco = _valor_por_indice(enderecos, i, nome, "endereco")
                regiao_nome = _valor_por_indice(regioes, i, nome, "regiao")
                regiao_origem_id = _get_or_create_regiao(db, regiao_nome).id if regiao_nome else None

                destino_nome = linha["destino"].strip()
                local = _get_or_create_local(db, destino_nome, regiao_placeholder.id)

                tipo = TipoAtendimento.FIXO if linha["fixo"].strip().upper() == "SIM" else TipoAtendimento.EVENTUAL
                origem = _extrair_bairro(endereco)
                saida = dt.datetime.strptime(linha["ida"].strip(), "%H:%M").time()
                retorno = dt.datetime.strptime(linha["volta"].strip(), "%H:%M").time()

                for digito in linha["escopo"].strip():
                    dia_semana = _DIA_POR_DIGITO.get(digito)
                    if dia_semana is None:
                        continue
                    db.add(
                        UsuarioAgendaSemanal(
                            usuario_id=usuario_id,
                            dia_semana=dia_semana,
                            tipo=tipo,
                            saida=saida,
                            retorno=retorno,
                            origem=origem,
                            regiao_origem_id=regiao_origem_id,
                            destino_id=local.id,
                        )
                    )
                    total += 1

        db.commit()
        print(f"{total} linhas de usuario_agenda_semanal inseridas.")
        return total
    finally:
        db.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed_empresas()
    seed_veiculos()
    seed_condutores()
    seed_locais()
    ids = seed_usuarios()
    seed_agenda_semanal(ids)
