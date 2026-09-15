/**
 * Catálogo de cuentas del **código agrupador del SAT** — T7, CASCARÓN.
 *
 * QUÉ ES ESTE ARCHIVO Y QUÉ NO ES
 * -------------------------------
 * Es el subconjunto de cuentas de primer nivel que las pólizas de `polizas.ts`
 * necesitan para cuadrar, más las que un catálogo mínimo tiene que enseñar para
 * que se vea de qué se está hablando. **No es el catálogo completo del Anexo 24
 * de la RMF**, que trae más de doscientas cuentas y subcuentas.
 *
 * FUENTE — LÉASE ANTES DE USARLO CON UN CLIENTE REAL
 * -------------------------------------------------
 * El código agrupador lo publica el SAT en el **Anexo 24 de la Resolución
 * Miscelánea Fiscal** (contabilidad electrónica). Los ocho códigos que la tarea
 * nombró explícitamente —101, 102, 105, 118, 201, 208, 401 y 601— son los que
 * entran a las pólizas. **El resto de códigos y TODOS los nombres de este
 * archivo están PENDIENTES DE CONTRASTAR contra el Anexo 24 publicado**: se
 * escribieron sin el documento enfrente, y en un catálogo contable un código
 * equivocado se ve exactamente igual que uno correcto.
 *
 * Por eso el catálogo se marca `PORVALIDAR` en pantalla, igual que el layout de
 * la DIOT en T5: mientras nadie lo coteje, esto sirve para ver la mecánica de
 * la partida doble, no para subir un catálogo al buzón tributario.
 */

/** Marca de procedencia del catálogo. Se pinta en el tab Catálogo. */
export const FUENTE_CATALOGO = 'PORVALIDAR' as const;

/** Rubro del estado financiero al que pertenece la cuenta. */
export type RubroCuenta = 'activo' | 'pasivo' | 'capital' | 'ingreso' | 'costo' | 'gasto';

/** Naturaleza del saldo: deudora suma por cargo, acreedora por abono. */
export type NaturalezaCuenta = 'deudora' | 'acreedora';

export interface CuentaSAT {
  /** Código agrupador de primer nivel. */
  codigo: string;
  nombre: string;
  rubro: RubroCuenta;
  naturaleza: NaturalezaCuenta;
}

export const CATALOGO_SAT: CuentaSAT[] = [
  // --- Activo ---
  { codigo: '101', nombre: 'Caja', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '102', nombre: 'Bancos', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '103', nombre: 'Inversiones', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '105', nombre: 'Clientes', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '107', nombre: 'Contribuciones a favor', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '110', nombre: 'Pagos anticipados', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '111', nombre: 'Inventario', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '115', nombre: 'Anticipo a proveedores', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '118', nombre: 'IVA acreditable pagado', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '119', nombre: 'IVA acreditable pendiente de pago', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '151', nombre: 'Terrenos', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '152', nombre: 'Edificios', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '154', nombre: 'Mobiliario y equipo de oficina', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '155', nombre: 'Equipo de transporte', rubro: 'activo', naturaleza: 'deudora' },
  { codigo: '156', nombre: 'Equipo de cómputo', rubro: 'activo', naturaleza: 'deudora' },

  // --- Pasivo ---
  { codigo: '201', nombre: 'Proveedores', rubro: 'pasivo', naturaleza: 'acreedora' },
  { codigo: '203', nombre: 'Acreedores diversos a corto plazo', rubro: 'pasivo', naturaleza: 'acreedora' },
  { codigo: '205', nombre: 'Anticipo de clientes', rubro: 'pasivo', naturaleza: 'acreedora' },
  { codigo: '208', nombre: 'IVA trasladado cobrado', rubro: 'pasivo', naturaleza: 'acreedora' },
  { codigo: '209', nombre: 'IVA trasladado no cobrado', rubro: 'pasivo', naturaleza: 'acreedora' },
  { codigo: '213', nombre: 'Impuestos y derechos por pagar', rubro: 'pasivo', naturaleza: 'acreedora' },
  { codigo: '216', nombre: 'Impuestos retenidos por enterar', rubro: 'pasivo', naturaleza: 'acreedora' },

  // --- Capital ---
  { codigo: '301', nombre: 'Capital social', rubro: 'capital', naturaleza: 'acreedora' },
  { codigo: '304', nombre: 'Resultado de ejercicios anteriores', rubro: 'capital', naturaleza: 'acreedora' },

  // --- Resultados ---
  { codigo: '401', nombre: 'Ingresos', rubro: 'ingreso', naturaleza: 'acreedora' },
  { codigo: '402', nombre: 'Devoluciones, descuentos o bonificaciones sobre ingresos', rubro: 'ingreso', naturaleza: 'deudora' },
  { codigo: '501', nombre: 'Costo de venta', rubro: 'costo', naturaleza: 'deudora' },
  { codigo: '601', nombre: 'Gastos generales', rubro: 'gasto', naturaleza: 'deudora' },
];

const POR_CODIGO = new Map(CATALOGO_SAT.map((c) => [c.codigo, c]));

/**
 * La cuenta, o `undefined` si el código no está en el catálogo.
 *
 * Devuelve `undefined` en vez de inventar una cuenta vacía: un renglón de
 * balanza con nombre en blanco es más difícil de notar que uno que falta.
 */
export function cuentaPorCodigo(codigo: string): CuentaSAT | undefined {
  return POR_CODIGO.get(codigo);
}

/** El nombre de la cuenta, o el código pelado si no está en el catálogo. */
export function nombreDeCuenta(codigo: string): string {
  return POR_CODIGO.get(codigo)?.nombre ?? codigo;
}

/** Etiqueta legible del rubro, para agrupar el catálogo en pantalla. */
export const ETIQUETA_RUBRO: Record<RubroCuenta, string> = {
  activo: 'Activo',
  pasivo: 'Pasivo',
  capital: 'Capital contable',
  ingreso: 'Ingresos',
  costo: 'Costos',
  gasto: 'Gastos',
};

/** Orden de pintado de los rubros: el del estado de situación financiera. */
export const ORDEN_RUBROS: RubroCuenta[] = ['activo', 'pasivo', 'capital', 'ingreso', 'costo', 'gasto'];
