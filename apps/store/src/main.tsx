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
import { CarteraProvider } from './context/CarteraContext';
import { AgentProvider } from './agent/AgentContext';
import { ThemeProvider } from './context/ThemeContext';
import AppRoutes from './AppRoutes';
import './styles/global.css';

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ProfileProvider>
          {/* R-06: LA CARTERA VA POR FUERA. El orden estaba al revés porque el
              selector del header leía el catálogo del backend por su cuenta;
              ahora `ClienteActivoProvider` deriva sus resúmenes de la cartera,
              así que tiene que estar dentro o el hook revienta. Un solo origen
              para "qué clientes existen". */}
          <CarteraProvider>
            <ClienteActivoProvider>
              <AgentProvider>
                <BrowserRouter>
                  <AppRoutes />
                </BrowserRouter>
              </AgentProvider>
            </ClienteActivoProvider>
          </CarteraProvider>
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
