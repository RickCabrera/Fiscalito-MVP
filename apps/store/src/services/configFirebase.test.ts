/**
 * `firebase.json` publica las reglas de Firestore. (R-01)
 *
 * POR QUÉ EXISTE
 * --------------
 * Hasta R-01, `firebase.json` **no tenía bloque `firestore`**, así que
 * `firebase deploy` publicaba sólo el sitio y las reglas versionadas nunca
 * llegaban al proyecto. El costo real de eso, medido el 2026-09-02: las reglas
 * vivas cubrían `users/{uid}` y `users/{uid}/declaraciones/**`, y **nada más**.
 * Como las reglas de Firestore no heredan hacia subcolecciones, todo
 * `users/{uid}/clientes/**` —la cartera, con el salario y el NSS de los
 * trabajadores de los clientes— estaba **denegado**, y la app caía siempre al
 * catálogo de demostración. Es decir: la ausencia de tres líneas en un JSON era
 * la causa raíz de que G-03 no cumpliera su criterio.
 *
 * Nadie lo notó durante tres tareas porque **el modo de falla es silencioso**:
 * el deploy sale verde, publica el sitio, y no menciona lo que no publicó.
 * Este test es lo que hace ruidoso ese silencio.
 *
 * LA MUTACIÓN QUE TIENE QUE MATAR, Y POR QUÉ NO ES LA OBVIA
 * ---------------------------------------------------------
 * La comprobación ingenua —"el valor de `rules` apunta a un archivo que
 * existe"— **no sirve**, y vale la pena entender por qué antes de simplificar
 * este archivo. El Firebase CLI resuelve esa ruta **relativa al directorio que
 * contiene `firebase.json`** (o sea `apps/store/`), y además **rechaza** toda
 * ruta que se salga de él:
 *
 *     Error: ../../firestore.rules is outside of project directory
 *
 * Ese error es real: es exactamente el que produjo el primer intento de R-01,
 * con las reglas todavía en la raíz del repo. Pero un test que resolviera la
 * ruta desde la raíz habría encontrado el archivo y habría pasado **verde con
 * el deploy roto**, porque en la raíz sí existía un `firestore.rules`.
 *
 * Por eso aquí se resuelve como lo hace el CLI y se exige que el resultado
 * quede **dentro** de `apps/store/`. Las dos mutaciones que mata:
 *   1. borrar el bloque `firestore` (se vuelve al agujero original);
 *   2. cambiar `"firestore.rules"` por `"../../firestore.rules"` (el deploy
 *      muere, aunque el archivo exista donde apunta).
 */

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, isAbsolute, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/** `apps/store/`, que es el directorio del proyecto para el Firebase CLI. */
const RAIZ_DEL_PROYECTO = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

function leerFirebaseJson(): { firestore?: { rules?: string } } {
  return JSON.parse(readFileSync(resolve(RAIZ_DEL_PROYECTO, 'firebase.json'), 'utf8'));
}

describe('firebase.json publica las reglas de Firestore', () => {
  it('declara el bloque `firestore` con su archivo de reglas', () => {
    const config = leerFirebaseJson();

    expect(
      config.firestore,
      'Sin bloque `firestore`, `firebase deploy` publica el sitio y NO las reglas, ' +
        'en silencio. Es lo que dejó `users/{uid}/clientes/**` denegado hasta R-01.',
    ).toBeDefined();
    expect(typeof config.firestore?.rules).toBe('string');
  });

  it('la ruta de las reglas queda DENTRO de apps/store, como exige el CLI', () => {
    const declarada = leerFirebaseJson().firestore?.rules as string;

    // Se resuelve igual que el CLI: relativa al directorio de `firebase.json`.
    const absoluta = resolve(RAIZ_DEL_PROYECTO, declarada);
    const desdeLaRaiz = relative(RAIZ_DEL_PROYECTO, absoluta);

    expect(
      desdeLaRaiz.startsWith('..') || isAbsolute(declarada),
      `firebase.json apunta a "${declarada}", que sale de apps/store/. El Firebase CLI ` +
        'lo rechaza con "is outside of project directory" y el deploy de reglas falla. ' +
        'Las reglas tienen que vivir dentro de apps/store/.',
    ).toBe(false);

    // Y el archivo existe donde el CLI lo va a buscar.
    expect(() => readFileSync(absoluta, 'utf8')).not.toThrow();
  });

  it('el archivo de reglas es el que protege la cartera por uid', () => {
    const declarada = leerFirebaseJson().firestore?.rules as string;
    const reglas = readFileSync(resolve(RAIZ_DEL_PROYECTO, declarada), 'utf8');
    // Sin comentarios: el encabezado de ese archivo cita reglas VIEJAS como
    // registro histórico, y buscarlas en el texto crudo daría un falso verde.
    const efectivas = reglas
      .split('\n')
      .filter((linea) => !linea.trim().startsWith('//'))
      .join('\n');

    // No se compara el archivo entero —eso sería un test de copiar y pegar que
    // hay que actualizar cada vez—, sino las dos propiedades de las que cuelga
    // el multi-tenant: que la cartera esté cubierta y que el resto esté negado.
    expect(efectivas).toContain('match /users/{uid}/{document=**}');
    expect(efectivas).toContain('request.auth.uid == uid');
    expect(efectivas).toMatch(/match \/\{document=\*\*\} \{\s*allow read, write: if false;/);
  });
});
