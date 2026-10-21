/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Config de tests separada de vite.config.ts para no acoplar build y pruebas.
 * Lleva el plugin de react para que los tests con JSX (AgentContext) compilen.
 *
 * Ojo: duplica el plugin de vite.config.ts a proposito. El build sólo define alias en
 * modo e2e (P6-04, `VITE_E2E=1`), y esos NO se replican aqui: vitest dobla Firebase con
 * `vi.mock` (`src/test/setup.ts`). Si alguna tarea agrega un alias de build normal, hay
 * que replicarlo aqui o los tests resolveran distinto en silencio.
 *
 * `e2e/` son specs de Playwright (`npm run e2e`): vitest no los recoge.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
  },
});
