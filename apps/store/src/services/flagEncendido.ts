/**
 * Cómo se lee un flag de `.env` en esta app, en un solo lugar. (T2)
 *
 * POR QUÉ EXISTE
 * --------------
 * Había dos convenciones. `modoEmpresa.ts` aceptaba `1`, `true`, `on`, `yes`,
 * `si` y `sí`, y lo justificaba con una frase que vale para cualquier flag:
 * *"un flag que ignora en silencio lo que le escribieron es peor que no
 * tenerlo"*. `cartera.ts` comparaba `=== '1'` y nada más, así que un
 * `VITE_CARTERA_BACKEND=true` en el `.env` dejaba el backend apagado **sin
 * decirlo** — y el síntoma de eso no es un error de configuración: es un
 * contador convencido de que está probando el backend cuando está escribiendo
 * Firestore.
 *
 * LA REGLA
 * --------
 * Encienden los valores que **no pueden significar otra cosa**. Lo ambiguo y lo
 * vacío dejan el flag APAGADO: un `.env` a medio escribir no cambia de app.
 *
 * Esto NO decide el default de ningún flag; sólo cómo se interpreta lo que
 * venga escrito. El default lo declara cada flag en su módulo, y los dos que
 * hay hoy —`VITE_MODO_EMPRESA_UNICA` y `VITE_CARTERA_BACKEND`— vienen apagados.
 */

/** Las formas de ENCENDER un flag. Todo lo demás lo deja apagado. */
const ENCENDIDO = new Set(['1', 'true', 'on', 'yes', 'si', 'sí']);

/**
 * `true` si el valor de entorno enciende el flag.
 *
 * Toma `unknown` porque `import.meta.env` no garantiza `string`: una variable
 * sin poner llega como `undefined`, y en los tests `vi.stubEnv` puede dejar
 * cualquier cosa.
 */
export function flagEncendido(valor: unknown): boolean {
  return ENCENDIDO.has(String(valor ?? '').trim().toLowerCase());
}
