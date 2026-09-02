/**
 * Fiscalito Store — Entry point
 * Autor: Ricardo Cabrera
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProfileProvider } from './context/ProfileContext';
import { AgentProvider } from './agent/AgentContext';
import { ThemeProvider } from './context/ThemeContext';
import ProtectedRoute from './components/ProtectedRoute';
import AppLayout from './components/AppLayout';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import MarketplacePage from './pages/MarketplacePage';
import ServiceDetailPage from './pages/ServiceDetailPage';
import ProfilePage from './pages/ProfilePage';
import AdminPage from './pages/AdminPage';
import OnboardingWizard from './pages/OnboardingWizard';
import FiscalitoServicePage from './pages/FiscalitoServicePage';
import HistorialPage from './pages/HistorialPage';
// E-01: stub; E-02 la llena con los clientes del despacho.
import ClientesPage from './pages/ClientesPage';
// DEMO D-07: se borra en F2 junto con la pantalla.
import NominaDemoPage from './pages/NominaDemoPage';
import './styles/global.css';

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ProfileProvider>
          <AgentProvider>
            <BrowserRouter>
              <Routes>
                {/* Public */}
                <Route path="/" element={<LandingPage />} />
                <Route path="/login" element={<LoginPage />} />

                {/* Onboarding — protected but no sidebar */}
                <Route path="/app/onboarding" element={
                  <ProtectedRoute>
                    <OnboardingWizard />
                  </ProtectedRoute>
                } />

                {/* Protected — App */}
                <Route path="/app" element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }>
                  <Route index element={<DashboardPage />} />
                  <Route path="historial" element={<HistorialPage />} />
                  <Route path="clientes" element={<ClientesPage />} />
                  <Route path="store" element={<MarketplacePage />} />
                  <Route path="store/fiscalito/use" element={<FiscalitoServicePage />} />
                  <Route path="store/:serviceId" element={<ServiceDetailPage />} />
                  <Route path="profile" element={<ProfilePage />} />
                  <Route path="admin" element={<AdminPage />} />
                  {/* DEMO D-07: se borra en F2 */}
                  <Route path="nomina-demo" element={<NominaDemoPage />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </AgentProvider>
        </ProfileProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
