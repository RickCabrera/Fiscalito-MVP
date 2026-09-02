/**
 * Ningún test puede depender de tener llaves de Firebase. (R-07)
 *
 * EL MODO DE FALLA QUE ESTO CIERRA
 * --------------------------------
 * `services/firebase.ts` llama a `getAuth(app)` **al importarse**, y sin
 * `VITE_FIREBASE_API_KEY` eso lanza `auth/invalid-api-key`. En local hay `.env`
 * y el archivo carga sin ruido; **en CI no hay secretos**, así que cualquier
 * test que lo importe —directa o transitivamente— revienta antes de su primer
 * `it`, y el error no se parece en nada a lo que se estaba probando.
 *
 * Pasó en R-07: `cartera.test.ts` importaba el despachador, que importa
 * `carteraBackend`, que importa `auth`. Local verde, CI rojo con un
 * `FirebaseError` que no menciona ninguno de los tres archivos.
 *
 * Es exactamente la clase de bug que la entrada de X-01 del `nocturno-log`
 * describe: **sólo aparece porque el test corre en un entorno distinto al
 * local**. Con las llaves presentes, dormiría.
 *
 * POR QUÉ SE PRUEBA ASÍ Y NO CONTANDO `vi.mock`
 * ---------------------------------------------
 * Un test que contara los `vi.mock('./firebase')` de la suite sería un test de
 * grep: pasaría con un mock puesto en un archivo que no lo necesita, y fallaría
 * cuando alguien lo escribiera con otra ruta relativa. Aquí se mide la causa
 * directa — que importar el módulo sin llaves lanza — para que quede escrito
 * por qué el doble hace falta.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => { vi.resetModules(); vi.unstubAllEnvs(); });

describe('services/firebase se inicializa al importarse', () => {
  it('sin API key, importarlo LANZA — por eso hay que doblarlo en los tests', async () => {
    vi.stubEnv('VITE_FIREBASE_API_KEY', '');
    vi.resetModules();

    await expect(import('./firebase')).rejects.toThrow();
  });

  it('los módulos que hablan con el backend arrastran esa dependencia', async () => {
    // `carteraBackend` necesita `auth.currentUser.getIdToken()`, así que importa
    // `./firebase`. Cualquier test que lo toque —o que toque el despachador—
    // tiene que doblarlo. Esto lo deja escrito donde alguien lo va a leer al
    // ver el CI rojo.
    vi.stubEnv('VITE_FIREBASE_API_KEY', '');
    vi.resetModules();

    await expect(import('./carteraBackend')).rejects.toThrow();
  });
});
