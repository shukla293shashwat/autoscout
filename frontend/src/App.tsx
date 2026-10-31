import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Toasts } from './components/ui'
import { DiscoveryPage } from './pages/DiscoveryPage'
import { ImpactPage } from './pages/ImpactPage'
import { UploadPage } from './pages/UploadPage'
import { WorkflowDetailPage } from './pages/WorkflowDetailPage'
import { SessionProvider, ToastProvider } from './store'

export default function App() {
  return (
    <SessionProvider>
      <ToastProvider>
        <BrowserRouter>
          <Layout>
            <Routes>
              <Route path="/" element={<UploadPage />} />
              <Route path="/discovery" element={<DiscoveryPage />} />
              <Route path="/workflow/:id" element={<WorkflowDetailPage />} />
              <Route path="/impact" element={<ImpactPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
          <Toasts />
        </BrowserRouter>
      </ToastProvider>
    </SessionProvider>
  )
}
