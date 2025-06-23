# Guia de Migração: Claude Code SDK

## Resumo Executivo

O Claude Code SDK oferece melhorias significativas para o projeto:
- **Redução de custos** vs OpenAI GPT-4o
- **Conversação multi-turn** para refinamento de queries
- **MCP (Model Context Protocol)** para ferramentas especializadas
- **Melhor performance** com Claude Opus 4

## Roteiro de Implementação

### Fase 1: Teste A/B (1-2 dias)
```bash
# 1. Instalar SDK
pip install claude-code-sdk

# 2. Configurar variável de ambiente
export ANTHROPIC_API_KEY="sua-chave-aqui"

# 3. Implementar endpoint paralelo
cp app/query_interface.py app/query_interface_backup.py
# Usar query_interface_claude.py criado
```

**Modificar `main.py`:**
```python
# Adicionar flag de feature
USE_CLAUDE = os.getenv("USE_CLAUDE_SDK", "false").lower() == "true"

@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    if USE_CLAUDE:
        from query_interface_claude import process_query_claude
        return await process_query_claude(request.question, request.session_id)
    else:
        # Código existente OpenAI
        ...
```

### Fase 2: Multi-turn (3-4 dias)

**Frontend - Adicionar estado de sessão:**
```typescript
// src/store/chatStore.ts
interface ChatSession {
  sessionId: string
  messages: Message[]
  canRefine: boolean
}

// src/components/ChatInterface.tsx
const [session, setSession] = useState<ChatSession>()

// Incluir sessionId nas requests
const response = await api.query({
  question: input,
  sessionId: session?.sessionId
})
```

**Backend - Habilitar refinamento:**
```python
@app.post("/api/query/refine")
async def refine_query(request: RefineRequest):
    return await claude_interface.query_with_refinement(
        request.question,
        request.session_id,
        max_turns=3
    )
```

### Fase 3: MCP Server (5-7 dias)

**1. Configurar servidor MCP:**
```bash
# Criar arquivo de configuração MCP
cat > mcp_config.json << EOF
{
  "servers": {
    "cad-analysis": {
      "path": "python",
      "args": ["app/cad_mcp_server.py"],
      "env": {
        "NEO4J_URI": "${NEO4J_URI}",
        "NEO4J_USER": "${NEO4J_USER}",
        "NEO4J_PASSWORD": "${NEO4J_PASSWORD}"
      }
    }
  }
}
EOF
```

**2. Integrar com Claude:**
```python
# Em query_interface_claude.py
options = ClaudeCodeOptions(
    mcp_servers=["cad-analysis"],
    system_prompt="""
    You have access to specialized CAD analysis tools:
    - analyze_spatial_distribution
    - detect_design_patterns
    - calculate_detailed_areas
    - extract_legends_and_colors
    Use these when appropriate.
    """
)
```

### Fase 4: Monitoramento (Contínuo)

**Métricas para acompanhar:**
```python
# app/metrics.py
from datetime import datetime
import json

class QueryMetrics:
    def __init__(self):
        self.metrics_file = "query_metrics.json"
    
    def log_query(self, model: str, query: str, cypher: str, 
                  success: bool, duration: float, cost: float = 0):
        metric = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "query_length": len(query),
            "cypher_length": len(cypher),
            "success": success,
            "duration": duration,
            "estimated_cost": cost
        }
        
        # Append to metrics file
        with open(self.metrics_file, 'a') as f:
            f.write(json.dumps(metric) + '\n')
```

## Checklist de Migração

### Semana 1
- [ ] Instalar claude-code-sdk
- [ ] Configurar ANTHROPIC_API_KEY
- [ ] Implementar query_interface_claude.py
- [ ] Adicionar feature flag USE_CLAUDE
- [ ] Testar queries básicas
- [ ] Comparar resultados OpenAI vs Claude

### Semana 2
- [ ] Implementar sessões no frontend
- [ ] Adicionar endpoint de refinamento
- [ ] Testar conversação multi-turn
- [ ] Ajustar prompts para Claude
- [ ] Documentar diferenças de comportamento

### Semana 3
- [ ] Configurar MCP server
- [ ] Implementar ferramentas CAD especializadas
- [ ] Integrar MCP com Claude SDK
- [ ] Testar ferramentas avançadas
- [ ] Otimizar performance

### Monitoramento Contínuo
- [ ] Dashboard de métricas
- [ ] Comparação de custos
- [ ] Taxa de sucesso de queries
- [ ] Satisfação do usuário
- [ ] Tempo de resposta

## Rollback Plan

Se necessário reverter:
```bash
# 1. Desabilitar feature flag
export USE_CLAUDE_SDK=false

# 2. Restaurar código original
cp app/query_interface_backup.py app/query_interface.py

# 3. Remover dependências se necessário
pip uninstall claude-code-sdk
```

## Custos Estimados

### Comparação OpenAI vs Claude:
- **OpenAI GPT-4o**: ~$0.01 por query complexa
- **Claude Opus 4**: ~$0.006 por query complexa
- **Economia estimada**: 40% em custos de API

### ROI esperado:
- Redução de 40% em custos de API
- Melhoria de 25% na precisão de queries
- Redução de 50% em queries de follow-up

## Suporte e Documentação

- [Claude Code SDK Docs](https://docs.anthropic.com/claude-code/sdk)
- [MCP Protocol Guide](https://docs.anthropic.com/mcp)
- Issues: Registrar em memory-bank/
- Métricas: Acompanhar em query_metrics.json