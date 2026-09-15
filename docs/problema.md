# Problema e Solução — EcoSala

## 1. Contexto

Salas de aula com temperatura elevada, umidade fora da faixa de conforto ou
iluminação insuficiente prejudicam a concentração e o rendimento dos alunos.
Diversos estudos de ergonomia e conforto ambiental apontam que condições fora
das faixas recomendadas aumentam a fadiga, reduzem a atenção e pioram o
desempenho em atividades cognitivas.

## 2. Problema real

Hoje a instituição **não possui nenhum dado objetivo** sobre as condições
ambientais das salas de aula. Não é possível responder perguntas simples como:

- Quais salas apresentam temperatura acima do ideal com mais frequência?
- Em quais horários do dia a umidade fica fora da faixa recomendada?
- Existe alguma sala com iluminação insuficiente durante as aulas noturnas?

Sem esses dados, a manutenção predial e a coordenação pedagógica atuam de forma
reativa (só quando alguém reclama), em vez de preventiva.

## 3. Público-alvo

- **Coordenação pedagógica / direção**: identificar salas problemáticas e
  priorizar manutenção (ar-condicionado, iluminação).
- **Setor de manutenção/facilities**: receber alertas objetivos em vez de
  reclamações informais.
- **Professores e alunos**: beneficiários indiretos de salas com melhor
  conforto ambiental.

## 4. Solução proposta — EcoSala

Um sistema IoT de monitoramento contínuo de conforto ambiental:

1. Um **ESP32** (simulado no Wokwi) em cada sala mede temperatura e umidade
   (sensor DHT22) e luminosidade (fotoresistor/LDR).
2. As leituras são publicadas via **MQTT** no broker **Mosquitto**.
3. Um **backend em Python** assina os tópicos MQTT, valida os dados, calcula o
   **status de conforto** (`OK`, `ATENCAO`, `CRITICO`) e persiste tudo no
   **InfluxDB** (banco de séries temporais).
4. Um **dashboard Web em Vue.js** exibe os valores atuais de cada sala, o
   status de conforto colorido e o histórico em gráficos, permitindo consultar
   diferentes períodos (15 min, 1h, 6h, 24h, 7 dias).

## 5. Faixas de referência (configuráveis via `.env`)

| Grandeza | Faixa ideal |
|---|---|
| Temperatura | 20 °C a 26 °C |
| Umidade relativa | 40% a 60% |
| Luminosidade | mínimo de 300 lux (aproximado via LDR) |

O status de conforto é calculado combinando as três grandezas:

- **OK**: todas as grandezas dentro da faixa ideal.
- **ATENCAO**: pelo menos uma grandeza levemente fora da faixa (dentro de uma
  margem de tolerância configurável).
- **CRITICO**: pelo menos uma grandeza significativamente fora da faixa.

A regra exata de cálculo está documentada e implementada em
`backend/app/domain/services/comfort_evaluator.py` (Etapa 4), permanecendo
isolada do restante do sistema para facilitar ajustes futuros nas faixas ou
nos critérios de classificação.

## 6. Por que IoT e não um formulário manual?

Um formulário manual dependeria de alguém percorrer as salas periodicamente,
o que é inviável em escala e não gera dados em tempo real. O monitoramento
automático permite:

- Dados contínuos, sem esforço humano recorrente.
- Alertas quase em tempo real (a cada ciclo de publicação, configurável,
  padrão de 5 segundos).
- Histórico consultável para identificar padrões (ex.: sala sempre quente às
  14h).

## 7. Escopo do 1º bimestre

- Leitura de temperatura, umidade e luminosidade em uma sala simulada.
- Cálculo de status de conforto e persistência histórica.
- Dashboard com valores atuais, status e histórico em gráfico.
- Comunicação **unidirecional** (dispositivo → sistema).

## 8. Escopo previsto para o 2º bimestre

Ver `docs/arquitetura.md`, seção "Evolução para o 2º bimestre": novos
sensores, atuadores com comunicação bidirecional, cadastro relacional de
salas/dispositivos/usuários e containerização com Docker.
