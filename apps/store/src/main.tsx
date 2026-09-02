/**
 * Fiscalito Store — Entry point
 * Autor: Ricardo Cabrera
 *
 * Aquí sólo viven `createRoot`, los providers y el `BrowserRouter`. El árbol de
 * rutas está en `AppRoutes.tsx` para que sea montable en jsdom: este archivo no
 * lo es, porque `createRoot` corre al importarlo.
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProfileProvider } from './context/ProfileContext';
import { ClienteActivoProvider } from './context/ClienteActivoContext';
import { AgentProvider } from './agent/AgentContext';
import { ThemeProvider } from './context/ThemeContext';
import AppRoutes from './AppRoutes';
import './styles/global.css';

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ProfileProvider>
          {/* DEMO E-02: la cartera sólo se carga para un perfil de contador. */}
          <ClienteActivoProvider>
            <AgentProvider>
              <BrowserRouter>
                <AppRoutes />
              </BrowserRouter>
            </AgentProvider>
          </ClienteActivoProvider>
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
