/**
 * RFC, código postal y entidad federativa del cliente (C-01).
 *
 * Funciones puras: el formulario las usa para decidir si se puede guardar, y
 * `schemas/cartera.py` aplica **las mismas reglas** del lado del backend. Si una
 * cambia, cambian las dos: que el navegador acepte lo que el backend rechaza es
 * un 422 sobre un campo que el contador ya dio por bueno.
 */

/**
 * Catálogo `c_Estado` del SAT (Anexo 20, catálogos del CFDI), sólo las claves de
 * México. Fuente: `apps/api/tests/xsd/catCFDI.xsd`, simpleType `c_Estado`,
 * versionado offline en el repo (su sha256 lo fija
 * `tests/nomina/test_xsd_versionados.py`); `tests/cartera/test_cartera_crud.py`
 * compara la lista del backend contra ese archivo, y `datosFiscalesCliente.test.ts`
 * compara ésta contra la misma lista.
 *
 * **La Ciudad de México tiene DOS claves vigentes en el catálogo**: `CMX` y la
 * anterior `DIF`. Se ofrecen las dos y no se elige por el contador: un cliente
 * que ya timbra con `DIF` no tiene por qué cambiar aquí.
 */
export const ENTIDADES_FEDERATIVAS = [
  { clave: 'AGU', nombre: 'Aguascalientes' },
  { clave: 'BCN', nombre: 'Baja California' },
  { clave: 'BCS', nombre: 'Baja California Sur' },
  { clave: 'CAM', nombre: 'Campeche' },
  { clave: 'CHP', nombre: 'Chiapas' },
  { clave: 'CHH', nombre: 'Chihuahua' },
  { clave: 'CMX', nombre: 'Ciudad de México' },
  { clave: 'DIF', nombre: 'Ciudad de México (clave anterior DIF)' },
  { clave: 'COA', nombre: 'Coahuila' },
  { clave: 'COL', nombre: 'Colima' },
  { clave: 'DUR', nombre: 'Durango' },
  { clave: 'GUA', nombre: 'Guanajuato' },
  { clave: 'GRO', nombre: 'Guerrero' },
  { clave: 'HID', nombre: 'Hidalgo' },
  { clave: 'JAL', nombre: 'Jalisco' },
  { clave: 'MEX', nombre: 'Estado de México' },
  { clave: 'MIC', nombre: 'Michoacán' },
  { clave: 'MOR', nombre: 'Morelos' },
  { clave: 'NAY', nombre: 'Nayarit' },
  { clave: 'NLE', nombre: 'Nuevo León' },
  { clave: 'OAX', nombre: 'Oaxaca' },
  { clave: 'PUE', nombre: 'Puebla' },
  { clave: 'QUE', nombre: 'Querétaro' },
  { clave: 'ROO', nombre: 'Quintana Roo' },
  { clave: 'SLP', nombre: 'San Luis Potosí' },
  { clave: 'SIN', nombre: 'Sinaloa' },
  { clave: 'SON', nombre: 'Sonora' },
  { clave: 'TAB', nombre: 'Tabasco' },
  { clave: 'TAM', nombre: 'Tamaulipas' },
  { clave: 'TLA', nombre: 'Tlaxcala' },
  { clave: 'VER', nombre: 'Veracruz' },
  { clave: 'YUC', nombre: 'Yucatán' },
  { clave: 'ZAC', nombre: 'Zacatecas' },
] as const;

/** 3 letras (moral) o 4 (física) + fecha AAMMDD + homoclave. Igual a `schemas/fiscal.py`. */
const RFC_FORMATO = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/;

/**
 * Longitudes que admite cada régimen: 601 es persona moral (12) y 612 de
 * persona física (13). Un régimen fuera de esta tabla sólo se valida en formato.
 *
 * DECISIÓN PROVISIONAL (nocturno): 626 acepta 12 **y** 13. El backlog de C-01
 * dice "626 = 13", pero RESICO también lo tributan personas morales (Título
 * VII, Cap. XII LISR, Arts. 206-215), y exigir 13 dejaría fuera a un cliente
 * RESICO moral legítimo sin salida. Lo conservador es no rechazar un RFC
 * válido; confirmarlo con la contadora queda en `docs/decisiones-nomina.md` §D31.
 */
const LONGITUDES_POR_REGIMEN: Record<string, readonly number[]> = {
  '601': [12],
  '612': [13],
  '626': [12, 13],
};

export function normalizarRfc(rfc: string): string {
  return rfc.trim().toUpperCase();
}

export function problemaRfc(rfc: string, regimen: string, obligatorio: boolean): string | null {
  const valor = normalizarRfc(rfc);
  if (valor === '') return obligatorio ? 'Captura el RFC del cliente.' : null;
  if (!RFC_FORMATO.test(valor)) {
    return (
      'El RFC no tiene un formato válido: son 12 caracteres para persona moral o 13 para ' +
      'física (3 o 4 letras, 6 dígitos de fecha y 3 de homoclave).'
    );
  }
  const admitidas = LONGITUDES_POR_REGIMEN[regimen];
  if (admitidas !== undefined && !admitidas.includes(valor.length)) {
    return admitidas[0] === 12
      ? `El régimen ${regimen} es de persona moral: su RFC son 12 caracteres, no ${valor.length}.`
      : `El régimen ${regimen} es de persona física: su RFC son 13 caracteres, no ${valor.length}.`;
  }
  return null;
}

export function problemaCodigoPostal(cp: string, obligatorio: boolean): string | null {
  const valor = cp.trim();
  if (valor === '') return obligatorio ? 'Captura el código postal del domicilio fiscal.' : null;
  return /^\d{5}$/.test(valor) ? null : 'El código postal son 5 dígitos.';
}

export function problemaEntidad(clave: string, obligatorio: boolean): string | null {
  if (clave === '') return obligatorio ? 'Elige la entidad federativa.' : null;
  return ENTIDADES_FEDERATIVAS.some((e) => e.clave === clave)
    ? null
    : `La clave de entidad ${clave} no está en el catálogo c_Estado del SAT.`;
}

export interface DatosFiscales {
  rfc?: string;
  codigo_postal?: string;
  clave_entidad?: string;
}

/** Lo que falta o está mal, con el motivo. Vacío = se puede guardar. */
export function problemasFiscales(
  datos: DatosFiscales,
  regimen: string,
  obligatorio: boolean,
): string[] {
  return [
    problemaRfc(datos.rfc ?? '', regimen, obligatorio),
    problemaCodigoPostal(datos.codigo_postal ?? '', obligatorio),
    problemaEntidad(datos.clave_entidad ?? '', obligatorio),
  ].filter((p): p is string => p !== null);
}
