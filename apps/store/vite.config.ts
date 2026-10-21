import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { aliasesE2E } from './src/e2e/aliasesE2E'

// P6-04: con VITE_E2E=1 el SDK de Firebase se cambia por los dobles de `src/e2e/`
// (Playwright, sin red). Sin la variable la lista de alias va vacía: el build normal
// no los conoce. Ver `src/e2e/aliasesE2E.ts`.
const CARPETA_E2E = fileURLToPath(new URL('./src/e2e/', import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: { alias: aliasesE2E(process.env.VITE_E2E, CARPETA_E2E) },
  server: { port: 3000 },
  build: { outDir: 'dist' }
})
