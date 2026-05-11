# Manual do Usuário — Painel de Toner HFS

**Sistema:** HFS Painel Impressora Toner  
**Acesso:** http://127.0.0.1:8000 (ou endereço fornecido pelo TI)

---

## O que é este painel?

O Painel de Toner HFS permite visualizar, em tempo real, o nível de toner de todas as impressoras HP do hospital. Com ele você sabe, sem sair da mesa, quais impressoras estão com toner crítico e precisam de atenção imediata.

---

## 1. Tela Principal — Dashboard

Ao abrir o painel, você verá a tela principal com dois blocos:

### 1.1 Resumo no topo

Quatro cartões mostram a situação geral das impressoras:

| Cartão | O que significa |
|---|---|
| **Total ativo** | Quantidade total de impressoras monitoradas |
| **Crítico (≤10%)** | Impressoras com algum cartucho em 10% ou menos — **trocar urgente** |
| **Atenção (≤20%)** | Impressoras com algum cartucho entre 11% e 20% — **providenciar reposição** |
| **Sem dados** | Impressoras que ainda não tiveram leitura coletada |

### 1.2 Tabela de Impressoras

Cada linha da tabela é uma impressora. As colunas são:

| Coluna | O que significa |
|---|---|
| **Impressora** | Nome da impressora. Clique para ver o histórico detalhado |
| **IP** | Endereço de rede da impressora |
| **Local** | Andar ou setor onde a impressora está instalada |
| **Preto** | Nível do toner preto (barra + percentual) |
| **Ciano / Magenta / Amarelo** | Níveis dos toners coloridos (somente impressoras coloridas) |
| **Status** | Situação atual da impressora |
| **Coletado** | Data e hora da última leitura de toner |
| *(botão circular)* | Coletar leitura agora para esta impressora |

---

## 2. Entendendo as Barras de Toner

Cada cartucho é representado por uma barra colorida seguida do percentual:

```
████████░░░░  65%   → Nível OK
███░░░░░░░░░  18%   → Atenção — providenciar reposição
█░░░░░░░░░░░   7%   → Crítico — trocar imediatamente
```

- Barra **cheia e escura** = toner OK
- Barra **curta** = toner baixo
- **—** no lugar da barra = impressora monocromática (não tem esse cartucho)

---

## 3. Entendendo os Status (Badges)

| Badge | Cor | Significado |
|---|---|---|
| **✓ OK** | Verde | Todos os cartuchos acima de 20% |
| **! Atenção** | Amarelo/laranja | Algum cartucho entre 11% e 20% |
| **⚠ Crítico** | Vermelho | Algum cartucho em 10% ou menos |
| **Sem dados** | Cinza | Nenhuma leitura coletada ainda |

---

## 4. Busca de Impressoras

No canto superior direito da tabela há um campo de busca. Digite qualquer parte do:
- Nome da impressora
- Endereço IP
- Local (andar ou setor)

A tabela filtra automaticamente enquanto você digita. Limpe o campo para ver todas.

---

## 5. Auto-Atualização da Página

O painel se atualiza **automaticamente a cada 5 minutos**. Você verá o contador regressivo no topo da tabela:

```
Auto-refresh em  4:32
```

Quando chegar a 0:00, a página recarrega sozinha com os dados mais recentes do banco. Você não precisa apertar F5.

> **Atenção:** o auto-refresh atualiza a **página**, não coleta novos dados das impressoras. A coleta real acontece todo dia às 07:00 da manhã de forma automática.

Você também pode clicar no botão **"Atualizar"** a qualquer momento para recarregar na hora.

---

## 6. Coletando Dados de Uma Impressora na Hora

Se precisar saber o nível atual de uma impressora específica sem esperar a coleta do dia seguinte:

1. Localize a impressora na tabela
2. Clique no botão circular (↻) na última coluna
3. Aguarde — o ícone muda para um ampulheta enquanto busca
4. Ao terminar, a página recarrega com o dado atualizado

> Use esse botão com moderação — ele acessa a impressora diretamente pela rede.

---

## 7. Detalhes de uma Impressora

Clique no **nome** de qualquer impressora para abrir a página de detalhes. Lá você encontra:

- Informações cadastrais (IP, local, modelo, protocolo usado)
- Barras de toner atuais com percentuais
- **Histórico das últimas leituras** com data, hora e nível de cada cartucho

Útil para verificar se um cartucho está caindo rápido ou estável.

---

## 8. Quando Agir — Guia Rápido

| Situação | O que fazer |
|---|---|
| Badge **Crítico** (vermelho) | Solicitar troca do cartucho imediatamente |
| Badge **Atenção** (amarelo) | Solicitar reposição — pode durar alguns dias |
| Badge **OK** (verde) | Nenhuma ação necessária |
| **Sem dados** (cinza) | Informar ao TI — impressora pode estar desligada ou fora da rede |
| Coluna "Coletado" com data antiga | Informar ao TI — coleta automática pode ter falhado |

---

## 9. Planilha Excel para Verificação

Todo dia, junto com a coleta automática de toner, o sistema gera uma planilha Excel com:

- **Aba "Impressoras":** situação atual de todas as impressoras
- **Aba "Histórico 7 dias":** leituras da última semana por impressora
- **Aba "Sem Dados":** impressoras sem leitura (para verificação)

As colunas **"Verificado"** e **"Observação"** (em amarelo) são para o estagiário preencher manualmente após conferir fisicamente as impressoras críticas.

O arquivo fica salvo na pasta do sistema com o nome `verificacao_toner_AAAA-MM-DD.xlsx`.

---

## 10. Perguntas Frequentes

**O painel não carregou — o que faço?**  
Verifique com o TI se o servidor está rodando. O endereço de acesso é `http://127.0.0.1:8000` (ou outro informado pelo TI).

**A leitura de uma impressora está desatualizada há dias.**  
A coleta automática pode ter falhado. Use o botão ↻ na linha da impressora ou avise o TI.

**Aparece "Sem dados" para uma impressora que existe.**  
A impressora pode estar desligada, sem rede ou com SNMP/HTTP desabilitado. O TI precisa verificar.

**A impressora aparece com nome "Not Found".**  
O sistema não conseguiu identificar o nome dela na rede. O local e o IP são suficientes para identificação. O TI pode corrigir o nome pelo painel Admin.

**Posso confiar 100% nos percentuais mostrados?**  
Os dados vêm diretamente das impressoras via rede. Pequenas variações podem ocorrer dependendo do modelo HP. Em caso de dúvida, o nível físico do cartucho é sempre a referência final.

---

*Dúvidas ou problemas: contatar o setor de TI do HFS.*
