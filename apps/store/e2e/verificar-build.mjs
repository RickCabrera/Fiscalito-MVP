// P6-04: el `dist/` de un build normal NO trae los dobles de Firebase del modo e2e.
//
// Se corre en CI después de `npm run build` (`node e2e/verificar-build.mjs`). Busca en
// los JS del bundle las marcas de `src/e2e/firebaseAppFalso.ts` y `firebaseAuthFalso.ts`;
// si alguna aparece, alguien compiló producción con `VITE_E2E=1` o importó los dobles a
// mano, y la app entregaría el uid como token en vez de un ID token de Firebase.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIST = fileURLToPath(new URL('../dist/', import.meta.url));
const MARCAS = ['FISCALITO_E2E_FIREBASE_FALSO', 'fiscalito_e2e_sesion', 'fiscalito_e2e_firestore'];

function archivos(dir) {
  return readdirSync(dir).flatMap((n) => {
    const ruta = join(dir, n);
    return statSync(ruta).isDirectory() ? archivos(ruta) : [ruta];
  });
}

let js;
try {
  js = archivos(DIST).filter((f) => f.endsWith('.js'));
} catch {
  console.error('No hay dist/: corre `npm run build` antes.');
  process.exit(2);
}
if (js.length === 0) {
  console.error('dist/ no tiene JS: el build no corrió.');
  process.exit(2);
}
const hallazgos = js.flatMap((f) => {
  const texto = readFileSync(f, 'utf8');
  return MARCAS.filter((m) => texto.includes(m)).map((m) => `${f}: ${m}`);
});
if (hallazgos.length) {
  console.error('El build de producción trae los dobles de Firebase del modo e2e:');
  for (const h of hallazgos) console.error(`  ${h}`);
  process.exit(1);
}
console.log(`dist/ limpio: ${js.length} archivo(s) JS sin los dobles e2e.`);
