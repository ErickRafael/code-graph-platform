import { useState } from 'react'
import type { ChatMessage, SmartQueryResponse } from '@/types/api'

interface ChatBubbleProps {
  message: ChatMessage
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const [showDetails, setShowDetails] = useState(false)

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  // Type guard to check if query_result is SmartQueryResponse
  const isSmartQueryResponse = (result: any): result is SmartQueryResponse => {
    return result && (result.primary_result || result.alternative_results)
  }

  const formatQueryResults = (results: any[]) => {
    if (!results || results.length === 0) {
      return 'No results found.'
    }

    // Check if first result exists and is an object
    if (!results[0] || typeof results[0] !== 'object') {
      return 'Invalid results format.'
    }

    if (results.length === 1 && Object.keys(results[0]).length === 1) {
      // Single value result
      const value = Object.values(results[0])[0]
      return `Result: ${value}`
    }

    // Multiple results - show in a table format
    const firstRow = results[0]
    const keys = Object.keys(firstRow)
    
    if (keys.length === 0) {
      return 'Empty results.'
    }

    return (
      <div className="mt-2 overflow-x-auto">
        <table className="min-w-full text-xs border border-gray-200 rounded">
          <thead className="bg-gray-50">
            <tr>
              {keys.map((key) => (
                <th key={key} className="px-2 py-1 text-left font-medium text-gray-600 border-b">
                  {key}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.slice(0, 5).map((row, index) => (
              <tr key={index} className="border-b">
                {keys.map((key, colIndex) => (
                  <td key={colIndex} className="px-2 py-1 text-gray-800">
                    {row && row[key] !== null && row[key] !== undefined 
                      ? (typeof row[key] === 'object' 
                          ? JSON.stringify(row[key]) 
                          : String(row[key]))
                      : 'N/A'
                    }
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
          <div className="text-sm whitespace-pre-line">{message.content}</div>
          
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
                  {/* Handle primary result */}
                  {isSmartQueryResponse(message.query_result) && message.query_result.primary_result && (
                    <div className="mb-2">
                      <strong>Primary Query:</strong>
                      {message.query_result.primary_result.cypher && (
                        <code className="block mt-1 bg-black/20 p-1 rounded text-xs font-mono">
                          {message.query_result.primary_result.cypher}
                        </code>
                      )}
                      <div className="mt-1">
                        <strong>Results ({(message.query_result.primary_result.results && Array.isArray(message.query_result.primary_result.results)) ? message.query_result.primary_result.results.length : 0}):</strong>
                        {formatQueryResults((message.query_result.primary_result.results && Array.isArray(message.query_result.primary_result.results)) ? message.query_result.primary_result.results : [])}
                      </div>
                    </div>
                  )}
                  
                  {/* Handle alternative results */}
                  {isSmartQueryResponse(message.query_result) && message.query_result.alternative_results && message.query_result.alternative_results.length > 0 && (
                    <div className="mt-2">
                      <strong>Alternative Queries:</strong>
                      {message.query_result.alternative_results.map((alt: any, index: number) => (
                        <div key={index} className="mt-2 pl-2 border-l border-white/20">
                          <div className="text-white/70 text-xs">{alt.description || `Alternative ${index + 1}`}</div>
                          {alt.cypher && (
                            <code className="block mt-1 bg-black/20 p-1 rounded text-xs font-mono">
                              {alt.cypher}
                            </code>
                          )}
                          <div className="mt-1">
                            <strong>Results ({(alt.results && Array.isArray(alt.results)) ? alt.results.length : 0}):</strong>
                            {formatQueryResults((alt.results && Array.isArray(alt.results)) ? alt.results : [])}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* Fallback for old query_result format */}
                  {message.query_result.cypher && !isSmartQueryResponse(message.query_result) && (
                    <div className="mb-2">
                      <strong>Cypher Query:</strong>
                      <code className="block mt-1 bg-black/20 p-1 rounded text-xs font-mono">
                        {message.query_result.cypher}
                      </code>
                      <div className="mt-1">
                        <strong>Results ({(message.query_result.results && Array.isArray(message.query_result.results)) ? message.query_result.results.length : 0}):</strong>
                        {formatQueryResults((message.query_result.results && Array.isArray(message.query_result.results)) ? message.query_result.results : [])}
                      </div>
                    </div>
                  )}
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