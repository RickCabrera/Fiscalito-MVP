/**
 * "Ninguna pantalla dice la marca vieja" — el criterio de O-02, medido, ahora
 * apuntando al otro lado.
 *
 * POR QUÉ ESTE TEST CAMBIÓ DE OBJETIVO Y NO SE BORRÓ
 * --------------------------------------------------
 * O-02 lo escribió para cazar "Fiscalito", que entonces era el nombre viejo.
 * Con el rebrand de vuelta a **Fiscalito**, buscar esa cadena afirmaría lo
 * contrario de lo que se quiere: el guardián bloquearía la marca actual y
 * dejaría entrar la anterior. Lo que el test mide —"la marca vieja no se cuela
 * a mano en una pantalla nueva en vez de importar la constante"— sigue siendo
 * exactamente lo que hay que vigilar; lo único que cambia es cuál es la cadena
 * vieja. Hoy es "Orca".
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
 * 1. El criterio **es** una afirmación negativa sobre todo el árbol ("ninguna
 *    pantalla"), y montar las 15 pantallas para leer su texto sería más frágil y
 *    mucho más lento que leerlas en el fuente.
 * 2. Lo que de verdad protege es el **rebrand siguiente**. Ya van tres.
 *
 * LA LISTA DE PERMITIDOS ES EL PUNTO DÉBIL, Y HAY QUE VIGILARLA
 * -------------------------------------------------------------
 * Si crece, este test se vuelve decorativo. Con la marca anterior los permitidos
 * eran nombres internos (rutas, tipos, llaves de `localStorage`); "Orca" no
 * tiene ninguno —nunca se usó como identificador— así que queda **uno solo**, y
 * no es un nombre interno sino un DATO: la razón social de un cliente real.
 * Sigue siendo un patrón y no una ruta de archivo: un archivo entero exento
 * sería exactamente la puerta por donde vuelve la marca.
 */

import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { MARCA, MARCA_CORTA, MARCA_LOGO, ASISTENTE, PREFIJO_ARCHIVO } from './marca';

/**
 * `src/`, resuelto con `fileURLToPath` y no con `.pathname`.
 *
 * En Windows `new URL(...).pathname` devuelve la ruta con una barra de más
 * delante de la letra de unidad, y `join` acababa buscando en la raíz del
 * disco. El primer intento de este archivo **pasaba en vacío** por eso:
 * recorría cero archivos y no encontraba nada que reportar. Por eso abajo hay
 * una cota inferior de archivos recorridos.
 */
const SRC = dirname(dirname(fileURLToPath(import.meta.url)));

/** La marca anterior al rebrand. Lo que este test persigue. */
const MARCA_VIEJA = 'Orca';

/**
 * La razón social de un CLIENTE, que no es la marca del producto.
 *
 * "Orca Ordorica Cristal Templado S.A. de C.V." es una empresa real dada de
 * alta en Firestore: un REGISTRO. Aparece en pantalla como `placeholder` del
 * campo de razón social en `ConfiguracionEmpresa`, a modo de ejemplo, y ahí
 * tiene que seguir — borrarla no sería completar el rebrand, sería perder un
 * dato.
 *
 * Se permite el nombre de la empresa, **no la palabra suelta**: un
 * `<h1>Orca</h1>` en una pantalla nueva sigue siendo un hallazgo.
 */
const DATOS_PERMITIDOS = [
  /Orca Ordorica/g,
];

/**
 * Lo que queda de la línea después de tachar lo permitido.
 *
 * SE TACHAN, NO SE PERDONA LA LÍNEA ENTERA. La versión original de este test
 * descartaba cualquier línea que casara con un permitido, y eso dejó pasar el
 * caso que más importaba entonces:
 *
 *     { id: 'fiscalito', to: '/app/store/fiscalito/use', label: 'Fiscalito' },
 *
 * La ruta interna excusaba a la **etiqueta del sidebar**, que es texto que un
 * contribuyente lee en pantalla. El mecanismo se conserva tal cual porque la
 * trampa no era de aquella marca: es de cualquier línea que mezcle un permitido
 * con texto visible.
 */
function sinPermitidos(linea: string): string {
  return DATOS_PERMITIDOS.reduce((acc, patron) => acc.replace(patron, ''), linea);
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
  it('ni "Orca" ni el nombre completo viejo, fuera de la razón social del cliente', () => {
    const hallazgos: string[] = [];

    const fuentes = archivosFuente(SRC);
    // LA COTA QUE IMPIDE EL VERDE VACÍO. Sin ella, una ruta mal resuelta —o un
    // filtro de más— deja este test afirmando que no hay ocurrencias porque no
    // leyó ni un archivo. Ya pasó una vez.
    expect(fuentes.length).toBeGreaterThan(80);

    for (const ruta of fuentes) {
      sinComentarios(readFileSync(ruta, 'utf8')).forEach((linea, i) => {
        if (!sinPermitidos(linea).includes(MARCA_VIEJA)) return;
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
    expect(html).not.toContain(MARCA_VIEJA);
    expect(html).toContain(`<title>${MARCA}</title>`);
  });
});

describe('la marca vive en un solo lugar', () => {
  it('las constantes son coherentes entre sí', () => {
    // El logotipo es lo que se pinta con el gradiente en sidebar, landing,
    // login y onboarding: si se separara del nombre corto, el header diría una
    // cosa y los PDF otra. Con la marca anterior eran DOS mitades
    // (`MARCA_LOGO_1` + `MARCA_LOGO_2`) y esta misma aserción las sumaba.
    expect(MARCA_LOGO).toBe(MARCA_CORTA);
    expect(MARCA.startsWith(MARCA_CORTA)).toBe(true);
  });

  it('el prefijo de archivo no lleva espacios, acentos ni guiones largos', () => {
    // Acaba en el nombre de una descarga. Con esta marca el prefijo y el nombre
    // coinciden; con la anterior no, y por eso son dos constantes y no un
    // `replace` sobre una. La aserción que exigía un espacio o un guión largo
    // EN `MARCA` se cayó con el rebrand: afirmaba una propiedad de aquel
    // nombre, no una regla del módulo.
    expect(PREFIJO_ARCHIVO).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  it('el asistente tiene nombre propio', () => {
    // Se presenta y firma, así que es una entidad distinta del producto. Si
    // colgara de `MARCA`, el bot se presentaría con el nombre completo del
    // producto, que con la marca anterior llevaba un guión largo dentro.
    expect(ASISTENTE.length).toBeGreaterThan(0);
    expect(ASISTENTE).not.toContain('—');
  });
});
