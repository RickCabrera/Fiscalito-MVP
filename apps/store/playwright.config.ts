/**
 * Pruebas de punta a punta (P6-04): `npm run e2e`.
 *
 * Levanta dos servidores y corre `e2e/*.spec.ts` en Chromium:
 * - API: `e2e/levantar.sh` (uvicorn + worker, SQLite temporal, adaptadores `falso`).
 * - Front: Vite con `VITE_E2E=1` (Firebase sustituido por `src/e2e/*Falso.ts`).
 *
 * Variables: `PYTHON` (intérprete con las dependencias de `apps/api`; default `python`),
 * `PW_CHROMIUM` (binario de Chromium ya instalado, para no descargar navegadores).
 */
import { defineConfig, devices } from '@playwright/test';

const PUERTO_API = 8765;
const PUERTO_FRONT = 4321;
const API = `http://127.0.0.1:${PUERTO_API}`;

export default defineConfig({
  testDir: './e2e',
  testMatch: '*.spec.ts',
  // El recorrido es UNA historia con estado (un despacho que avanza); no se paraleliza.
  fullyParallel: false,
  workers: 1,
  timeout: 5 * 60_000,
  expect: { timeout: 20_000 },
  // Sin reintentos: el recorrido deja estado en la base (despacho, cliente), y un segundo
  // intento contra la misma API fallaría por otra razón que la original.
  retries: 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PUERTO_FRONT}`,
    actionTimeout: 30_000,
    navigationTimeout: 30_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'es-MX',
    timezoneId: 'America/Mexico_City',
    launchOptions: process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'bash e2e/levantar.sh',
      url: `${API}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      stdout: 'pipe',
      stderr: 'pipe',
      env: { E2E_PUERTO_API: String(PUERTO_API) },
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${PUERTO_FRONT} --strictPort`,
      url: `http://127.0.0.1:${PUERTO_FRONT}`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: { VITE_E2E: '1', VITE_FISCAL_AGENT_URL: API },
    },
  ],
});
