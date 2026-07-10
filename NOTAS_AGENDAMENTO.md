# Notas — remodelagem do agendamento base -> geracao dinamica

> Arquivo temporario de handoff entre maquinas/sessoes. Pode apagar depois de
> retomar o contexto em outra sessao.

## Motivacao

`AgendamentoBase` + `UsuarioAgendamentoBase` (template fixo de carro por
dia_tipo + regiao + horario, com vinculo manual de usuario a esse carro)
nao representavam o fluxo real desejado. Foram substituidos por geracao
dinamica a partir de `UsuarioAgendaSemanal`.

## Fluxo desejado (conforme descrito)

1. Usuario seleciona um dia e clica "Gerar agendamento do dia".
2. Sistema busca todos `UsuarioAgendaSemanal` com `dia_semana` = dia
   escolhido, `tipo = FIXO`, `ativo = true`.
3. Trata excecoes (`UsuarioExcecao`) para esses usuarios nessa data (consulta
   unica, filtrada por `usuario_id IN (...)`).
4. Agrupa usuarios selecionados por `regiao_origem_id`.
5. Abre carro por regiao, preenche ate o limite de capacidade do carro; se
   sobrar gente e tiver veiculo liberado na empresa que atende a regiao, abre
   outro carro; continua ate esgotar a demanda ou a frota.

## Decisoes de design tomadas na conversa

- **`Veiculo.capacidade: int`** (novo campo, default 4) — fonte real de
  capacidade por carro, substitui o numero fixo que vinha do
  `AgendamentoBase.capacidade`.
- **`UsuarioAgendaSemanal.ordem: int`** (novo campo, default 0) — curadoria
  manual de proximidade ("quem mora perto fica junto"), feita uma vez no
  cadastro do usuario, reaproveitada em toda geracao futura (resolve a
  reclamacao de nao querer reagrupar manualmente todo dia).
- **`ViagemDia.horario_saida`** passa a ser calculado automaticamente como
  `min(hora dos passageiros do carro) - 60min` (constante
  `TEMPO_SAIDA_GARAGEM_MINUTOS` em `geracao.py`, representando o tempo de
  saida da garagem).
- **Um mesmo veiculo/condutor pode fazer mais de uma viagem no dia**: cada
  bucket (regiao, sentido, hora exata) sempre vira uma `ViagemDia` distinta
  (nunca mistura horas diferentes numa mesma viagem), mas o mesmo
  veiculo/condutor pode ser reaproveitado numa `ViagemDia` posterior desde que
  as janelas de horario nao se sobreponham. Isso ja existia parcialmente em
  `viagens.py` (`_detectar_conflito_recurso`/`_fim_viagem`, usado na edicao
  manual para permitir "dois turnos" do mesmo carro) — foi extraido para
  `app/services/recursos.py` (`fim_viagem`, `janelas_sobrepoem`) e reaproveitado
  tambem na geracao automatica (`_proximo_veiculo_livre`,
  `_proximo_condutor_livre` em `geracao.py`).
- Bucketing por hora **exata** (sem tolerancia de minutos) — decisao
  conservadora para nao juntar por engano horarios diferentes. Se depois se
  mostrar problematico (grupos com horarios levemente escalonados abrindo
  carros demais), pode-se introduzir uma janela de tolerancia.

## O que foi implementado

**Backend**
- Removidos: `AgendamentoBase`, `UsuarioAgendamentoBase`, `DiaTipo` (model,
  schemas, router `agendamento_base.py`), `ViagemDia.agendamento_base_id`.
- Novo: `Veiculo.capacidade`, `UsuarioAgendaSemanal.ordem`.
- Novo `app/services/recursos.py` (`fim_viagem`, `janelas_sobrepoem`)
  compartilhado entre `viagens.py` e `geracao.py`.
- `app/services/geracao.py` reescrito do zero com o algoritmo novo.
- `app/services/dia.py`: removido `dia_tipo_from_date` (nao usado mais).
- Migration Alembic `613ace416f4b` aplicada localmente (banco de teste
  recriado do zero + reseed, por causa de um problema de ordering do SQLite
  batch mode ao dropar tabela referenciada por FK — ver secao abaixo).

**Frontend**
- Removida pagina/rota "Agendamento base" (`AgendamentoBasePage.tsx`, nav em
  `App.tsx`).
- `VeiculosSection.tsx`: campo Capacidade no form + tabela.
- `AgendaSemanalEditor.tsx`: campo Ordem no form de edicao (input numerico
  simples, com tooltip explicando o proposito).
- `api/types.ts` atualizado (removidos tipos de base, adicionados
  `capacidade`/`ordem`).

**Validado**: import do backend, typecheck do frontend, dois smoke tests
manuais do algoritmo (limite de frota cortando corretamente o excedente;
reuso de carro/condutor em duas viagens do mesmo dia sem sobreposicao), teste
end-to-end via servidor real (`/viagens/gerar`).

## Pendente / proximos passos

1. **`horario_saida` NAO esta editavel ainda.** Foi pedido explicitamente que
   a tela de escala do dia permita ajustar esse valor apos a geracao
   automatica, mas isso ficou faltando: nao existe endpoint PATCH para
   `ViagemDia.horario_saida` (so e definido na criacao, seja manual via
   `POST /viagens/abrir`, seja automatico na geracao). Falta:
   - Endpoint (`PATCH /viagens/{id}` ou estender `ViagemDiaAtribuir`) para
     editar `horario_saida`.
   - Campo editavel na tela de escala do dia (`AgendamentoDiaPage`/`CarroCard`).
2. **Dados de seed nao tem `regiao_origem_id` preenchido** em nenhuma linha
   de `usuario_agenda_semanal` (gap preexistente, nao é regressao). Por isso
   `POST /viagens/gerar` retorna lista vazia com os dados atuais — para
   testar de verdade, precisa popular `regiao_origem_id` nos usuarios de
   teste e vincular `empresa_regiao`.
3. **Migrations do banco de teste devem ser limpas/squashadas antes do prod**
   (combinado em conversa anterior) — os `server_default` adicionados nas
   migrations recentes (`98ba361c9edc`, `613ace416f4b`) sao descartaveis.
4. **UI de `ordem`** hoje e so um input numerico manual. A ideia de
   drag-and-drop para reordenar visualmente (mencionada na conversa) fica
   para uma tela futura.
5. Revisitar se bucketing por hora exata (sem tolerancia) e suficiente na
   pratica, ou se precisa de uma janela de tolerancia em minutos.

## Arquivos-chave para retomar contexto

- `backend/app/models.py` — schema atual (models `ViagemDia`,
  `UsuarioAgendaSemanal`, `Veiculo`).
- `backend/app/services/geracao.py` — algoritmo de geracao.
- `backend/app/services/recursos.py` — helpers de sobreposicao de horario.
- `backend/app/routers/viagens.py` — endpoints de viagem/escala do dia
  (onde entraria o PATCH de `horario_saida`).
- `frontend/src/pages/AgendamentoDiaPage.tsx` +
  `frontend/src/components/board/CarroCard.tsx` — tela de escala do dia
  (onde entraria a edicao de `horario_saida` na UI).
