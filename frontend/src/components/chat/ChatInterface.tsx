import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { ChatMessage } from '@/types/api'
import { ChatBubble } from './ChatBubble'
import { ChatInput } from './ChatInput'

interface ChatInterfaceProps {
  className?: string
}

export function ChatInterface({ className = '' }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      type: 'assistant',
      content: 'Hello! I can help you query your CAD data. Upload a DWG file first, then ask me questions like "How many spaces are in the building?" or "Show me all wall segments".',
      timestamp: new Date(),
    }
  ])
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const queryMutation = useMutation({
    mutationFn: (question: string) => apiClient.sendSmartQuery({ question }),
    onSuccess: (response: any, question: string) => {
      // Add user message
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        type: 'user',
        content: question,
        timestamp: new Date(),
      }

      // Add assistant response
      // Handle smart query response format - keep it concise and objective
      let content = 'ℹ️ Consulta executada'
      // Preserve the full smart query response structure for Query Details
      let query_result = response
      
      // First, check if we have a formatted explanation from the backend
      if (response?.explanation && response.explanation.trim() && 
          response.explanation !== 'ℹ️ Consulta executada') {
        content = response.explanation
      } else if (response?.primary_result?.results && Array.isArray(response.primary_result.results) && response.primary_result.results.length > 0) {
        // Format smart query results for user
        const primaryResults = response.primary_result.results
        
        // Create a concise, objective response
        if (primaryResults.length === 1 && primaryResults[0] && typeof primaryResults[0] === 'object' && Object.keys(primaryResults[0]).length > 0) {
          const result = primaryResults[0]
          try {
            // Special formatting for scale information
            if (result.metadata_scales && typeof result.metadata_scales === 'object') {
              // Check alternative results for actual scale notations first
              const altResults = response?.alternative_results || []
              const scaleResults = altResults.find((alt: any) => 
                alt?.results && Array.isArray(alt.results) && alt.results.length > 0 &&
                alt.results.some((r: any) => r.exact_scale_notation)
              )
              
              if (scaleResults && scaleResults.results[0]?.exact_scale_notation) {
                const scaleNotation = scaleResults.results[0].exact_scale_notation
                const meaning = scaleResults.results[0].scale_meaning
                content = `📏 **${scaleNotation}**\n• ${meaning}`
              } else {
                // Fallback to metadata scales
                const scales = result.metadata_scales
                const mainScale = scales.dimscale || scales.ltscale || scales.cmlscale || scales.celtscale
                if (mainScale) {
                  content = `📏 **Escala do projeto: 1:${mainScale}**`
                  if (scales.dimscale && scales.dimscale !== mainScale) content += `\n• Dimensões: 1:${scales.dimscale}`
                  if (scales.ltscale && scales.ltscale !== mainScale) content += `\n• Linhas: 1:${scales.ltscale}`
                } else {
                  content = '📏 Informações de escala encontradas, mas valores não definidos.'
                }
              }
            } else if (result.types && Array.isArray(result.types)) {
              // For entity counts (legend queries)
              const typeLabel = result.types[0] || 'Unknown'
              const count = result.count || 0
              content = `📊 **${typeLabel}**: ${count} elementos`
            } else {
              // Generic formatting for other results - show key information only
              const keyEntries = Object.entries(result)
                .filter(([, value]) => value !== null && value !== undefined)
                .slice(0, 3) // Show only first 3 key fields
                .map(([key, value]) => {
                  if (typeof value === 'object') {
                    if (Array.isArray(value)) {
                      return `**${key}**: ${value.length} itens`
                    } else {
                      const objEntries = Object.entries(value || {})
                      if (objEntries.length <= 2) {
                        const readable = objEntries.map(([k, v]) => `${k}: ${v}`).join(', ')
                        return `**${key}**: ${readable}`
                      } else {
                        return `**${key}**: ${objEntries.length} propriedades`
                      }
                    }
                  }
                  return `**${key}**: ${value}`
                })
              content = keyEntries.length > 0 ? keyEntries.join('\n') : 'ℹ️ Informação encontrada'
            }
          } catch (error) {
            content = 'ℹ️ Informação encontrada (erro ao formatar detalhes)'
          }
        } else if (primaryResults.length > 1 && primaryResults[0]?.types) {
          // Multiple entity type results
          const entityTypes = primaryResults.map((r: any) => {
            const typeLabel = r.types[0] || 'Unknown'
            const count = r.count || 0
            return `${typeLabel}: ${count}`
          }).slice(0, 5)
          content = `📊 **Elementos no projeto:**\n• ${entityTypes.join('\n• ')}`
        } else {
          content = `ℹ️ **${primaryResults.length} resultado(s) encontrado(s)**`
        }
      } else {
        // No primary results, check alternative results for actual findings
        const altResults = response?.alternative_results || []
        const altWithResults = altResults.find((alt: any) => alt?.results && Array.isArray(alt.results) && alt.results.length > 0)
        
        if (altWithResults) {
          // For scale queries, show the actual scale found
          if (altWithResults.results[0]?.exact_scale_notation) {
            const scaleNotation = altWithResults.results[0].exact_scale_notation
            const meaning = altWithResults.results[0].scale_meaning
            content = `📏 **${scaleNotation}**\n• ${meaning}`
          } else if (altWithResults.results[0]?.a && altWithResults.results[0].a.text) {
            // For annotation-based results
            const annotations = altWithResults.results.map((r: any) => r.a?.text || r.text).filter(Boolean).slice(0, 3)
            content = `📝 **Encontrado:**\n• ${annotations.join('\n• ')}`
          } else if (altWithResults.results[0]?.types && Array.isArray(altWithResults.results[0].types)) {
            // For entity type results (legends query)
            const entityTypes = altWithResults.results.map((r: any) => {
              const typeLabel = r.types[0] || 'Unknown'
              const count = r.count || 0
              return `${typeLabel}: ${count}`
            }).slice(0, 5)
            content = `📊 **Elementos encontrados:**\n• ${entityTypes.join('\n• ')}`
          } else {
            content = `ℹ️ **${altWithResults.results.length} resultado(s) encontrado(s)**`
          }
        } else {
          content = '❌ Nenhuma informação encontrada para sua pergunta.'
        }
      }
      
      // Final fallback to explanation if we still have default content
      if (content === 'ℹ️ Consulta executada' && response?.explanation && response.explanation.trim()) {
        content = response.explanation
      }

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        type: 'assistant',
        content: content,
        timestamp: new Date(),
        query_result: query_result,
      }

      setMessages(prev => [...prev, userMessage, assistantMessage])
      setIsTyping(false)
    },
    onError: (error: Error, question: string) => {
      // Add user message
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        type: 'user',
        content: question,
        timestamp: new Date(),
      }

      // Add error message
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        type: 'assistant',
        content: `Sorry, I encountered an error: ${error.message}`,
        timestamp: new Date(),
      }

      setMessages(prev => [...prev, userMessage, errorMessage])
      setIsTyping(false)
    },
  })

  const handleSendMessage = async (message: string) => {
    if (!message.trim()) return

    setIsTyping(true)
    queryMutation.mutate(message)
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isTyping])

  return (
    <div className={`flex flex-col h-full bg-white rounded-lg shadow-sm border ${className}`}>
      {/* Header */}
      <div className="border-b border-gray-200 p-4">
        <h3 className="text-lg font-semibold text-gray-800">CAD Query Assistant</h3>
        <p className="text-sm text-gray-500">Ask questions about your uploaded CAD data</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <ChatBubble key={message.id} message={message} />
        ))}
        
        {isTyping && (
          <div className="flex items-center space-x-2">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
            </div>
            <span className="text-sm text-gray-500">Assistant is thinking...</span>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4">
        <ChatInput
          onSendMessage={handleSendMessage}
          disabled={queryMutation.isPending}
          placeholder="Ask about your CAD data..."
        />
      </div>
    </div>
  )
}