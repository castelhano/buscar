# Plano — Reestruturação do modo Base (v2)

> Documento de planejamento para simulação/discussão. Nada aqui foi implementado.
> Versão consolidada após rodada de perguntas/respostas — reflete o desenho fechado,
> pendente de simulação manual antes de decidir implementar.

## 1. Por que mudar

O modo Base atual (`ordem_ida`/`ordem_retorno` + `pin_ida_agenda_id`/`pin_retorno_agenda_id`) infere o
agrupamento a partir de `(região, sentido, horário)` e usa a `ordem` só como critério de prioridade
*dentro* desse bucket implícito. O pin foi uma tentativa de furar a restrição de região caso a caso,
mas continua limitado:

- Região continua sendo o eixo primário — o pin é uma exceção pontual entre duas pessoas, não uma
  forma de desenhar o carro como um todo.
- Capacidade é rígida no preview (mesmo limite do veículo real), então não dá pra rascunhar um carro
  "cheio demais" pra depois decidir quem tira.
- O grupo não é uma entidade — é recalculado a cada geração a partir de `ordem` + região + pin, o que
  tornou o comportamento de arrastar difícil de prever (vários bugs de reindex nas últimas sessões).

## 2. Ideia nova

- Grupos (**carros conceituais**) são criados livremente na Base, **sem restrição de região**.
- Sem limite rígido de usuários por horário dentro de um carro — só um **alerta visual** (cor) se
  passar de 4 pessoas num mesmo horário. A geração **respeita a estrutura da Base como está definida**;
  o alerta é só um aviso, nunca um bloqueio ou uma correção automática — ajuste é sempre manual.
- Cada usuário tem uma **ordem dentro da viagem** (`membro_viagem_base.ordem`) — não existe mais
  prioridade global (`ordem_ida`/`ordem_retorno` deixam de existir, ver seção 3).
- A tela Base se apresenta **exatamente como a tela de Dia**: um card = um carro conceitual (sem
  prefixo/empresa/condutor, só um rótulo genérico tipo "Carro 1"), cada carro pode ter **N viagens**
  (06h00, 07h00, Retorno 13h00, etc.), cada viagem pode ter **N usuários**.
- A geração real carrega esses grupos primeiro, ajusta por exceções do dia, tenta resolver
  empresa/condutor/veículo pra cada carro (igual já funciona hoje), e só depois preenche quem sobrou
  (não classificado) nas vagas restantes — sem nunca desmontar o que foi definido na Base.

Isso **elimina a necessidade do pin** — hoje o pin existe só pra contornar a rigidez de região; se o
grupo é uma entidade livre, cross-região é só arrastar.

## 3. Modelo de dados novo

Três tabelas novas (nomes provisórios):

```
grupo_base
  id
  dia_semana         (DiaSemana)
  rotulo             (str | null — opcional, só se o usuário quiser nomear "Carro da manhã" etc.)
  ordem_exibicao     (int — posição do card na tela, só cosmético)

viagem_base
  id
  grupo_base_id      (FK -> grupo_base, cascade delete)
  sentido            (Sentido: Ida/Retorno)
  hora               (time)

membro_viagem_base
  id
  viagem_base_id     (FK -> viagem_base, cascade delete)
  agenda_id          (FK -> usuario_agenda_semanal)
  ordem              (int, 1..N — posição dentro da viagem)
```

Notas:
- **Sem `regiao_id` em lugar nenhum** dessas três tabelas — região não é mais um eixo de modelagem do
  grupo, só um dado derivado dos membros na hora de gerar.
- **Sem capacidade** em `viagem_base` — é conceitual; capacidade real só existe no `Veiculo` de verdade,
  consultado na geração.
- `membro_viagem_base` referencia `usuario_agenda_semanal` (a agenda semanal, não o usuário direto).
- Um mesmo `agenda_id` só pode estar em **uma** `viagem_base` por sentido (constraint de aplicação, não
  necessariamente de banco).

**`ordem_ida`/`ordem_retorno`/`pin_ida_agenda_id`/`pin_retorno_agenda_id` são removidos por completo**
de `UsuarioAgendaSemanal` (reverte o que foi adicionado nas sessões anteriores). Não sobra nenhum uso
pra eles: o agrupamento da Base agora é `membro_viagem_base.ordem`, e a ordenação de passageiros dentro
de um carro já gerado num dia real já existe em `ViagemDiaPassageiro.ordem`, independente da Base.

## 4. Dados existentes

Sem preocupação com migração — o banco será excluído e recriado do zero junto com essa mudança.

## 5. Geração real (`gerar_agendamento_dia`) — novo fluxo

1. Resolve `dia_semana` da data pedida.
2. Carrega `grupo_base` + `viagem_base` + `membro_viagem_base` daquele dia da semana.
3. Para cada membro, resolve elegibilidade real na data (igual já acontece hoje): `UsuarioExcecao`
   (suspenso, atendimento eventual, mudança de horário/local), recesso do local. Quem foi suspenso sai
   da viagem; quem teve exceção que muda horário/destino deixa de casar com aquele `viagem_base`
   específico e vira "não classificado" daquele sentido (passo 6) — **nunca** tenta realocar em outro
   slot do mesmo carro sozinho.
4. Para cada `viagem_base` sobrevivente, calcula as regiões reais dos membros do dia (uma por horário —
   nunca mistura região dentro do mesmo horário automaticamente) e busca empresa(s) que atendam **todas**
   as regiões tocadas pelo `grupo_base` ao longo do dia, com veículo ativo disponível (mesma lógica de
   feasibility que já existe hoje, só que a "aresta" entre pessoas vem de estarem no mesmo `grupo_base`,
   não de um pin):
   - **Viável**: aloca via rotação normal de veículo/condutor (`_proximo_veiculo_livre`), do jeito que já
     funciona hoje — inclusive o mesmo veículo podendo rodar horários de regiões diferentes ao longo do
     dia, se a empresa cobrir todas (isso já é comportamento natural do rodízio, nada novo).
   - **Inviável** (nenhuma empresa atende a mistura de regiões do `grupo_base`): **não divide** — o carro
     é criado exatamente como definido na Base (todo mundo junto), só sem `empresa_id`/`condutor_id`/
     `veiculo_id` (ficam `None`), com alerta pro usuário resolver manualmente (mesmo botão
     "Condutor/veículo" que já existe hoje no `CarroCard`).
5. Se os membros de uma `viagem_base` excederem a capacidade real do veículo alocado (o desenho na Base é
   livre e permite isso), **ninguém é removido** — só um alerta visual ("grupo X excede capacidade do
   veículo"), ajuste é manual.
6. **Preenchimento de "não classificados"** (agenda ativa na data, sem `membro_viagem_base` pra esse
   sentido, ou removida no passo 3): pra cada um, na ordem em que forem processados —
   a. Tenta encaixar num carro que veio da Base, no mesmo `sentido`+`hora`:
      - Se o carro **tem** empresa/condutor resolvidos: entra se há vaga real e a empresa atende a
        região do usuário.
      - Se o carro **não tem** empresa resolvida (caso inviável do passo 4): só entra se a região do
        usuário **já está representada** entre os membros existentes daquele carro naquele horário
        (ex.: carro tem 1 usuário CPA + 1 COXIPO sem empresa comum — outro usuário de CPA ou de COXIPO
        pode entrar; um usuário de uma terceira região, não). Região nova não entra automaticamente.
   b. Se não encaixar em nenhum carro de Base: abre carro novo, **só de uma região** por horário — mesmo
      algoritmo de bucket por região+horário+rotação de veículo que já existe hoje (nada novo aqui).
   c. Se não houver frota disponível pra abrir carro novo: fica sem alocação pra decisão manual, igual ao
      "sem vaga" de hoje.
7. Persiste como hoje (`ViagemDia` + `ViagemDiaPassageiro`). Proposta opcional: `ViagemDia` ganha uma
   coluna nullable `origem_grupo_base_id` só para rastreabilidade/debug — não essencial pro MVP.

`montar_preview_semana` deixa de existir como "algoritmo que decide o agrupamento" — vira uma leitura
direta de `grupo_base`/`viagem_base`/`membro_viagem_base` (com join pra enriquecer usuário/agenda),
devolvendo uma forma parecida com a de hoje pro frontend não precisar mudar muito na renderização.

## 6. Tela Base — novo fluxo de edição

- Continua no mesmo lugar (switch Dia/Base já existente), mas a interação muda de "arrasta e o sistema
  infere o grupo" pra **edição explícita de estrutura**:
  - Botão "+ Novo carro" cria um `grupo_base` vazio.
  - Dentro do card do carro, "+ Nova viagem" pede horário + sentido e cria um `viagem_base` (também pode
    ser criada on-the-fly ao soltar um usuário num horário que ainda não existe naquele carro).
  - Cada viagem renderiza como hoje (lista de passageiros, drag-and-drop pra reordenar/mover entre
    viagens/carros) — sem qualquer checagem de região no drop.
  - Contagem de pessoas por viagem exibe aviso visual (cor) ao passar de 4, sem bloquear.
  - Área separada de "não classificados" (agendas da semana sem `membro_viagem_base` naquele sentido)
    continua arrastável pra dentro de qualquer viagem de qualquer carro — com filtro por usuário (nome),
    região e destino.
  - Excluir carro/viagem é uma ação explícita (não é mais "esvaziar e a região desaparece sozinha").
- **Pin deixa de existir** nessa tela — vira redundante, já que qualquer combinação de região é livre por
  construção.

## 7. Endpoints novos (substituem os atuais de preview-semana)

- `POST /base/{dia_semana}/grupos` — cria carro conceitual.
- `DELETE /base/grupos/{grupo_id}` — remove carro (cascade nas viagens/membros).
- `POST /base/grupos/{grupo_id}/viagens` — cria viagem (sentido + hora) dentro do carro.
- `DELETE /base/viagens/{viagem_id}` — remove viagem.
- `PATCH /base/membros/{agenda_id}/mover` — move um membro pra uma `viagem_base` numa posição (`ordem`);
  pode criar a viagem de destino on-the-fly se ainda não existir naquele carro.
- `GET /base/{dia_semana}` — lê a estrutura completa pra renderizar a tela (grupos + viagens + membros +
  não classificados).

## 8. O que muda pouco / o que muda muito

**Muda pouco** (reaproveita quase tudo):
- Renderização de card/viagem/passageiro no frontend (`CarroCard`, `LegBlock`, `PassageiroCard`).
- Lógica de rotação de veículo/condutor por janela de horário (`_proximo_veiculo_livre`) — só passa a
  ser chamada com a lista de empresas resolvida por `grupo_base` em vez de por cluster de pin.
- Algoritmo de abertura de carro novo por região+horário pra "não classificados" — é o de hoje, sem
  mudança.

**Muda muito**:
- Toda a semântica de agrupamento no preview deixa de ser inferida (`ordem` + região + pin) e vira
  **entidade persistida e editada explicitamente** (`grupo_base`/`viagem_base`/`membro_viagem_base`).
- O fluxo de drag-and-drop na tela Base muda de "solta em cima de alguém e o sistema decide" pra "solta
  dentro de uma viagem explícita".
- `ordem_ida`/`ordem_retorno`, `pin_ida_agenda_id`/`pin_retorno_agenda_id` e toda a resolução de clusters
  via union-find (`_resolver_clusters_pin`) são removidos — a feasibility de empresa passa a ser
  calculada por `grupo_base` diretamente.
- Geração deixa de tentar "otimizar" globalmente — passa a ser "replica a Base + resolve empresa por
  carro + encaixa quem sobrou", nunca reorganiza o que já foi definido manualmente.

## 9. Decisões fechadas

1. `grupo_base` inviável (nenhuma empresa atende a mistura de regiões): gera do jeito que está definido
   na Base, sem dividir, só sem empresa/condutor/veículo — alerta pro usuário resolver manualmente.
2. Excedente de capacidade dentro de uma viagem da Base: só alerta visual, gerador não remove ninguém.
3. Prioridade de "não classificados" no preenchimento: irrelevante, qualquer carro que encaixe serve.
4. Um `grupo_base` = um carro real ao longo do dia — geração nunca divide, só replica.
5. Sem bootstrap — começa do zero.
6. `PATCH /base/membros/{agenda_id}/mover` pode criar viagem nova on-the-fly.
7. Carro novo aberto automaticamente pra não classificado é sempre de uma única região por horário —
   igual ao algoritmo de hoje; o mesmo veículo pode rodar horários de regiões diferentes ao longo do dia
   se a empresa cobrir todas (comportamento natural do rodízio, nada novo).
8. Encaixe de "não classificado" num carro da Base sem empresa resolvida (inviável): só entra se a
   região do usuário já está representada entre os membros existentes daquele carro naquele horário;
   região nova não entra automaticamente (abre carro novo se disponível, senão fica manual).
9. `ordem_ida`/`ordem_retorno`/pin removidos de `UsuarioAgendaSemanal` — sem uso remanescente.

## 10. Ordem de implementação sugerida (quando/se for aprovado)

1. Reverter `ordem_ida`/`ordem_retorno`/pin de `models.py` + migration de remoção.
2. Migration + models das 3 tabelas novas (`grupo_base`, `viagem_base`, `membro_viagem_base`).
3. Endpoints CRUD de grupo/viagem/membro (sem geração ainda) + schemas.
4. Frontend: nova tela de edição (criar carro/viagem, mover membro) reaproveitando componentes visuais
   existentes.
5. `gerar_agendamento_dia`: novo fluxo (seção 5), com os alertas de inviabilidade/overflow visíveis na
   resposta.
6. Aposentar `montar_preview_semana`, `_resolver_clusters_pin` (depois de confirmar que nada mais
   depende deles).
