# Configuração do Agendamento — HFS Painel Toner

## Problema Resolvido

O agendamento via `.bat` requer permissões administrativas no Windows. A solução é usar o script Python standalone `coletar.py` que **não depende de BAT** nem de permissões admin.

---

## Instalação Rápida

### 1. Atualizar o repositório

```powershell
cd C:\Pietro\Projetos\HFS_PAINEL_IMPRESSORA_TONER\HFS_PAINEL_IMPRESSORA_TONER
git pull origin master
```

### 2. Testar manualmente

Sem necessidade de permissões administrativas:

```powershell
.\venv\Scripts\python coletar.py
```

Ou com exportação de Excel:

```powershell
.\venv\Scripts\python coletar.py --exportar
```

**Saída esperada:**
```
======================================================================
HFS - Coleta Automática de Toner
11/06/2026 16:26:09
======================================================================

[1/2] Coletando níveis de toner de todas as impressoras...

Coleta finalizada: 89 impressoras
  Sucesso : 79
  Falha   : 10

[2/2] Gerando planilha Excel para verificação...

Planilha gerada: C:\Pietro\...\verificacao_toner_20260611.xlsx
```

---

## Configuração no Windows Task Scheduler

### Removar tarefas antigas (com BAT)

Se existirem tarefas antigas apontando para `.bat`, remova:

```powershell
schtasks /delete /tn "\HFS_Toner_Coletar_06h" /f
schtasks /delete /tn "\HFS_Toner_Coletar_12h" /f
schtasks /delete /tn "\HFS_Toner_Coletar_18h" /f
```

### Criar tarefas novas (Python)

**Para cada horário (06h, 12h, 18h):**

```powershell
$python = "C:\Pietro\Projetos\HFS_PAINEL_IMPRESSORA_TONER\HFS_PAINEL_IMPRESSORA_TONER\venv\Scripts\python.exe"
$script = "coletar.py"
$cwd = "C:\Pietro\Projetos\HFS_PAINEL_IMPRESSORA_TONER\HFS_PAINEL_IMPRESSORA_TONER"

# 06:00
schtasks /create /tn "HFS_Toner_Coletar_06h" /tr "$python $script --exportar" /sc daily /st 06:00 /f

# 12:00
schtasks /create /tn "HFS_Toner_Coletar_12h" /tr "$python $script --exportar" /sc daily /st 12:00 /f

# 18:00
schtasks /create /tn "HFS_Toner_Coletar_18h" /tr "$python $script --exportar" /sc daily /st 18:00 /f
```

### Ou via UI (GUI)

1. Abra **Agendador de Tarefas** (`taskschd.msc`)
2. **Criar Tarefa Básica**
3. **Nome:** `HFS_Toner_Coletar_06h`
4. **Acionador:** Diário às 06:00
5. **Ação:**
   - **Programa/Script:** `C:\Pietro\Projetos\HFS_PAINEL_IMPRESSORA_TONER\HFS_PAINEL_IMPRESSORA_TONER\venv\Scripts\python.exe`
   - **Argumentos:** `coletar.py --exportar`
   - **Iniciar em:** `C:\Pietro\Projetos\HFS_PAINEL_IMPRESSORA_TONER\HFS_PAINEL_IMPRESSORA_TONER`
6. **Repetir para 12h e 18h**

---

## Validação

### Verificar tarefas criadas

```powershell
schtasks /query /tn "HFS_Toner_Coletar_06h" /fo LIST /v
schtasks /query /tn "HFS_Toner_Coletar_12h" /fo LIST /v
schtasks /query /tn "HFS_Toner_Coletar_18h" /fo LIST /v
```

### Verificar última execução

```powershell
Get-ScheduledTaskInfo -TaskName "HFS_Toner_Coletar_06h"
```

### Executar manualmente para teste

```powershell
schtasks /run /tn "HFS_Toner_Coletar_06h"
```

---

## Troubleshooting

### "Module not found" ao executar

Certifique-se de que o venv foi criado corretamente:

```powershell
cd C:\Pietro\Projetos\HFS_PAINEL_IMPRESSORA_TONER\HFS_PAINEL_IMPRESSORA_TONER
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
```

### "ModuleNotFoundError: No module named 'django'"

O venv pode estar corrompido (criado em outro Python). Recrie:

```powershell
Remove-Item -Recurse -Force venv
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
```

### Script não executa no Task Scheduler mas roda manualmente

Verifique se o usuário da tarefa tem permissão de leitura/escrita em:
- `C:\Pietro\Projetos\HFS_PAINEL_IMPRESSORA_TONER\HFS_PAINEL_IMPRESSORA_TONER\`
- `C:\Pietro\Projetos\HFS_PAINEL_IMPRESSORA_TONER\HFS_PAINEL_IMPRESSORA_TONER\db.sqlite3`

---

## Referência Rápida

| Comando | Uso |
|---------|-----|
| `python coletar.py` | Apenas coleta (sem Excel) |
| `python coletar.py --exportar` | Coleta + gera planilha Excel |
| `python manage.py collect_toner` | Alternativa: Django management command |
| `python manage.py exportar_excel` | Apenas gera planilha |

---

## Notas

- O script **não requer permissões administrativas**
- Banco de dados: **SQLite** (sem PostgreSQL necessário)
- Timezone: **America/Sao_Paulo** (PT-BR)
- Encoding: **UTF-8** (sem problemas de Windows PT-BR)
