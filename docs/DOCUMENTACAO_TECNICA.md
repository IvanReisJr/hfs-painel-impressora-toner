# Documentação Técnica — HFS Painel Impressora Toner

**Versão:** 1.3.0  
**Projeto:** Monitoramento de toner de impressoras HP — Hospital  
**Responsável inicial:** Ivan Reis  
**Data:** Maio/2026

---

## 1. Visão Geral

Sistema web interno para monitorar em tempo real o nível de toner de ~90 impressoras HP distribuídas pelo hospital. Os dados são coletados via protocolo SNMP e/ou HTTP (EWS — Embedded Web Server das impressoras HP). O sistema descobre automaticamente impressoras novas na rede, armazena histórico de leituras e exporta relatórios Excel para verificação manual pelos estagiários.

---

## 2. Stack Tecnológico

| Camada | Tecnologia | Versão |
|---|---|---|
| Linguagem | Python | 3.12 |
| Framework web | Django | 5.1 |
| Banco de dados | SQLite | (built-in) |
| Coleta SNMP | pysnmp | 6.2 |
| Coleta HTTP/EWS | requests + lxml | — |
| Relatório Excel | openpyxl | — |
| Arquivos estáticos | whitenoise | — |
| Agendamento in-process | django-apscheduler (APScheduler) | — |
| Agendamento OS | Windows Task Scheduler | — |
| Configuração por ambiente | python-decouple | — |
| Testes | pytest + pytest-django | — |

---

## 3. Arquitetura do Projeto

```
HFS_PAINEL_IMPRESSORA_TONER/
├── hfs_toner/                  # Configurações Django
│   ├── settings.py             # Config principal (decouple + .env)
│   ├── urls.py                 # Roteamento raiz
│   └── wsgi.py
├── printers/                   # App principal
│   ├── models.py               # Printer + TonerReading
│   ├── views.py                # Dashboard, detalhe, APIs
│   ├── urls.py                 # Rotas do app
│   ├── admin.py                # Admin Django
│   ├── scheduler.py            # APScheduler (coleta automática in-process)
│   ├── services/
│   │   ├── snmp_client.py      # Coleta via SNMP (MIB-II Printer)
│   │   ├── http_client.py      # Coleta via HTTP/EWS (JSON + XML)
│   │   ├── collector.py        # Orquestra SNMP→HTTP (AUTO fallback)
│   │   └── discovery.py        # Varredura de rede (ThreadPoolExecutor)
│   ├── management/commands/
│   │   ├── collect_toner.py    # python manage.py collect_toner
│   │   ├── importar_impressoras.py  # python manage.py importar_impressoras
│   │   ├── descobrir_impressoras.py # python manage.py descobrir_impressoras
│   │   └── exportar_excel.py   # python manage.py exportar_excel
│   └── templates/printers/
│       ├── base.html
│       ├── dashboard.html
│       ├── printer_detail.html
│       └── _toner_bar.html
├── tests/                      # Suíte de testes (103 testes)
├── docs/                       # Esta documentação
├── executar_coleta.bat         # Script diário completo
├── modelo_impressoras.csv      # Template para importação manual
├── requirements.txt
└── .env                        # Variáveis de ambiente (não versionado)
```

---

## 4. Modelos de Dados

### 4.1 `Printer`

Representa uma impressora cadastrada no sistema.

| Campo | Tipo | Descrição |
|---|---|---|
| `name` | CharField | Nome/hostname da impressora |
| `ip_address` | GenericIPAddressField (unique) | IP — chave natural do sistema |
| `location` | CharField | Localização física (andar, setor) |
| `model_name` | CharField | Modelo HP (ex: LaserJet MFP E42540) |
| `protocol` | CharField | AUTO / SNMP / HTTP |
| `snmp_community` | CharField | Community string SNMP (padrão: `public`) |
| `is_color` | BooleanField | Se possui cartuchos coloridos |
| `is_active` | BooleanField | Se deve ser incluída nas coletas |

**Propriedades calculadas:**
- `latest_reading` — retorna o `TonerReading` mais recente ordenado por `(-collected_at, -pk)`

### 4.2 `TonerReading`

Cada linha representa uma leitura de toner em um momento específico.

| Campo | Tipo | Descrição |
|---|---|---|
| `printer` | FK → Printer | Impressora associada |
| `black_pct` | IntegerField nullable | Toner preto em % |
| `cyan_pct` | IntegerField nullable | Toner ciano em % (coloridas) |
| `magenta_pct` | IntegerField nullable | Toner magenta em % |
| `yellow_pct` | IntegerField nullable | Toner amarelo em % |
| `protocol_used` | CharField | SNMP ou HTTP (qual funcionou) |
| `success` | BooleanField | Se a coleta teve sucesso |
| `error_message` | TextField | Mensagem de erro se falhou |
| `collected_at` | DateTimeField | Timestamp da coleta (auto) |

**Propriedade `alert_level`:**
- `"critical"` — qualquer cartucho ≤ 10%
- `"warning"` — qualquer cartucho ≤ 20%
- `"ok"` — todos > 20%

---

## 5. Fluxo de Coleta de Dados

### 5.1 Protocolo AUTO (padrão)

```
collect_printer(printer)
    │
    ├─ Tenta SNMP primeiro
    │      └─ pysnmp.hlapi.asyncio → GET Printer MIB (OIDs 43.11.1.1.8/9)
    │              ├─ Sucesso → salva TonerReading (protocol_used="SNMP")
    │              └─ Falha   → tenta HTTP
    │
    └─ HTTP/EWS
           ├─ GET /sws/app/information/consumables/consumables.json (JSON)
           ├─ GET /DevMgmt/ProductUsageDyn.xml (XML)
           └─ Salva TonerReading (protocol_used="HTTP")
```

### 5.2 OIDs SNMP utilizados

| OID | MIB | Descrição |
|---|---|---|
| `1.3.6.1.2.1.43.11.1.1.9.1.X` | Printer-MIB | Nível atual do cartucho slot X |
| `1.3.6.1.2.1.43.11.1.1.8.1.X` | Printer-MIB | Capacidade máxima slot X |
| `1.3.6.1.2.1.1.1.0` | MIB-II | sysDescr (identificação do device) |
| `1.3.6.1.2.1.1.5.0` | MIB-II | sysName (hostname) |
| `1.3.6.1.2.1.1.6.0` | MIB-II | sysLocation (localização configurada) |

Slots: 1=Preto, 2=Ciano, 3=Magenta, 4=Amarelo.

Caso `maxCapacity == -2`, a impressora já retorna o valor diretamente em percentual (modo direto HP).

### 5.3 Endpoints HTTP/EWS utilizados

| Endpoint | Formato | Uso |
|---|---|---|
| `/sws/app/information/consumables/consumables.json` | JSON | Nível de toner (preferencial) |
| `/DevMgmt/ProductUsageDyn.xml` | XML | Fallback quando JSON não disponível |
| `/hp/device/DeviceInformation/Index` | HTML | Nome, localização, serial (discovery) |
| `/DevMgmt/ProductConfigDyn.xml` | XML | Localização e alias (discovery) |

---

## 6. Descoberta Automática de Impressoras

O comando `descobrir_impressoras` varre ranges CIDR com `ThreadPoolExecutor` (50 workers padrão).

**Por IP testado (`scan_ip`):**
1. Verifica TCP nas portas 80, 443 ou 161 (UDP — pré-filtro rápido)
2. Faz probe HTTP: confirma se é HP, detecta cor, extrai nome/modelo
3. Faz probe SNMP: extrai sysDescr, sysName, sysLocation
4. Prioridade de localização: HTTP > SNMP
5. Filtra apenas HP (flag `--todos` inclui todos os dispositivos)

**Rede monitorada:** `192.168.100.0/22` (~1.022 IPs)  
**Tempo médio de varredura:** ~95 segundos com 50 workers

---

## 7. Agendamento Automático

### 7.1 Windows Task Scheduler (principal)

Tarefa: **HFS_Coleta_Toner**  
Horário: **07:00 diariamente**  
Script: `executar_coleta.bat`

O bat executa em sequência:
```
1. descobrir_impressoras 192.168.100.0/22  → descobre IPs novos
2. importar_impressoras --atualizar        → cadastra/atualiza no banco
3. collect_toner                           → lê toner de todas as ativas
4. exportar_excel verificacao_YYYY-MM-DD   → gera planilha do dia
```

### 7.2 APScheduler (in-process — backup)

Configurado em `printers/scheduler.py` com `MemoryJobStore` (não persiste entre reinicializações). Executa `collect_all_active()` às 07:00 horário de Brasília enquanto o servidor Django estiver rodando. É um backup caso o Task Scheduler falhe.

---

## 8. Rotas da Aplicação

| URL | View | Descrição |
|---|---|---|
| `/` | `dashboard` | Lista todas as impressoras com status |
| `/impressora/<id>/` | `printer_detail` | Histórico de leituras de uma impressora |
| `/api/status/<id>/` | `api_status` | JSON com última leitura (GET) |
| `/api/coletar/<id>/` | `api_collect_now` | Coleta imediata de uma impressora (POST) |
| `/admin/` | Django Admin | Gerenciamento completo |

---

## 9. Configuração do Ambiente (.env)

```ini
SECRET_KEY=sua-chave-secreta-aqui
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,<IP-do-servidor>

# Timeouts de coleta (segundos)
SNMP_TIMEOUT=3
HTTP_TIMEOUT=5
```

O arquivo `.env` não é versionado (consta no `.gitignore`). Em produção, copiar `.env.example` e preencher.

---

## 10. Testes

```bash
# Rodar suíte completa
pytest

# Com cobertura
pytest --tb=short -q
```

103 testes distribuídos em:

| Arquivo | Escopo |
|---|---|
| `tests/test_snmp_client.py` | Parsing de OIDs, cálculo de percentual, modo max==-2 |
| `tests/test_http_client.py` | Parsing JSON EWS, parsing XML, fallback |
| `tests/test_collector.py` | Lógica AUTO: SNMP→HTTP fallback |
| `tests/test_models.py` | `latest_reading`, `alert_level`, tiebreaker de pk |
| `tests/test_views.py` | Dashboard, detalhe, API collect |
| `tests/test_importar_impressoras.py` | CSV parsing, upsert, dry-run, validação |
| `tests/test_discovery.py` | scan_ip, filtro HP, prioridade de localização |

---

## 11. Deploy Local (Windows)

```bash
# 1. Criar ambiente virtual
python -m venv venv
venv\Scripts\activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar .env (copiar e editar)
copy .env.example .env

# 4. Migrar banco
python manage.py migrate

# 5. Criar superusuário para o Admin
python manage.py createsuperuser

# 6. Rodar servidor
python manage.py runserver 0.0.0.0:8000
```

**Importante:** definir `set PYTHONUTF8=1` e `set PYTHONIOENCODING=utf-8` antes de rodar os management commands no terminal Windows para evitar erros de encoding.

---

## 12. Repositório

GitHub: [IvanReisJr/hfs-painel-impressora-toner](https://github.com/IvanReisJr/hfs-painel-impressora-toner)

---

## 13. Pontos de Atenção para Manutenção

- **Impressoras falsas no banco:** dispositivos não-HP (switches, servidores) podem ser descobertos com `--todos`. Desativar via Admin (`is_active = False`).
- **SNMP community:** padrão `public`. Se a rede mudar para community privada, atualizar campo por impressora ou no `.env`.
- **Banco SQLite:** adequado para o volume atual (~90 impressoras, leitura diária). Se o histórico crescer muito (> 2 anos), avaliar migração para PostgreSQL.
- **pysnmp 6.2:** usa `pysnmp.hlapi.asyncio` — versões anteriores usavam `pysnmp.hlapi` diretamente. Não fazer downgrade.
- **Porta 161 UDP:** o firewall do Windows pode bloquear respostas SNMP. Verificar se a regra de entrada UDP 161 está liberada caso coletas SNMP falhem.
