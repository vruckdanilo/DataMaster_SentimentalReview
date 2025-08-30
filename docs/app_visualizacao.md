# 📊 Aplicação de Visualização - DataMaster SentimentalReview

![Dashboard Magic](https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExdmM0cDBiZml4eWRqaTIzcmN4aGV3ZWhnZ2FtaTF0dG5vbjhsNjcwMiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/26n6WywJyh39n1pBu/giphy.gif)

**NOTA:** Este documento descreve a aplicação de visualização planejada. O Apache Superset está configurado no docker-compose.yml mas os dashboards ainda não foram implementados.

Este documento detalha a aplicação de visualização construída com Apache Superset, apresentando dashboards interativos para análise de sentimentos e KPIs de agências Santander.

---

## 📋 Índice

- [🎯 Visão Geral da Aplicação](#-visão-geral-da-aplicação)
- [📈 Dashboards e Métricas](#-dashboards-e-métricas)
- [🚀 Configuração e Acesso](#-configuração-e-acesso)
- [🖼️ Navegação e Interface](#️-navegação-e-interface)
- [📖 Diário de Bordo](#-Diário-de-Bordo)

---

## 🎯 Visão Geral da Aplicação



### Stack de Visualização

**Tecnologia Principal:** Apache Superset (latest)
**Conexão de Dados:** Trino Query Engine → Hive Metastore → Delta Lake → MinIO
**Arquitetura:** Web-based BI com dashboards interativos

### Propósito e Audiência

| Dashboard | Audiência | Objetivo | Frequência de Uso |
|-----------|-----------|----------|-------------------|
| **Executive Overview** | C-Level, Diretores | Visão estratégica geral | Semanal |
| **Agency Performance** | Gerentes Regionais | Performance por agência | Diário |
| **Sentiment Analysis** | Analistas de CX | Análise de satisfação | Diário |
| **Risk Management** | Compliance, Risco | Alertas reputacionais | Tempo real |

---

## 📈 Dashboards e Métricas

![Charts and Graphs](https://media.giphy.com/media/3oKIPEqDGUULpEU0aQ/giphy.gif)

### 1. 📊 Executive Overview Dashboard


**Objetivo:** Visão executiva consolidada dos KPIs principais

**Métricas Principais:**
- **NPS Score Geral:** Agregação de todas as agências
- **Distribuição de Sentimentos:** Pie chart (Positivo/Neutro/Negativo)
- **Tendência Temporal:** Line chart dos últimos 12 meses
- **Top 5 Agências:** Ranking por performance
- **Alertas Críticos:** Counter de riscos reputacionais

**Fonte de Dados:** `datalake.agency_performance_kpis`

```sql
-- Query principal do Executive Dashboard
SELECT 
    COUNT(DISTINCT place_id) as total_agencias,
    AVG(rating_medio) as nps_geral,
    SUM(total_reviews) as avaliacoes_totais,
    ROUND(SUM(reviews_positivos) * 100.0 / SUM(total_reviews), 2) as perc_positivos,
    ROUND(SUM(reviews_negativos) * 100.0 / SUM(total_reviews), 2) as perc_negativos
FROM datalake.agency_performance_kpis
WHERE gold_timestamp >= CURRENT_DATE - INTERVAL '30' DAY;
```

### 2. 🏢 Agency Performance Dashboard



**Objetivo:** Análise detalhada por agência e região

**Visualizações:**
- **Mapa de Calor:** Performance por bairro
- **Ranking Interativo:** Filtros por região/período
- **Drill-down:** Agência → Avaliações individuais
- **Comparativo:** Benchmark vs média regional

**Fonte de Dados:** `datalake.agency_performance_kpis` (tabela gerada pelo job silver_to_gold_working.py)

```sql
-- Query do mapa de performance
SELECT 
    bairro,
    COUNT(DISTINCT place_id) as agencias_no_bairro,
    AVG(rating_medio) as rating_medio_bairro,
    SUM(total_reviews) as total_avaliacoes_bairro,
    CASE 
        WHEN AVG(rating_medio) >= 4.0 THEN 'Excelente'
        WHEN AVG(rating_medio) >= 3.5 THEN 'Bom'
        WHEN AVG(rating_medio) >= 3.0 THEN 'Regular'
        ELSE 'Crítico'
    END as status_bairro
FROM datalake.agency_performance_kpis
GROUP BY bairro
ORDER BY rating_medio_bairro DESC;
```

### 3. 💭 Sentiment Analysis Dashboard



**Objetivo:** Análise profunda de sentimentos e feedback

**Componentes:**
- **Sentiment Distribution:** Distribuição de sentimentos por período
- **Sentiment Timeline:** Evolução temporal dos sentimentos
- **Review Analysis:** Análise de reviews por rating e sentimento
- **Correlation Matrix:** Correlação rating vs sentimento

**Fonte de Dados:** `silver.google_maps_reviews_enriched`

```sql
-- Query de análise temporal de sentimentos
SELECT 
    DATE_TRUNC('month', CAST(data_coleta AS DATE)) as mes,
    sentimento,
    COUNT(*) as total_reviews,
    AVG(CAST(rating_review AS DOUBLE)) as rating_medio,
    -- Nota: sentimento_score não existe no schema real
    COUNT(*) as total_por_sentimento
FROM silver.google_maps_reviews_enriched 
WHERE data_coleta >= CURRENT_DATE - INTERVAL '12' MONTH
GROUP BY DATE_TRUNC('month', CAST(data_coleta AS DATE)), sentimento
ORDER BY mes DESC, sentimento;
```

### 4. ⚠️ Risk Management Dashboard

**Objetivo:** Monitoramento de riscos reputacionais

**Alertas em Tempo Real:**
- **Críticos:** Riscos que requerem ação imediata
- **Médios:** Monitoramento próximo necessário
- **Baixos:** Acompanhamento de rotina

**Fonte de Dados:** `datalake.risk_alerts`

```sql
-- Query de alertas de risco
SELECT 
    place_id,
    nome_agencia,
    total_reviews_negativas as total_ocorrencias,
    CASE 
        WHEN total_reviews_negativas > 10 THEN 'ALTO'
        WHEN total_reviews_negativas > 5 THEN 'MEDIO'
        ELSE 'BAIXO'
    END as nivel_risco
FROM datalake.risk_alerts
WHERE total_reviews_negativas > 0
ORDER BY total_reviews_negativas DESC;
```

---

## 🚀 Configuração e Acesso



### Inicialização Local

```bash
# 1. Iniciar todo o ambiente
[`./scripts/start.sh`](../scripts/start.sh)

# 2. Aguardar inicialização (5-10 minutos)
# 3. Verificar se Superset está rodando
curl -f http://localhost:8088/health

# 4. Acessar interface web
# URL: http://localhost:8088
# Usuário: admin
# Senha: admin123
```

### Configuração da Conexão de Dados

**Passo 1: Conectar ao Trino**
```
Database Type: Other
Database Name: DataLakehouse
SQLAlchemy URI: trino://admin@trino-coordinator:8080/hive/default
```

**Passo 2: Testar Conectividade**
```sql
-- Query de teste no SQL Lab
SELECT COUNT(*) as total_records 
FROM silver.google_maps_reviews_enriched 
LIMIT 10;
```

**Passo 3: Criar Datasets**
- Navegar para **Data → Datasets**
- Adicionar datasets baseados nas tabelas Datalake (Gold layer)
- Configurar refresh automático

### Endpoints de Configuração

| Serviço | URL Local | Propósito |
|---------|-----------|-----------|
| **Superset Web** | http://localhost:8088 | Interface principal |
| **Trino Coordinator** | http://localhost:8080 | Query engine |
| **Spark Master UI** | http://localhost:8082 | Monitoramento Spark |
| **MinIO Console** | http://localhost:9001 | Gestão de dados |
| **Airflow** | http://localhost:8089 | Orquestração de pipelines |

---

## 🖼️ Navegação e Interface

![User Interface](https://media.giphy.com/media/xTiTnxpQ3ghPiB2Hp6/giphy.gif)

### Fluxo de Navegação Principal

```
Login → Home Dashboard → [Escolher Dashboard] → Drill-down → Análise Detalhada
```

### Instruções de Navegação

#### 1. **Primeiro Acesso**
1. Acesse http://localhost:8088
2. Login: `admin` / Senha: `admin123`
3. Clique em **"Dashboards"** no menu superior
4. Selecione **"Executive Overview"** para visão geral

#### 2. **Criando Novos Charts**
1. Vá para **Data → Datasets**
2. Selecione dataset (ex: `agency_performance_kpis`)
3. Clique **"Create Chart"**
4. Escolha tipo de visualização
5. Configure métricas e dimensões
6. Salve e adicione ao dashboard

#### 3. **Configurando Filtros**
1. No dashboard, clique **"Edit Dashboard"**
2. Adicione **"Filter Box"** component
3. Configure filtros por:
    - Período (data_coleta)
   - Bairro (bairro)
   - Sentimento (sentimento)
4. Salve as alterações

#### 4. **Exportando Relatórios**
1. Abra o dashboard desejado
2. Clique no menu **"..."** no canto superior direito
3. Selecione **"Download as PDF"** ou **"Email Report"**
4. Configure periodicidade se necessário


### Navegação por Perfil de Usuário

#### **Executivos (C-Level)**
```
Home → Executive Overview → [Filtro: Últimos 30 dias] → Export PDF
```

#### **Gerentes Regionais**
```
Home → Agency Performance → [Filtro: Região específica] → Drill-down agência
```

#### **Analistas de CX**
```
Home → Sentiment Analysis → SQL Lab → Análise customizada
```

#### **Compliance/Risco**
```
Home → Risk Management → [Filtro: Alertas críticos] → Export para investigação
```

---

##  📖 Diário de Bordo



### 🎯 Estratégia de UX/UI

### Escolhas de Visualização

#### **Por que Superset vs outras ferramentas?**

**Vantagens do Superset:**
- ✅ **Open Source:** Zero custo de licenciamento
- ✅ **SQL Native:** Analistas podem criar queries customizadas
- ✅ **Extensível:** Plugins e customizações possíveis
- ✅ **Integração Trino:** Conectividade nativa com nosso stack

**Trade-offs aceitos:**
- ❌ **Curva de aprendizado:** Mais técnico que PowerBI/Tableau
- ❌ **Recursos avançados:** Menos features que ferramentas pagas
- ❌ **Suporte:** Comunidade vs suporte comercial





---

## 💡 Dica Rápida

**Para criar um novo dashboard rapidamente:**
```sql
-- 1. Acesse SQL Lab no Superset
-- 2. Execute query de validação
SELECT * FROM datalake.agency_performance_kpis LIMIT 5;

-- 3. Salve como dataset
-- 4. Create Chart → Dashboard
-- 5. Configure filtros básicos
```

## 🎯 Erros que já cometi aqui

1. **Overloading dashboards:** Muita informação em uma tela só
2. **Cores inconsistentes:** Vermelho para positivo em um gráfico, verde em outro
3. **Queries lentas:** Não otimizei para performance desde o início
4. **Mobile ignorado:** Design apenas para desktop

---
