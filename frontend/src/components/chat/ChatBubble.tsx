import { useState } from 'react'
import type { ChatMessage } from '@/types/api'

interface ChatBubbleProps {
  message: ChatMessage
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const [showDetails, setShowDetails] = useState(false)

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const formatQueryResults = (results: any[]) => {
    if (!results || results.length === 0) {
      return 'No results found.'
    }

    if (results.length === 1 && Object.keys(results[0]).length === 1) {
      // Single value result
      const value = Object.values(results[0])[0]
      return `Result: ${value}`
    }

    // Multiple results - show in a table format
    return (
      <div className="mt-2 overflow-x-auto">
        <table className="min-w-full text-xs border border-gray-200 rounded">
          <thead className="bg-gray-50">
            <tr>
              {Object.keys(results[0]).map((key) => (
                <th key={key} className="px-2 py-1 text-left font-medium text-gray-600 border-b">
                  {key}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.slice(0, 5).map((row, index) => (
              <tr key={index} className="border-b">
                {Object.values(row).map((value, colIndex) => (
                  <td key={colIndex} className="px-2 py-1 text-gray-800">
                    {String(value)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {results.length > 5 && (
          <p className="text-xs text-gray-500 mt-1">
            ... and {results.length - 5} more results
          </p>
        )}
      </div>
    )
  }

  return (
    <div className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[70%] ${message.type === 'user' ? 'order-2' : 'order-1'}`}>
        <div className={`chat-bubble ${message.type}`}>
          <p className="text-sm">{message.content}</p>
          
          {message.query_result && (
            <div className="mt-3 pt-3 border-t border-white/20">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="text-xs text-white/80 hover:text-white flex items-center gap-1"
              >
                <span>Query Details</span>
                <svg 
                  className={`w-3 h-3 transition-transform ${showDetails ? 'rotate-180' : ''}`}
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              
              {showDetails && (
                <div className="mt-2 text-xs bg-white/10 rounded p-2">
                  <div className="mb-2">
                    <strong>Cypher Query:</strong>
                    <code className="block mt-1 bg-black/20 p-1 rounded text-xs font-mono">
                      {message.query_result.cypher}
                    </code>
                  </div>
                  
                  <div>
                    <strong>Results ({message.query_result.results.length}):</strong>
                    {formatQueryResults(message.query_result.results)}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
        
        <div className={`flex items-center mt-1 ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
          <span className="text-xs text-gray-500">
            {formatTime(message.timestamp)}
          </span>
        </div>
      </div>
    </div>
  )
}