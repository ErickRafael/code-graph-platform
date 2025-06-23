
interface SidebarProps {
  className?: string
}

export function Sidebar({ className = '' }: SidebarProps) {
  const navigationItems = [
    { 
      name: 'Upload Files', 
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      ),
      active: true 
    },
    { 
      name: 'Query Data', 
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      ),
      active: false 
    },
    { 
      name: 'Graph Viewer', 
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      ),
      active: false 
    },
    { 
      name: 'Statistics', 
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
      active: false 
    },
  ]

  const recentFiles = [
    { name: 'SBBI-GRL-010-3000-00.dwg', uploadedAt: '2 hours ago', status: 'processed' },
    { name: 'SBBI-GRL-010-3003-00.dwg', uploadedAt: '1 day ago', status: 'processed' },
    { name: 'SBBI-GRL-010-3004-00.dwg', uploadedAt: '2 days ago', status: 'error' },
  ]

  return (
    <aside className={`bg-white border-r border-gray-200 ${className}`}>
      <div className="p-6">
        {/* Navigation */}
        <nav className="space-y-2">
          {navigationItems.map((item) => (
            <button
              key={item.name}
              className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-left transition-colors ${
                item.active 
                  ? 'bg-blue-50 text-blue-700 border border-blue-200' 
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              {item.icon}
              <span className="font-medium">{item.name}</span>
            </button>
          ))}
        </nav>

        {/* Recent Files */}
        <div className="mt-8">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Recent Files</h3>
          <div className="space-y-2">
            {recentFiles.map((file) => (
              <div key={file.name} className="p-3 bg-gray-50 rounded-lg">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {file.name}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {file.uploadedAt}
                    </p>
                  </div>
                  <div className={`flex-shrink-0 ml-2 ${
                    file.status === 'processed' 
                      ? 'text-green-500' 
                      : file.status === 'error' 
                      ? 'text-red-500' 
                      : 'text-yellow-500'
                  }`}>
                    {file.status === 'processed' && (
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                    )}
                    {file.status === 'error' && (
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                      </svg>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Graph Stats */}
        <div className="mt-8 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-100">
          <h3 className="text-sm font-semibold text-gray-900 mb-2">Current Graph</h3>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Nodes:</span>
              <span className="font-medium text-gray-900">1,639</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Relationships:</span>
              <span className="font-medium text-gray-900">1,638</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Entities:</span>
              <span className="font-medium text-gray-900">58,258</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}