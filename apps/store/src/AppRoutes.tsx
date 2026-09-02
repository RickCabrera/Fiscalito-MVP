/**
 * Árbol de rutas de la app.
 *
 * POR QUÉ ESTÁ SEPARADO DE `main.tsx` (E-02)
 * ------------------------------------------
 * `main.tsx` llama a `createRoot` al importarse, así que no se puede montar en
 * jsdom: mientras las rutas vivieron ahí, **ningún test cubría que una ruta
 * estuviera registrada**. E-01 dejó ese hueco declarado al agregar
 * `/app/clientes`; esto lo cierra.
 *
 * El `BrowserRouter` se queda en `main.tsx` a propósito: así los tests montan
 * este componente dentro de un `MemoryRouter` y pueden entrar por cualquier
 * ruta sin tocar el historial del navegador.
 */

import { Routes, Route } from 'react-router-dom';
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
// DEMO E-02: cartera del despacho. Se borra en F2.
import ClientesPage from './pages/ClientesPage';
import ClienteDetallePage from './pages/ClienteDetallePage';
// DEMO D-07: se borra en F2 junto con la pantalla.
import NominaDemoPage from './pages/NominaDemoPage';

export default function AppRoutes() {
  return (
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
        {/* DEMO E-02 */}
        <Route path="clientes" element={<ClientesPage />} />
        <Route path="clientes/:id" element={<ClienteDetallePage />} />
        <Route path="store" element={<MarketplacePage />} />
        <Route path="store/fiscalito/use" element={<FiscalitoServicePage />} />
        <Route path="store/:serviceId" element={<ServiceDetailPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="admin" element={<AdminPage />} />
        {/* DEMO D-07: se borra en F2 */}
        <Route path="nomina-demo" element={<NominaDemoPage />} />
      </Route>
    </Routes>
  );
}
