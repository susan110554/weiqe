import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Templates from './pages/Templates';
import Cases from './pages/Cases';
import Messages from './pages/Messages';
import Broadcasts from './pages/Broadcasts';
import PDFTemplates from './pages/PDFTemplates';
import CaseDetail from './pages/CaseDetail';
import Users from './pages/Users';
import Agents from './pages/Agents';
import FeeConsole from './pages/FeeConsole';
import AuditLogs from './pages/AuditLogs';
import Blacklist from './pages/Blacklist';
import AdminManagement from './pages/AdminManagement';
import SystemSettings from './pages/SystemSettings';
import './App.css';

const isAuth = () => !!localStorage.getItem('access_token');

const Private = ({ children }) => isAuth() ? children : <Navigate to="/login" />;

function App() {
  return (
    <ConfigProvider theme={{ token: { colorPrimary: '#1890ff', borderRadius: 8 } }}>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={
            <Private>
              <Layout>
                <Routes>
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/templates" element={<Templates />} />
                  <Route path="/cases" element={<Cases />} />
                  <Route path="/cases/:caseId" element={<CaseDetail />} />
                  <Route path="/users" element={<Users />} />
                  <Route path="/agents" element={<Agents />} />
                  <Route path="/fee-console" element={<FeeConsole />} />
                  <Route path="/messages" element={<Messages />} />
                  <Route path="/broadcasts" element={<Broadcasts />} />
                  <Route path="/pdf-templates" element={<PDFTemplates />} />
                  <Route path="/audit-logs" element={<AuditLogs />} />
                  <Route path="/blacklist" element={<Blacklist />} />
                  <Route path="/admins" element={<AdminManagement />} />
                  <Route path="/system-settings" element={<SystemSettings />} />
                  <Route path="/" element={<Navigate to="/dashboard" />} />
                </Routes>
              </Layout>
            </Private>
          } />
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;
