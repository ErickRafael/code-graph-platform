import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { FileUploadProgress, UploadResponse } from '@/types/api'

interface FileUploadProps {
  onUploadComplete?: (response: UploadResponse) => void
  onUploadProgress?: (progress: FileUploadProgress) => void
  maxSize?: number
  accept?: Record<string, string[]>
  className?: string
}

export function FileUpload({
  onUploadComplete,
  onUploadProgress,
  maxSize = 50 * 1024 * 1024, // 50MB
  accept = {
    'application/acad': ['.dwg'],
    'image/vnd.dwg': ['.dwg'],
    'application/dxf': ['.dxf'],
  },
  className = '',
}: FileUploadProps) {
  const [uploadProgress, setUploadProgress] = useState<FileUploadProgress>({
    loaded: 0,
    total: 0,
    percentage: 0,
    stage: 'uploading',
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => {
      return apiClient.uploadFile(file, (percentage) => {
        const progress: FileUploadProgress = {
          loaded: (percentage / 100) * file.size,
          total: file.size,
          percentage,
          stage: percentage < 100 ? 'uploading' : 'extracting',
        }
        setUploadProgress(progress)
        onUploadProgress?.(progress)
      })
    },
    onSuccess: (response) => {
      setUploadProgress(prev => ({
        ...prev,
        percentage: 100,
        stage: 'completed',
      }))
      onUploadComplete?.(response)
    },
    onError: (error) => {
      setUploadProgress(prev => ({
        ...prev,
        stage: 'error',
      }))
      console.error('Upload failed:', error)
    },
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      uploadMutation.mutate(file)
    }
  }, [uploadMutation])

  const { 
    getRootProps, 
    getInputProps, 
    isDragActive,
    isDragAccept,
    isDragReject,
    fileRejections
  } = useDropzone({
    onDrop,
    maxSize,
    accept,
    multiple: false,
  })

  const getUploadAreaClass = () => {
    let baseClass = `upload-area ${className}`
    
    if (isDragActive) baseClass += ' drag-active'
    if (isDragAccept) baseClass += ' drag-accept'
    if (isDragReject) baseClass += ' drag-reject'
    
    return baseClass
  }

  const isUploading = uploadMutation.isPending
  const hasError = uploadMutation.isError || uploadProgress.stage === 'error'

  return (
    <div className="w-full max-w-md mx-auto">
      <div {...getRootProps()} className={getUploadAreaClass()}>
        <input {...getInputProps()} />
        
        {isUploading ? (
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-4 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
            <p className="text-lg font-medium text-gray-700">
              {uploadProgress.stage === 'uploading' && 'Uploading file...'}
              {uploadProgress.stage === 'extracting' && 'Extracting CAD data...'}
              {uploadProgress.stage === 'processing' && 'Processing entities...'}
            </p>
            <p className="text-sm text-gray-500 mt-2">
              {uploadProgress.percentage.toFixed(0)}%
            </p>
            <div className="w-full bg-gray-200 rounded-full h-2 mt-3">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress.percentage}%` }}
              ></div>
            </div>
          </div>
        ) : hasError ? (
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-4 text-red-500">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 18.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <p className="text-lg font-medium text-red-600">Upload failed</p>
            <p className="text-sm text-gray-500 mt-2">
              {uploadMutation.error?.message || 'Please try again'}
            </p>
          </div>
        ) : (
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-4 text-gray-400">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <p className="text-lg font-medium text-gray-700">
              {isDragActive ? 'Drop your file here' : 'Upload CAD Files'}
            </p>
            <p className="text-sm text-gray-500 mt-2">
              Drag & drop DWG/DXF files or click to browse
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Max file size: {(maxSize / 1024 / 1024).toFixed(0)}MB
            </p>
          </div>
        )}
      </div>

      {fileRejections.length > 0 && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-600 font-medium">File rejected:</p>
          {fileRejections.map(({ file, errors }) => (
            <div key={file.name} className="mt-1">
              <p className="text-xs text-red-500">{file.name}</p>
              {errors.map((error) => (
                <p key={error.code} className="text-xs text-red-400">
                  {error.message}
                </p>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}