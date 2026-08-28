import { Routes, Route, useLocation } from 'react-router-dom'
import { WorkflowProvider } from './state/WorkflowContext'
import Sidebar from './components/Sidebar'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import UploadPage from './pages/UploadPage'
import AnalyzePage from './pages/AnalyzePage'
import PreviewPage from './pages/PreviewPage'
import ConversionPage from './pages/ConversionPage'
import HistoryPage from './pages/HistoryPage'
import SettingsPage from './pages/SettingsPage'

function Shell() {
  const location = useLocation()
  const isLanding = location.pathname === '/'

  if (isLanding) {
    return (
      <Routes>
        <Route path="/" element={<Landing />} />
      </Routes>
    )
  }

  return (
    <div className="flex h-full">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/preview" element={<PreviewPage />} />
          <Route path="/conversion" element={<ConversionPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <WorkflowProvider>
      <Shell />
    </WorkflowProvider>
  )
}
