/**
 * Qué cuentas ven los datos de demostración. (R-06)
 *
 * EL PROBLEMA QUE RESUELVE
 * ------------------------
 * La app arrastra tres clientes de demostración —uno construido de un CFDI
 * timbrado **real** con montos reales anonimizados, y dos sintéticos— y una
 * pestaña con el histórico de ese caso real. Servían para la demo del
 * 2026-09-02. Después de esa fecha, una cuenta nueva que entra y ve la cartera
 * de otra persona no está viendo una demostración: está viendo datos que no son
 * suyos.
 *
 * NO SE BORRA NADA
 * ----------------
 * Las fixtures, sus tests y `GET /despacho/clientes/{id}` **se quedan enteros**:
 * son la verificación del motor contra la realidad, que es lo único que
 * demuestra que los números cuadran al centavo. Lo que cambia es **quién los
 * ve**: se ocultan de la UI para las cuentas que no son de desarrollo.
 *
 * LOS TRES CLIENTES SE OCULTAN, INCLUIDO EL DEL CASO REAL
 * -------------------------------------------------------
 * Y aquí hay una versión anterior de esta tarea que hay que dejar escrita
 * porque estuvo **al revés**: filtraba `origen === 'sintetico'`, o sea Cafetería
 * y Taller —los dos **inventados**— y dejaba en pantalla `demo`, que es
 * "Servicios Administrativos Integrales", `origen="fixtures-s04"`, construido de
 * un comprobante timbrado real. Una tarea llamada "sacar el mock del flujo de
 * producción" habría escondido los mocks y dejado a la vista el único con
 * dinero de alguien. Se ocultan **los tres**.
 */

/** Orígenes que produce `apps/api/app/despacho_demo.py`. */
const ORIGENES_DEMO = new Set(['sintetico', 'fixtures-s04']);

/**
 * Si un cliente es de demostración.
 *
 * Se decide por `origen`, que **ya existe** en el backend y viaja en la
 * respuesta: no hace falta un campo nuevo ni tocar `despacho_demo.py`. Un
 * cliente capturado por el contador trae `origen: 'propio'` (ver `ModalCliente`)
 * y nunca cae aquí.
 */
export function esClienteDemo(origen: string): boolean {
  return ORIGENES_DEMO.has(origen);
}

/**
 * Si esta cuenta puede ver los datos de demostración.
 *
 * Tres puertas, de la más automática a la más explícita:
 *
 * 1. `import.meta.env.DEV` — el servidor de desarrollo de Vite. Cubre el caso
 *    normal: quien corre `npm run dev` está desarrollando.
 * 2. `VITE_MOSTRAR_DEMO=1` — para enseñar la demo desde un build de producción,
 *    que es exactamente lo que hace falta para un ensayo con el proyector.
 * 3. `VITE_CUENTAS_DEMO` — lista de correos separados por coma. Para que una
 *    cuenta concreta vea la demostración en un despliegue compartido sin
 *    abrírsela a todo el mundo.
 *
 * **El default es NO.** Una cuenta nueva en un build de producción no ve nada
 * que no sea suyo, que es el criterio literal de R-06.
 */
export function esCuentaDeDesarrollo(email: string | null | undefined): boolean {
  if (import.meta.env.DEV) return true;
  if (import.meta.env.VITE_MOSTRAR_DEMO === '1') return true;

  const permitidas = String(import.meta.env.VITE_CUENTAS_DEMO ?? '')
    .split(',')
    .map((c) => c.trim().toLowerCase())
    .filter(Boolean);
  if (permitidas.length === 0 || !email) return false;
  return permitidas.includes(email.toLowerCase());
}
