1) Controle de km (odometro)
[ ] Criar modelos para controle de rodagem por veiculo, periodo (de | ate) km (inicial | final), em um primeiro momento registros seram feitos mensalmente, dia 01-31 (primeiro a ultimo dia do mes) mais abordagem permite lançamentos diarios semanais, etc, no futuro caso se mostr necessário.
[ ] Teremos nova tela Resumos, entrada no painel lateral, abaixo de usuarios, aqui será listado um dashboard com um resumo dos dados por um periodo, seleção rápida pelo mes/ano (aplica filtros do dia 01 - final do mes), resumos relevantes (agrupados por visao de indicador, 3 visoes selecionais):

## Rodagem
[ ] km rodado por veiculo, empresa, condutor (em todos os casos acumulado do periodo)
[ ] evolução do km rodado por empresa, ideia aqui eh mostrar os ultimos N meses, pensei em inferir 6 meses contando com o periodo alvo, inicio periodo buscado assume o mês e mais 5 meses anteriores, faz sentido?
[ ] Resumo por empresa comparar com percentual de contrato, requer adicionar no modelo de empresa campo (float, decimal, ou similar) para registrar participação no sistema (pode sugerir nome do campo)
[ ] Resumo diário de uso de frota, (table) com campos [dd;ddd;empresaX;empresaY] 

## Atendimentos
** ddd = dia da semana (ex: SEG;TER)
[ ] Resumo dos atendimentos (usuarios atendidos) uma tabela detalhada (data eixo de linha e horario eixo de coluna) com a quantidade de atendimentos PLANEJADOS (indiferente se foi cancelado ou não), se entrou na geração conta, apenas excessões antecipadas são ignoradas aqui.
[ ] Historico de cancelamentos
[ ] Cancelamento por usuario, aqui separar em dois contadores (cancelamento | viagem perdida) 

## Outros



Aqui eh uma prévia, quero sugestão de outros indicadores interessantes que podem ser inferidos


alguns pontos:
> o cadastro de km, essa lista vai crescer rapidamente, seria interessante adicionar um filtro (por mes/ano provavelmente) e so listar quando selecionado o filtro
> no lostfocus da data de inicio, podia popular a data de im com o ultimo dia do mes selecionado
> 