# Regras de Comportamento - Claude Code

## REGRA CRÍTICA: Proibição de Soluções Paliativas

### ❌ NUNCA FAZER:
- Criar fallbacks que mascarar problemas reais
- Implementar workarounds que ignoram a causa raiz
- Simular dados ou resultados falsos
- Substituir um sistema por outro sem entender o problema original
- Consolidar dados prematuramente causando perda de informação
- Assumir que "funciona parcialmente" é suficiente

### ✅ SEMPRE FAZER:
- Identificar e atacar a CAUSA RAIZ do problema
- Manter redundância verdadeira (sistemas complementares, não substitutos)
- Preservar dados originais de cada extrator separadamente
- Investigar profundamente quando algo não funciona como esperado
- Validar que soluções realmente resolvem o problema identificado
- Questionar por que algo não está funcionando ao invés de contornar


## Contexto do Projeto

Este é um sistema de análise de documentos DWG para extrair:
- Legendas e cores associadas
- Cálculos de área
- Data do projeto e escala
- Anotações técnicas
- Dados de infraestrutura aeroportuária


### Motor IA OpenAI GPT-4o:
- **API**: OpenAI GPT-4o (migrado do Mistral)
- **Schema Awareness**: Prompts baseados na estrutura real do Neo4j
- **Validação**: Queries Cypher com validação EXPLAIN
- **Zero Fallbacks**: Erros surfaced para investigação, não mascarados



## Gestão de Arquivos e Organização

### ❌ NUNCA:
- Manter arquivos de teste temporários após conclusão
- Duplicar arquivos ou criar versões desnecessárias
- Criar arquivos .md sem necessidade real
- Deixar dependências desatualizadas após mudanças no código
- Atualizar componentes sem consultar documentação oficial
- **SUBSTITUIR chaves API já configuradas por placeholders** (ex: "your_api_key_here")

### ✅ SEMPRE:
- **Consulta Context7**: ANTES de qualquer mudança de código, consultar mcp context7 para entender documentações atualizadas das stacks utilizadas
- **Limpeza Automática**: Excluir arquivos de teste (.json, .log temporários) após uso
- **Verificação de Dependências**: Após qualquer mudança de código, verificar se todas as dependencies estão atualizadas
- **Consulta Oficial**: Verificar documentação GitHub/oficial antes de atualizar componentes
- **Organização**: Manter estrutura de pastas limpa e sem duplicações
- **Documentação Útil**: Apenas criar .md quando realmente necessário para o projeto
- **Memory Bank**: Sempre atualizar memory-bank/ com evoluções importantes
- **README Atualizado**: Manter README.md sincronizado com mudanças do sistema

## Gestão de Tarefas Complexas

### REGRA OBRIGATÓRIA - Task-Master-AI:
Para qualquer tarefa complexa (3+ etapas ou modificações em múltiplos arquivos):

1. **ANTES DE INICIAR**: Criar tasks no TaskMaster-AI
2. **DURANTE EXECUÇÃO**: Consultar TaskMaster-AI para verificar progresso
3. **APÓS CONCLUSÃO**: Atualizar status das tasks no TaskMaster-AI
4. **VERIFICAÇÃO**: Sempre checar o que ainda falta executar

### Como Usar TaskMaster-AI:
```bash
# Criar nova task
echo "FASE X.Y: Descrição da tarefa" >> .taskmaster/current_tasks.md

# Verificar status
cat .taskmaster/current_tasks.md

# Atualizar progresso
# [Editar arquivo com status: pending/in_progress/completed]
```

### Exemplo de Task Complexa:
```
❌ ERRADO: Começar a modificar código direto
✅ CORRETO:
1. Consultar Context7 sobre as tecnologias envolvidas
2. Criar tasks no TaskMaster-AI
3. Consultar documentação oficial do componente
4. Verificar dependências atuais
5. Executar mudanças
6. Verificar dependencies pós-mudança
7. Limpar arquivos temporários
8. Atualizar memory-bank e README
9. Marcar tasks como completed
```

### Context7 - Documentação das Stacks:
Use `mcp context7` para consultar documentações atualizadas sobre:


## Fluxo de Trabalho Padrão

### Início de Tarefa:
1. **Consultar Context7**: Verificar documentações atualizadas das tecnologias envolvidas
2. Consultar TodoRead para ver pending tasks
3. Se tarefa complexa → criar no TaskMaster-AI
4. Verificar documentação oficial se aplicável

### Durante Execução:
1. **Consultar Context7** sempre que precisar entender melhor uma tecnologia
2. Manter organização de arquivos
3. Não criar duplicações desnecessárias
4. Verificar dependencies após mudanças

### Finalização:
1. Limpar arquivos temporários/teste
2. Atualizar memory-bank com evoluções
3. Atualizar README se necessário
4. Marcar tasks como completed
5. Verificar TaskMaster-AI para próximos passos