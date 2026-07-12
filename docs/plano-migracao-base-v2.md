# Plano — Reestruturação do modo Base (v2)

> Documento de planejamento para simulação/discussão. Nada aqui foi implementado.

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

## 2. Ideia nova (conforme descrito)

- Grupos (**carros conceituais**) são criados livremente, **sem restrição de região**.
- Sem limite rígido de usuários por horário dentro de um carro — só um **alerta visual** (cor) se
  passar de 4 pessoas num mesmo horário. Quem decide o corte real é a geração, na hora de casar com
  frota de verdade.
- Cada usuário tem uma **ordem dentro do grupo/horário** (substitui `ordem_ida`/`ordem_retorno` como
  prioridade global).
- A tela Base passa a se parecer **exatamente com a tela de Dia**: um card = um carro conceitual (sem
  prefixo/empresa/condutor, só um rótulo genérico tipo "Carro 1"), cada carro pode ter **N viagens**
  (06h00, 07h00, Retorno 13h00, etc.), cada viagem pode ter **N usuários**.
- A geração real passa a **carregar esses grupos primeiro**, ajustar por exceções do dia, e só depois
  preencher quem sobrou (não classificado, ou que caiu fora do grupo por exceção) nas vagas restantes
  que atendam os requisitos — e abrir carro novo se ainda sobrar gente.

Isso **elimina a necessidade do pin** — hoje o pin existe só pra contornar a rigidez de região; se o
grupo é uma entidade livre, cross-região é só arrastar.

## 3. Modelo de dados novo

Três tabelas novas (nomes provisórios):

```
grupo_base
  id
  dia_semana         (DiaSemana)
  rotulo             (str | null — opcional, só se o usuário quiser nomear "Carro da manhã" etc.)
  ordem_exibicao      (int — posição do card na tela, só cosmético)

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
- `membro_viagem_base` referencia `usuario_agenda_semanal` (a agenda semanal, não o usuário direto) —
  mesma referência que `pin_*_agenda_id` usa hoje, mantém consistência com exceções por dia da semana.
- Um mesmo `agenda_id` só pode estar em **uma** `viagem_base` por sentido (constraint de aplicação, não
  necessariamente de banco) — evita duplicidade.

`ordem_ida`/`ordem_retorno`/`pin_ida_agenda_id`/`pin_retorno_agenda_id` em `UsuarioAgendaSemanal` deixam
de ser a fonte da verdade do agrupamento. Proposta: manter os campos (não remover ainda) só para servir
de critério de desempate de quem sobrar sem grupo (fila dos "não classificados"), até decidirmos se vale
a pena simplificar para outra coisa (ex.: ordenar por nome/id).

## 4. Migração / bootstrap dos dados existentes

Não dá pra migrar `ordem_ida/ordem_retorno/pin` 1:1 pros novos grupos — a semântica é outra (bucket
implícito vira entidade explícita). Proposta de bootstrap **opcional**, rodado uma vez por dia da semana:

1. Rodar a lógica atual de `montar_preview_semana` (região + sentido + hora + pin resolvido) como está
   hoje.
2. Cada bucket resultante vira um `grupo_base` com uma `viagem_base` por `(sentido, hora)` existente
   nele, e os membros entram em `membro_viagem_base` na ordem atual.
3. O usuário parte desse rascunho pré-preenchido em vez de tela em branco, e edita livremente (funde
   carros de regiões diferentes, cria/apaga viagens, reordena).

Isso é só ponto de partida — depois de rodado, os dados antigos (`ordem_ida` etc.) podem ficar
congelados/ignorados pro que já foi migrado.

## 5. Geração real (`gerar_agendamento_dia`) — novo fluxo

1. Resolve `dia_semana` da data pedida.
2. Carrega `grupo_base` + `viagem_base` + `membro_viagem_base` daquele dia da semana.
3. Para cada membro, resolve elegibilidade real na data (igual já acontece hoje): `UsuarioExcecao`
   (suspenso, atendimento eventual, mudança de horário/local), recesso do local. Quem foi suspenso sai
   da viagem; quem teve exceção que muda horário/destino deixa de casar com aquele `viagem_base`
   específico e volta pro fluxo de "não classificado" da fase 6 (não tenta adivinhar outro slot do
   mesmo carro).
4. Para cada `viagem_base` sobrevivente (com >=1 membro), calcula as regiões reais dos membros do dia e
   busca empresa(s) que atendam **todas** elas com veículo ativo disponível — generaliza a lógica que já
   existe (`_resolver_clusters_pin` + `_empresas_com_veiculo_ativo`), só que agora a "aresta" entre
   pessoas não vem de um pin, vem de estarem na mesma `viagem_base`.
   - **Viável**: aloca via rotação normal de veículo/condutor (`_proximo_veiculo_livre`), tentando
     **reutilizar o mesmo veículo/condutor entre as `viagem_base` do mesmo `grupo_base`** ao longo do
     dia (é isso que faz o card parecer "um carro com N viagens" também no dia real).
   - **Inviável** (nenhuma empresa atende a mistura de regiões deste horário): quebra esse
     `viagem_base` em subgrupos por região (fallback ao algoritmo de bucket de hoje) e sinaliza um aviso
     pro usuário ("grupo X não pôde ser realizado como definido nesta data, dividido automaticamente").
5. Se os membros de uma `viagem_base` viável excederem a capacidade real do veículo alocado (o desenho
   livre permite isso), os excedentes — pelos últimos na `ordem` da viagem — saem pra fase 6 com um
   aviso ("grupo X excede capacidade do veículo, N usuário(s) realocado(s)").
6. **Preenchimento residual**: qualquer agenda ativa na data (sentido correspondente) que não ficou
   alocada por um `grupo_base` (nunca esteve em nenhum grupo, ou caiu fora por exceção/overflow/
   inviabilidade) entra no algoritmo de hoje — bucket por `(região, sentido, hora)`, tentando vaga nos
   carros recém-criados a partir dos grupos e, se não couber, abrindo carro novo com frota que sobrar.
7. Persiste como hoje (`ViagemDia` + `ViagemDiaPassageiro`). Proposta opcional: `ViagemDia` ganha uma
   coluna nullable `origem_grupo_base_id` só para rastreabilidade/debug (ver de onde veio cada carro
   gerado) — não essencial pro MVP, dá pra adicionar depois.

`montar_preview_semana` deixa de existir como "algoritmo que decide o agrupamento" — vira uma leitura
direta de `grupo_base`/`viagem_base`/`membro_viagem_base` (com join pra enriquecer usuário/agenda),
devolvendo uma forma parecida com a de hoje pro frontend não precisar mudar muito na renderização.

## 6. Tela Base — novo fluxo de edição

- Continua no mesmo lugar (switch Dia/Base já existente), mas a interação muda de "arrasta e o sistema
  infere o grupo" pra **edição explícita de estrutura**:
  - Botão "+ Novo carro" cria um `grupo_base` vazio.
  - Dentro do card do carro, "+ Nova viagem" pede horário + sentido e cria um `viagem_base`.
  - Cada viagem renderiza como hoje (lista de passageiros, drag-and-drop pra reordenar/mover entre
    viagens/carros) — sem qualquer checagem de região no drop.
  - Contagem de pessoas por viagem exibe aviso visual (cor) ao passar de 4, sem bloquear.
  - Área separada de "não classificados" (agendas da semana sem `membro_viagem_base` naquele sentido)
    continua arrastável pra dentro de qualquer viagem de qualquer carro.
  - Excluir carro/viagem é uma ação explícita (não é mais "esvaziar e a região desaparece sozinha").
- **Pin deixa de existir** nessa tela — vira redundante, já que qualquer combinação de região é livre por
  construção.

## 7. Endpoints novos (substituem os atuais de preview-semana)

- `POST /base/{dia_semana}/grupos` — cria carro conceitual.
- `DELETE /base/grupos/{grupo_id}` — remove carro (cascade nas viagens/membros).
- `POST /base/grupos/{grupo_id}/viagens` — cria viagem (sentido + hora) dentro do carro.
- `DELETE /base/viagens/{viagem_id}` — remove viagem.
- `PATCH /base/membros/{agenda_id}/mover` — move um membro pra uma `viagem_base` (id explícito) numa
  posição (`ordem`); se a viagem de destino não existir ainda pro carro, pode implicitamente criar (a
  definir na simulação: talvez seja mais simples exigir que a viagem já exista e o usuário crie via
  "+ Nova viagem" antes de arrastar pra ela).
- `GET /base/{dia_semana}` — lê a estrutura completa pra renderizar a tela (grupos + viagens + membros +
  não classificados).

## 8. O que muda pouco / o que muda muito

**Muda pouco** (reaproveita quase tudo):
- Renderização de card/viagem/passageiro no frontend (`CarroCard`, `LegBlock`, `PassageiroCard`) — a
  forma dos dados devolvidos continua parecida.
- Lógica de rotação de veículo/condutor por janela de horário (`_proximo_veiculo_livre`) — só passa a
  ser chamada com a lista de empresas resolvida por `viagem_base` em vez de por região/cluster de pin.
- Fase de preenchimento residual — é o algoritmo de hoje, só que rodando sobre "o que sobrou" em vez de
  "todo mundo".

**Muda muito**:
- Toda a semântica de agrupamento no preview deixa de ser inferida (`ordem` + região + pin) e vira
  **entidade persistida e editada explicitamente** (`grupo_base`/`viagem_base`/`membro_viagem_base`).
- O fluxo de drag-and-drop na tela Base muda de "solta em cima de alguém e o sistema decide" pra "solta
  dentro de uma viagem explícita" — mais parecido com mover cartão entre colunas do que com reordenar
  lista.
- `pin_ida_agenda_id`/`pin_retorno_agenda_id` e toda a resolução de clusters via union-find
  (`_resolver_clusters_pin`) deixam de ser necessários pro modo Base (só ficariam, se sobrar uso, restrito
  à geração real puxando `viagem_base` — mas aí a "aresta" já vem da tabela nova, não do pin).

## 9. Pontos em aberto (decidir depois da simulação)

1. Quando um `grupo_base` não é viável no dia real (nenhuma empresa atende a mistura de regiões daquele
   horário): split automático com aviso (proposto acima) ou bloquear a geração e pedir ajuste manual?
2. Quando sobra gente além da capacidade real dentro de uma viagem desenhada livremente: os excedentes
   são os últimos por `ordem` (proposto) ou outro critério?
3. Prioridade de quem fica "não classificado" no preenchimento residual: mantém `ordem_ida`/
   `ordem_retorno` como estão hoje, ou simplifica (nome/id)?
4. Um carro conceitual deve necessariamente virar **um único** veículo/condutor real ao longo do dia
   (tenta manter, quebra em mais de um só se não der — proposto), ou pode ser aceitável a geração já
   dividir livremente sem tentar preservar a unidade do carro?
5. Vale a pena o bootstrap automático (seção 4) ou prefere começar do zero por dia da semana?
6. `PATCH /base/membros/{agenda_id}/mover` exige que a viagem de destino já exista, ou deve poder criar
   uma viagem nova on-the-fly ao soltar num horário que ainda não existe naquele carro?

## 10. Ordem de implementação sugerida (quando/se for aprovado)

1. Migration + models das 3 tabelas novas.
2. Endpoints CRUD de grupo/viagem/membro (sem geração ainda) + schemas.
3. Frontend: nova tela de edição (criar carro/viagem, mover membro) reaproveitando componentes visuais
   existentes.
4. Script de bootstrap (seção 4), rodado manualmente uma vez por dia da semana como ponto de partida.
5. `gerar_agendamento_dia`: novo fluxo (seção 5), com os avisos de split/overflow visíveis na resposta.
6. Aposentar `montar_preview_semana`, `_resolver_clusters_pin`, pin fields (depois de confirmar que
   nada mais depende deles).
