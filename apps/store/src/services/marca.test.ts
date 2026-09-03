/**
 * "Ninguna pantalla dice Fiscalito" — el criterio de O-02, medido. (O-02)
 *
 * QUÉ MIDE Y QUÉ NO: LEE ESTO ANTES DE CONFIAR EN ÉL
 * ---------------------------------------------------
 * Esto es un test de **forma**, no de píxeles: recorre el código fuente y busca
 * la marca vieja en posiciones donde acabaría siendo texto visible. No monta una
 * sola pantalla, así que **no prueba que la pantalla se vea bien**; prueba que
 * la cadena no está donde no debe.
 *
 * El `nocturno-log` de R-07 ya dejó anotado el límite de esta clase de prueba:
 * *"un test de grep mide la forma y no la causa"*. Se acepta a sabiendas por dos
 * razones concretas:
 *
 * 1. El criterio de O-02 **es** una afirmación negativa sobre todo el árbol
 *    ("ninguna pantalla"), y montar las 15 pantallas para leer su texto sería
 *    más frágil y mucho más lento que leerlas en el fuente.
 * 2. Lo que de verdad protege es el **rebrand siguiente**: si alguien mete
 *    "Orca" a mano en una pantalla nueva en vez de importar la constante, el
 *    cambio de nombre volverá a ser cuarenta cadenas repartidas.
 *
 * LA LISTA DE PERMITIDOS ES EL PUNTO DÉBIL, Y HAY QUE VIGILARLA
 * -------------------------------------------------------------
 * Si crece, este test se vuelve decorativo. Por eso los permitidos son
 * **patrones de identificador**, no rutas de archivo: se permite `TabFiscalito`
 * como nombre de tipo en cualquier lado, no "todo lo que haya en tools.ts". Un
 * archivo entero exento sería exactamente la puerta por donde vuelve la marca.
 */

import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { MARCA, MARCA_CORTA, MARCA_LOGO_1, MARCA_LOGO_2, ASISTENTE, PREFIJO_ARCHIVO } from './marca';

/**
 * `src/`, resuelto con `fileURLToPath` y no con `.pathname`.
 *
 * En Windows `new URL(...).pathname` devuelve `/C:/...` con la barra de más, y
 * `join` acababa buscando en `C:\`. El primer intento de este archivo **pasaba
 * en vacío** por eso: recorría cero archivos y no encontraba nada que reportar.
 * Por eso abajo hay una cota inferior de archivos recorridos.
 */
const SRC = dirname(dirname(fileURLToPath(import.meta.url)));

/**
 * Nombres INTERNOS con la marca vieja, que la tarea prohíbe tocar.
 *
 * Rutas guardadas en enlaces, ids de Firestore, llaves de `localStorage`,
 * nombres de archivo y de tipo. Renombrarlos rompe sesiones y documentos ya
 * escritos a cambio de nada: nadie los ve.
 */
const INTERNOS_PERMITIDOS = [
  /TabFiscalito/g,
  /FiscalitoVoiceChat/g,
  /FiscalitoServicePage/g,
  /fiscalito\/use/g,
  /fiscalito_/g, // llaves de localStorage: fiscalito_profile, fiscalito_cliente_activo
  /id: 'fiscalito'/g,
];

/**
 * Lo que queda de la línea después de tachar los nombres internos permitidos.
 *
 * SE TACHAN, NO SE PERDONA LA LÍNEA ENTERA. La primera versión descartaba
 * cualquier línea que casara con un permitido, y eso dejó pasar el caso que más
 * importaba:
 *
 *     { id: 'fiscalito', to: '/app/store/fiscalito/use', label: 'Fiscalito' },
 *
 * La ruta interna excusaba a la **etiqueta del sidebar**, que es texto que un
 * contribuyente lee en pantalla. El criterio de O-02 es "ninguna pantalla dice
 * Fiscalito", y esa lo decía.
 */
function sinNombresInternos(linea: string): string {
  return INTERNOS_PERMITIDOS.reduce((acc, patron) => acc.replace(patron, ''), linea);
}

function archivosFuente(dir: string, acc: string[] = []): string[] {
  for (const entrada of readdirSync(dir)) {
    const ruta = join(dir, entrada);
    if (statSync(ruta).isDirectory()) {
      archivosFuente(ruta, acc);
    } else if (/\.tsx?$/.test(entrada) && !/\.test\.tsx?$/.test(entrada)) {
      acc.push(ruta);
    }
  }
  return acc;
}

/**
 * Quita comentarios: un comentario no es una pantalla.
 *
 * Se hace **línea por línea**, llevando el estado de "voy dentro de un bloque".
 * La primera versión aplicaba un `replace` global de bloques sobre el fuente
 * entero y luego partía en líneas: eso **cambia el número de líneas** cuando un
 * comentario abarca varias, así que los renglones reportados dejaban de
 * corresponder al archivo. Un hallazgo con la línea equivocada es peor que
 * ninguno, porque manda a leer otra cosa.
 */
function sinComentarios(fuente: string): string[] {
  let enBloque = false;
  return fuente.split('\n').map((original) => {
    let l = original;
    if (enBloque) {
      const cierre = l.indexOf('*/');
      if (cierre === -1) return '';
      enBloque = false;
      l = l.slice(cierre + 2);
    }
    l = l.replace(/\/\*.*?\*\//g, '');
    const apertura = l.indexOf('/*');
    if (apertura !== -1) {
      enBloque = true;
      l = l.slice(0, apertura);
    }
    const linea = l.indexOf('//');
    return linea === -1 ? l : l.slice(0, linea);
  });
}

describe('la marca vieja no queda en ningún texto visible', () => {
  it('ni "Fiscalito" ni "Fiscalito Store" fuera de los nombres internos', () => {
    const hallazgos: string[] = [];

    const fuentes = archivosFuente(SRC);
    // LA COTA QUE IMPIDE EL VERDE VACÍO. Sin ella, una ruta mal resuelta —o un
    // filtro de más— deja este test afirmando que no hay ocurrencias porque no
    // leyó ni un archivo. Ya pasó una vez.
    expect(fuentes.length).toBeGreaterThan(80);

    for (const ruta of fuentes) {
      sinComentarios(readFileSync(ruta, 'utf8')).forEach((linea, i) => {
        if (!sinNombresInternos(linea).includes('Fiscalito')) return;
        hallazgos.push(`${ruta.slice(SRC.length)}:${i + 1}  ${linea.trim()}`);
      });
    }

    expect(hallazgos, hallazgos.join('\n')).toEqual([]);
  });

  it('el título del documento tampoco', () => {
    // `index.html` no puede importar la constante —es estático— así que su
    // título se ancla aquí: es lo que se lee en la pestaña del navegador y en
    // el nombre de un marcador guardado.
    const html = readFileSync(join(SRC, '..', 'index.html'), 'utf8');
    expect(html).not.toContain('Fiscalito');
    expect(html).toContain(`<title>${MARCA}</title>`);
  });
});

describe('la marca vive en un solo lugar', () => {
  it('las constantes son coherentes entre sí', () => {
    // El logotipo se pinta en dos mitades con estilos distintos; juntas tienen
    // que ser el nombre corto, o el header diría una cosa y los PDF otra.
    expect(`${MARCA_LOGO_1} ${MARCA_LOGO_2}`).toBe(MARCA_CORTA);
    expect(MARCA.startsWith(MARCA_CORTA)).toBe(true);
  });

  it('el prefijo de archivo no lleva espacios, acentos ni guiones largos', () => {
    // Acaba en el nombre de una descarga. `MARCA` sí los lleva, y por eso son
    // dos constantes y no un `replace` sobre una.
    expect(PREFIJO_ARCHIVO).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(MARCA).toMatch(/[—\s]/);
  });

  it('el asistente tiene nombre propio', () => {
    // Se presenta y firma, así que es una entidad distinta del producto. Si
    // colgara de `MARCA`, el bot se presentaría como "Orca Ordorica — Nómina".
    expect(ASISTENTE.length).toBeGreaterThan(0);
    expect(ASISTENTE).not.toContain('—');
  });
});
