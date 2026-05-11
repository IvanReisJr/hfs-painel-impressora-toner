# Changelog — HFS Painel Impressora Toner

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [1.3.0] — 2026-05-11

### Adicionado
- `_http_device_info()`: raspa `/hp/device/DeviceInformation/Index` (EWS novo firmware) e `/DevMgmt/ProductConfigDyn.xml` para extrair automaticamente **Localização**, **Apelido** e **Número de Série** da impressora
- `_snmp_probe()` agora coleta `sysName` e `sysLocation` (OID `1.3.6.1.2.1.1.6.0`) além de `sysDescr` — `sysLocation` é o mesmo campo que "Localização do dispositivo" no EWS HP
- `DiscoveryResult` ganhou campos `location` e `serial`; `location` é preenchido automaticamente durante a varredura
- CSV de descoberta agora inclui colunas `location` (preenchida) e `serial`
- Tabela de saída do comando exibe coluna Localização ao lado do nome
- `_extract_field_after_label()` e `_extract_xml_text()`: utilitários de parsing HTML/XML para EWS
- 13 novos testes unitários para os novos utilitários e comportamentos

---

## [1.2.0] — 2026-05-11

### Adicionado
- `printers/services/discovery.py`: serviço de varredura de rede
  - `scan_ip()`: sonda um único IP via TCP, HTTP (SWS JSON + EWS) e SNMP, detecta HP e extrai nome/modelo
  - `scan_range()`: varre múltiplos ranges CIDR em paralelo com `ThreadPoolExecutor`
  - Detecção de impressoras coloridas via HTTP e SNMP sysDescr
  - Fallback automático de protocolo: `auto` quando ambos respondem, `snmp` ou `http` quando só um funciona
- `python manage.py descobrir_impressoras <ranges>`: varredura completa da rede
  - Suporta múltiplos ranges CIDR: `192.168.103.0/24 192.168.100.0/24`
  - Flags `--workers` (padrão 50), `--timeout` (padrão 3s), `--todos`, `--saida`
  - Gera `impressoras_descobertas.csv` pronto para `importar_impressoras`
  - Exibe tabela com IP, nome, cor, SNMP✓/✗, HTTP✓/✗ e protocolo detectado
- 18 novos testes unitários em `tests/test_discovery.py`

---

## [1.1.0] — 2026-05-11

### Adicionado
- `python manage.py importar_impressoras arquivo.csv`: importação em lote de impressoras via CSV
  - Upsert por IP: cria novas e, com `--atualizar`, atualiza existentes
  - Flag `--dry-run`: simula a importação sem gravar no banco
  - Validação de colunas obrigatórias (`name`, `ip_address`) com relatório de erros por linha
  - Suporte a encoding UTF-8 com BOM (arquivo salvo pelo Excel)
  - Arquivo de modelo `modelo_impressoras.csv` incluído na raiz do projeto
- 20 novos testes unitários em `tests/test_importar_impressoras.py`

---

## [1.0.0] — 2026-05-11

### Adicionado
- Projeto Django 5.1 com app `printers`
- Model `Printer`: cadastro de impressoras com IP, nome, localização, protocolo (SNMP/HTTP/Auto), community SNMP, flag colorida
- Model `TonerReading`: snapshot diário de toner com black/cyan/magenta/yellow (%), protocolo usado, status de sucesso e mensagem de erro
- `printers.services.snmp_client`: coleta via SNMP v2c usando OIDs padrão RFC 3805 (prtMarkerSupplies), suporte a printers com max=-2 (percentual direto)
- `printers.services.http_client`: coleta via HTTP tentando HP SWS JSON (`/sws/app/information/consumables/consumables.json`) e HP EWS XML (`/DevMgmt/ProductUsageDyn.xml`, `/DevMgmt/ConsumableConfigDyn.xml`)
- `printers.services.collector`: orquestrador com estratégia AUTO (SNMP com fallback HTTP), SNMP apenas, ou HTTP apenas por impressora
- `python manage.py collect_toner`: management command para coleta manual ou por IP específico
- APScheduler com `DjangoJobStore`: coleta automática diária às 07:00 (America/Sao_Paulo)
- Dashboard HTML com Bootstrap 5: tabela de todas as impressoras, barras de toner coloridas, badges de alerta (crítico/atenção/ok), busca em tempo real e botão "Coletar agora"
- Página de detalhe: gráfico Chart.js com histórico de 30 dias por cor, cards de toner atual
- API REST JSON: `GET /api/status/` e `POST /api/coletar/<id>/`
- Django Admin completo com inline de leituras e indicador visual de toner
- Testes unitários com `pytest-django`: 30+ testes cobrindo models, services (snmp, http, collector) e views
- `whitenoise` para servir arquivos estáticos
- `python-decouple` para configuração via `.env`
- `requirements.txt` e `pytest.ini`
