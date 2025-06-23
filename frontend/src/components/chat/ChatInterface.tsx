import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { ChatMessage, QueryResponse } from '@/types/api'
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
    mutationFn: (question: string) => apiClient.sendQuery({ question }),
    onSuccess: (response: QueryResponse, question: string) => {
      // Add user message
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        type: 'user',
        content: question,
        timestamp: new Date(),
      }

      // Add assistant response
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        type: 'assistant',
        content: response.summary || 'Query executed successfully.',
        timestamp: new Date(),
        query_result: response,
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