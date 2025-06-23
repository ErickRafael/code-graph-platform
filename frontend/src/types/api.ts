// API Types for FastAPI integration

export interface UploadResponse {
  message: string
  file_path: string
  entities_extracted: number
  nodes_created: number
  relationships_created: number
}

export interface QueryRequest {
  question: string
}

export interface QueryResponse {
  cypher: string
  results: Array<Record<string, any>>
  summary?: string
}

export interface FileUploadProgress {
  loaded: number
  total: number
  percentage: number
  stage: 'uploading' | 'extracting' | 'processing' | 'completed' | 'error'
}

export interface ChatMessage {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: Date
  query_result?: QueryResponse
}

export interface GraphStats {
  nodes: number
  relationships: number
  node_types: string[]
  last_updated: string
}

export interface CADEntity {
  type: string
  layer: string
  properties: Record<string, any>
}

export interface ProcessingStatus {
  stage: 'idle' | 'uploading' | 'extracting' | 'transforming' | 'loading' | 'completed' | 'error'
  progress: number
  message: string
  error?: string
}