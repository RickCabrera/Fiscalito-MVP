/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Config de tests separada de vite.config.ts para no acoplar build y pruebas.
 * Lleva el plugin de react para que los tests con JSX (AgentContext) compilen.
 *
 * Ojo: duplica el plugin de vite.config.ts a proposito. Hoy no hay divergencia
 * porque el build no define aliases ni resolve; si alguna tarea agrega uno, hay
 * que replicarlo aqui o los tests resolveran distinto en silencio.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
