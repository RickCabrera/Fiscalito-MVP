/**
 * Datos del RESPONSABLE del tratamiento (LFPDPPP) para el aviso de privacidad y los
 * términos (P6-01).
 *
 * NO SE INVENTAN. Vienen de `VITE_RESPONSABLE_*` (ver `.env.example`); el que falte se pinta
 * como `[POR DEFINIR: …]` para que salte a la vista en la página publicada. El texto legal es
 * una PLANTILLA genérica marcada "REVISAR CON ABOGADO".
 */

import { MARCA } from './marca';

export const POR_DEFINIR = '[POR DEFINIR';

export interface Responsable {
  nombre: string;
  domicilio: string;
  correo: string;
  fechaAviso: string;
  marca: string;
}

function valor(crudo: unknown, etiqueta: string): string {
  const texto = String(crudo ?? '').trim();
  return texto || `${POR_DEFINIR}: ${etiqueta}]`;
}

export function responsable(): Responsable {
  const env = import.meta.env;
  return {
    nombre: valor(env.VITE_RESPONSABLE_NOMBRE, 'nombre o razón social del responsable'),
    domicilio: valor(env.VITE_RESPONSABLE_DOMICILIO, 'domicilio del responsable'),
    correo: valor(env.VITE_RESPONSABLE_CORREO, 'correo para derechos ARCO'),
    fechaAviso: valor(env.VITE_RESPONSABLE_FECHA_AVISO, 'fecha de última actualización'),
    marca: MARCA,
  };
}
