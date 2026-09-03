/**
 * Traducción de una respuesta de error del backend a un mensaje para pantalla.
 *
 * POR QUÉ EXISTE ESTE ARCHIVO
 * ---------------------------
 * El 2026-09-02 el calendario patronal mostró `No se pudo cargar el calendario
 * patronal: Not Found` en el navegador. No era un bug de ruta: la API que
 * respondía se había levantado ANTES del merge que agregó
 * `/api/v1/despacho/calendario`, así que servía los endpoints viejos con 200 y
 * el nuevo con 404. El mensaje no daba forma de saberlo — "Not Found" es lo que
 * FastAPI escribe cuando *la ruta no existe*, y se leía igual que cualquier
 * otro error.
 *
 * LOS DOS 404 NO SON EL MISMO 404
 * -------------------------------
 * Medido contra la API real, el backend produce cuatro formas distintas:
 *
 * | Caso                          | Status | Cuerpo                                    |
 * |-------------------------------|--------|-------------------------------------------|
 * | Cliente inexistente (dominio) | 404    | `{"exito":false,"error":"El cliente…"}`   |
 * | Ruta inexistente (FastAPI)    | 404    | `{"detail":"Not Found"}`                  |
 * | Método equivocado (FastAPI)   | 405    | `{"detail":"Method Not Allowed"}`         |
 * | Validación de dominio         | 422    | `{"exito":false,"error":"Año fuera de…"}` |
 *
 * Los 404 de dominio del backend son `FiscalAgentError`, nunca `HTTPException`,
 * y por eso salen con sobre propio (`{exito, error}`) por el handler global de
 * `main.py`. Ningún 404 legítimo del backend viaja con `detail` string. Esa es
 * la razón por la que se puede distinguir: `detail` string + 404/405 significa
 * **el backend que contestó no conoce esta llamada**.
 *
 * EL MENSAJE NO DIAGNOSTICA, DESCRIBE
 * -----------------------------------
 * Hay dos causas para eso y desde el navegador no se distinguen: un proceso de
 * antes del último merge, o `VITE_FISCAL_AGENT_URL` apuntando a otro backend.
 * Afirmar una sola mandaría a reiniciar un servidor cuando el problema era el
 * `.env`. Por eso el mensaje dice **qué se observó** —qué backend, qué ruta— y
 * ofrece las dos.
 */

/** Cuerpo de error tal como puede llegar. Todo opcional: no se confía en nada. */
interface CuerpoError {
  error?: unknown;
  detail?: unknown;
}

/**
 * `<origen> · <ruta>` de la petición, para que el mensaje diga contra QUÉ
 * backend se estrelló. `res.url` está vacío en algunos stubs de test y en
 * respuestas opacas; en ese caso se omite en vez de inventar.
 */
function dondePego(res: Response): string | null {
  if (!res.url) return null;
  try {
    const u = new URL(res.url);
    return `${u.origin}${u.pathname}`;
  } catch {
    return res.url;
  }
}

/**
 * `true` cuando la respuesta es FastAPI diciendo "no conozco esta llamada":
 * 404 (ruta inexistente) o 405 (la ruta existe con otro verbo, que es el mismo
 * diagnóstico cuando un endpoint cambió de método entre commits).
 */
function esRutaDesconocida(res: Response, cuerpo: CuerpoError | null): boolean {
  return (
    (res.status === 404 || res.status === 405) && typeof cuerpo?.detail === 'string'
  );
}

function mensajeDeRutaDesconocida(res: Response): string {
  const donde = dondePego(res);
  const backend = donde ? `El backend en ${donde}` : 'El backend';
  return (
    `${backend} contestó ${res.status}: no reconoce esta llamada. ` +
    'O el proceso que responde es de antes del último merge (relánzalo), ' +
    'o VITE_FISCAL_AGENT_URL apunta a otro backend.'
  );
}

/**
 * Detalle legible de una respuesta que no es `ok`.
 *
 * El orden importa: `error` (sobre propio del backend) se lee ANTES que
 * `detail`. Invertirlo haría que un 404 de dominio que algún día traiga los dos
 * campos se reporte como ruta inexistente, que es lo contrario de la verdad.
 */
/**
 * Un `422` de FastAPI, escrito para que se pueda ARREGLAR. (F-02)
 *
 * FastAPI responde `{"detail": [{loc, msg, type}, ...]}`. Se pintaba
 * `detail[0].msg` a secas, y eso produce mensajes que no se pueden accionar:
 *
 * - `"Extra inputs are not permitted"` — ¿cuál campo? El `msg` no lo dice; el
 *   nombre vive en `loc`. Es justo el 422 que tumbó el alta de empleado en
 *   F-01 (`tabla_vacaciones` contra una API anterior a O-03), y el operador
 *   veía una frase en inglés sin una sola pista de qué tocar.
 * - Con varios campos inválidos, los demás se perdían: se arregla uno, se
 *   reintenta, aparece el siguiente. Se muestran todos.
 *
 * `loc` viene como `["body", "tabla_vacaciones"]` o `["body", "incidencias",
 * 0, "faltas"]`. Se tira el primer segmento —siempre es de dónde venía, no
 * qué campo es— y el resto se une con puntos, que es como lo nombra quien lo
 * mandó. Los índices se conservan: en una plantilla de 40 empleados, saber que
 * es el renglón 12 es la mitad del arreglo.
 */
function validacionesLegibles(detail: unknown[]): string | null {
  const partes = detail
    .map((d) => {
      const e = d as { loc?: unknown; msg?: unknown };
      if (typeof e?.msg !== 'string') return null;
      const campo = Array.isArray(e.loc)
        ? e.loc
            .slice(1)
            .filter((s) => typeof s === 'string' || typeof s === 'number')
            .join('.')
        : '';
      return campo ? `${campo}: ${e.msg}` : e.msg;
    })
    .filter((p): p is string => Boolean(p));

  // Tope: un 422 sobre una plantilla grande puede traer un renglón por
  // empleado, y volcarlos todos en un aviso lo vuelve ilegible otra vez.
  if (partes.length === 0) return null;
  if (partes.length <= 3) return partes.join(' · ');
  return `${partes.slice(0, 3).join(' · ')} (y ${partes.length - 3} más)`;
}

export function detalleDelError(res: Response, cuerpo: unknown): string {
  const c = (cuerpo ?? null) as CuerpoError | null;

  if (typeof c?.error === 'string') return c.error;
  if (esRutaDesconocida(res, c)) return mensajeDeRutaDesconocida(res);
  if (Array.isArray(c?.detail)) {
    const legible = validacionesLegibles(c.detail);
    if (legible) return legible;
  }
  if (typeof c?.detail === 'string') return c.detail;
  return `El servidor respondió ${res.status}`;
}

/** Lee el cuerpo como JSON sin reventar si no lo es (HTML de un proxy, vacío…). */
export async function cuerpoDeError(res: Response): Promise<unknown> {
  return res.json().catch(() => null);
}
