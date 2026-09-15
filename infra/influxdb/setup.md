# Setup do InfluxDB 2.x — EcoSala

Este guia cobre a instalação e configuração inicial do InfluxDB 2.x rodando
**localmente** (sem Docker neste bimestre). Os valores gerados aqui (URL,
organização, bucket, token) serão usados depois em `backend/.env` (Etapa 4/6)
— nenhum deles deve ser hardcoded no código.

## 1. Instalação (Windows)

**Opção A — instalador oficial (recomendado):**

1. Baixe o pacote Windows em https://www.influxdata.com/downloads/ (InfluxDB
   OSS 2.x).
2. Extraia o `.zip` em uma pasta de sua escolha, por exemplo
   `C:\influxdb2\`.
3. O pacote contém dois executáveis: `influxd.exe` (o servidor) e
   `influx.exe` (o cliente de linha de comando).

**Opção B — Chocolatey:**

```powershell
choco install influxdb
```

## 2. Iniciar o servidor

Em um terminal dedicado (deixe rodando durante todo o desenvolvimento e a
apresentação):

```powershell
& "C:\influxdb2\influxd.exe"
```

Por padrão, a API HTTP fica disponível em `http://localhost:8086`.

## 3. Configuração inicial (org, bucket, usuário, token)

**Opção A — via navegador (mais simples):**

1. Acesse http://localhost:8086 no navegador.
2. Clique em "Get Started" e preencha:
   - **Username**: `admin` (ou de sua escolha)
   - **Password**: escolha uma senha
   - **Organization Name**: `ecosala-org`
   - **Bucket Name**: `ecosala`
3. Ao concluir, vá em **Load Data → API Tokens** e gere (ou copie) um token
   com permissão de leitura/escrita no bucket `ecosala`.

**Opção B — via CLI (`influx setup`):**

```powershell
& "C:\influxdb2\influx.exe" setup `
  --username admin `
  --password "escolha-uma-senha-forte" `
  --org ecosala-org `
  --bucket ecosala `
  --retention 0 `
  --force
```

O comando imprime no final um `token` — copie e guarde-o.

## 4. Valores a anotar para o `.env` do backend (Etapa 4/6)

| Variável (prevista) | Valor de exemplo |
|---|---|
| `INFLUXDB_URL` | `http://localhost:8086` |
| `INFLUXDB_ORG` | `ecosala-org` |
| `INFLUXDB_BUCKET` | `ecosala` |
| `INFLUXDB_TOKEN` | *(token gerado no passo 3)* |

Nunca versione o token — ele só existirá em `backend/.env` (arquivo
ignorado pelo Git; `backend/.env.example` conterá apenas placeholders).

## 5. Teste manual do pipeline de escrita/leitura

Estes testes confirmam que o InfluxDB está pronto para receber os dados do
backend (Etapa 5), escrevendo manualmente um ponto no mesmo formato do
modelo de dados definido em `docs/arquitetura.md` (measurement `environment`,
tags `device_id`/`room_id`/`comfort_status`, fields `temperature`/
`humidity`/`luminosity`).

Defina o token em uma variável de ambiente da sessão do terminal (não fica
salvo em lugar nenhum):

```powershell
$env:INFLUX_TOKEN = "cole-o-token-aqui"
```

**Escrever um ponto de teste** (line protocol):

```powershell
& "C:\influxdb2\influx.exe" write `
  --bucket ecosala --org ecosala-org --token $env:INFLUX_TOKEN `
  --precision s `
  "environment,device_id=esp32-sala-101,room_id=sala-101,comfort_status=OK temperature=24.5,humidity=50.2,luminosity=450"
```

**Consultar de volta (Flux)** para confirmar que o ponto foi gravado:

```powershell
& "C:\influxdb2\influx.exe" query `
  --org ecosala-org --token $env:INFLUX_TOKEN `
  'from(bucket:"ecosala") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "environment")'
```

Você deve ver uma tabela com as colunas `_time`, `_field`, `_value`,
`device_id`, `room_id`, `comfort_status` etc.

**Ou visualmente**, no navegador: http://localhost:8086 → **Data Explorer**
→ selecione o bucket `ecosala` → measurement `environment` → **Submit**.

## 6. Checklist de conclusão da Etapa 2 (InfluxDB)

- [ ] `influxd` rodando e acessível em `http://localhost:8086`.
- [ ] Organização `ecosala-org` e bucket `ecosala` criados.
- [ ] Token com permissão de leitura/escrita gerado e anotado.
- [ ] Ponto de teste escrito e visível no Data Explorer / via `influx query`.
