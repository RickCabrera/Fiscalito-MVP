/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Config de tests separada de vite.config.ts para no acoplar build y pruebas.
 * Lleva el plugin de react para que los tests con JSX (AgentContext) compilen.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
