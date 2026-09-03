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
// DEMO E-03: la nómina vive dentro del cliente. Se borra en F2.
import NominaClientePage from './pages/NominaClientePage';
import NominaDelClienteActivo from './pages/NominaDelClienteActivo';
// R-05: empleados y dispositivos del cliente activo, entradas propias del sidebar.
import EmpleadosPage from './pages/EmpleadosPage';
import DispositivosPage from './pages/DispositivosPage';
// DEMO E-07: calendario patronal de la cartera. Se borra en F2.
import CalendarioPatronalPage from './pages/CalendarioPatronalPage';
import { ID_EMPRESA, modoEmpresaUnica } from './services/modoEmpresa';

/**
 * Las rutas de la cartera (O-01).
 *
 * En modo empresa única **no se borran: dejan de montarse**. Las tres redirigen
 * a la nómina de la empresa, que es lo único que hay. Los componentes siguen
 * importados y probados para el modo despacho — apagar no es borrar.
 *
 * `/app/nomina` cambia de significado según el modo, y por eso está aquí y no
 * suelto entre las demás:
 *
 * - **Despacho**: `NominaDelClienteActivo`, que resuelve el cliente en foco y
 *   redirige a `/app/clientes/{id}/nomina`.
 * - **Empresa única**: la pantalla de nómina **directa**, con el id implícito.
 *   Sin el salto intermedio: no hay cliente que resolver, y una redirección a
 *   una ruta que a su vez redirige de vuelta sería un ciclo.
 */
function RutasDeCartera() {
  if (modoEmpresaUnica()) {
    const aLaNomina = <Navigate to="/app/nomina" replace />;
    return (
      <>
        <Route path="clientes" element={aLaNomina} />
        <Route path="clientes/:id" element={aLaNomina} />
        <Route path="clientes/:id/nomina" element={aLaNomina} />
        <Route path="nomina" element={<NominaClientePage clienteId={ID_EMPRESA} />} />
      </>
    );
  }
  return (
    <>
      {/* DEMO E-02 */}
      <Route path="clientes" element={<ClientesPage />} />
      <Route path="clientes/:id" element={<ClienteDetallePage />} />
      <Route path="clientes/:id/nomina" element={<NominaClientePage />} />
      {/* Enlace del sidebar del contador: no conoce el id, lo resuelve. */}
      <Route path="nomina" element={<NominaDelClienteActivo />} />
    </>
  );
}

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
        {/* Se INVOCA, no se monta como `<RutasDeCartera />`.
            `createRoutesFromChildren` de react-router sólo entiende `<Route>` y
            `React.Fragment` entre los hijos de `<Routes>`: un componente propio
            que devuelva rutas se descarta en silencio y las rutas simplemente
            no existirían — 404 sin un solo error. Llamarla devuelve el fragmento
            directo, que sí sabe recorrer. */}
        {RutasDeCartera()}
        {/* R-05: mismo patrón — resuelven el cliente activo, y sin cliente lo
            piden en vez de caer en un default silencioso. */}
        <Route path="empleados" element={<EmpleadosPage />} />
        <Route path="dispositivos" element={<DispositivosPage />} />
        {/* DEMO E-07: obligaciones patronales de los clientes del despacho. */}
        <Route path="calendario" element={<CalendarioPatronalPage />} />
        <Route path="store" element={<MarketplacePage />} />
        <Route path="store/fiscalito/use" element={<FiscalitoServicePage />} />
        <Route path="store/:serviceId" element={<ServiceDetailPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="admin" element={<AdminPage />} />
        {/* La ruta de D-07 sobrevive como redirección: el runbook de la demo
            y los enlaces viejos apuntan ahí. En modo empresa única el destino
            no puede ser el cliente `demo` —no existe— y va a la nómina de la
            empresa; si no, el enlace viejo caería en la redirección de
            `clientes/:id/nomina` y daría dos saltos para llegar al mismo sitio. */}
        <Route
          path="nomina-demo"
          element={
            <Navigate
              to={modoEmpresaUnica() ? '/app/nomina' : '/app/clientes/demo/nomina'}
              replace
            />
          }
        />
      </Route>
    </Routes>
  );
}
