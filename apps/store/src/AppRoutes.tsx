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

import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import AppLayout from './components/AppLayout';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import MarketplacePage from './pages/MarketplacePage';
import ServiceDetailPage from './pages/ServiceDetailPage';
import ProfilePage from './pages/ProfilePage';
// T8: planes de la cuenta. Se entra desde Perfil, no desde el sidebar.
import PlanesPage from './pages/PlanesPage';
// P0-07: bitácora de auditoría. Se entra desde Perfil, no desde el sidebar.
import AuditoriaPage from './pages/AuditoriaPage';
import AdminPage from './pages/AdminPage';
import OnboardingWizard from './pages/OnboardingWizard';
import FiscalitoServicePage from './pages/FiscalitoServicePage';
// T7: cascarón de contabilidad electrónica. 100% front, no llama al API.
import ContabilitoPage from './pages/ContabilitoPage';
// DEMO E-02: cartera del despacho. Se borra en F2.
import ClientesPage from './pages/ClientesPage';
import ClienteDetallePage from './pages/ClienteDetallePage';
// DEMO E-03: la nómina vive dentro del cliente. Se borra en F2.
import NominaClientePage from './pages/NominaClientePage';
import NominaDelClienteActivo from './pages/NominaDelClienteActivo';
// R-05: empleados y dispositivos del cliente activo, entradas propias del sidebar.
import EmpleadosPage from './pages/EmpleadosPage';
import DispositivosPage from './pages/DispositivosPage';
// P0-03: bóveda de CFDI del cliente activo.
import BovedaPage from './pages/BovedaPage';
import CalculadorasPage from './pages/CalculadorasPage';
import DescargaSatPage from './pages/DescargaSatPage';
// P3-10: calendario unificado (fiscal + patronal + credenciales) y agenda del despacho.
import CalendarioPatronalPage from './pages/CalendarioPatronalPage';
// P3-09: alertas fiscales de la cartera (se entra por la campana del layout).
import AlertasPage from './pages/AlertasPage';
// P5-01/02/03: equipo del despacho, dashboard de entrada y cuentas por cobrar.
import InicioPage from './pages/InicioPage';
import EquipoPage from './pages/EquipoPage';
import CobranzaPage from './pages/CobranzaPage';
import AceptarInvitacionPage from './pages/AceptarInvitacionPage';
// P6-01: aviso de privacidad (LFPDPPP) y términos, públicos.
import AvisoPrivacidadPage from './pages/AvisoPrivacidadPage';
import TerminosPage from './pages/TerminosPage';

export default function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      {/* P5-01: el enlace del correo de invitación. Pública: pide sesión por dentro. */}
      <Route path="/aceptar-invitacion" element={<AceptarInvitacionPage />} />
      <Route path="/privacidad" element={<AvisoPrivacidadPage />} />
      <Route path="/terminos" element={<TerminosPage />} />

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
        {/* P5-02: `/app` entra al dashboard DEL DESPACHO (no el del contribuyente,
            que K retiró). La ruta vieja del historial se sigue redirigiendo. */}
        <Route index element={<Navigate to="/app/inicio" replace />} />
        <Route path="inicio" element={<InicioPage />} />
        <Route path="equipo" element={<EquipoPage />} />
        <Route path="cobranza" element={<CobranzaPage />} />
        <Route path="historial" element={<Navigate to="/app/clientes" replace />} />
        {/* DEMO E-02 */}
        <Route path="clientes" element={<ClientesPage />} />
        <Route path="clientes/:id" element={<ClienteDetallePage />} />
        <Route path="clientes/:id/nomina" element={<NominaClientePage />} />
        {/* Enlace del sidebar: no conoce el id, lo resuelve. */}
        <Route path="nomina" element={<NominaDelClienteActivo />} />
        {/* R-05: mismo patrón — resuelven el cliente activo, y sin cliente lo
            piden en vez de caer en un default silencioso. */}
        <Route path="empleados" element={<EmpleadosPage />} />
        <Route path="dispositivos" element={<DispositivosPage />} />
        <Route path="boveda" element={<BovedaPage />} />
        {/* P1-02: descarga masiva del SAT del cliente activo. */}
        <Route path="sat" element={<DescargaSatPage />} />
        {/* P3-10: vencimientos fiscales y patronales de la cartera + agenda semanal. */}
        <Route path="calendario" element={<CalendarioPatronalPage />} />
        <Route path="alertas" element={<AlertasPage />} />
        {/* P3-08: calculadoras fiscales sueltas del despacho (sin cliente). */}
        <Route path="calculadoras" element={<CalculadorasPage />} />
        <Route path="store" element={<MarketplacePage />} />
        <Route path="store/fiscalito/use" element={<FiscalitoServicePage />} />
        {/* T7. Va ANTES de `store/:serviceId` por legibilidad, no por necesidad:
            react-router v7 rankea por especificidad y un segmento literal le
            gana a uno dinámico, así que el orden de declaración no decide. */}
        <Route path="store/contabilito/use" element={<ContabilitoPage />} />
        <Route path="store/:serviceId" element={<ServiceDetailPage />} />
        <Route path="profile" element={<ProfilePage />} />
        {/* T8: no va en el sidebar. `getSidebarLinks` está congelado por
            `navigation.test.ts` con la lista exacta de cada perfil, y meter
            "Planes" entre las herramientas del despacho mueve su navegación
            diaria por una pantalla que se visita una vez. Se llega desde la
            tarjeta de plan del Perfil. */}
        <Route path="planes" element={<PlanesPage />} />
        <Route path="auditoria" element={<AuditoriaPage />} />
        <Route path="admin" element={<AdminPage />} />
        {/* La ruta de D-07 sobrevive como redirección: el runbook de la demo
            y los enlaces viejos apuntan ahí. */}
        <Route path="nomina-demo" element={<Navigate to="/app/nomina" replace />} />
      </Route>
    </Routes>
  );
}
