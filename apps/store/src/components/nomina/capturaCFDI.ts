/**
 * Lo que el operador captura del trabajador para el CFDI de nómina (T4).
 *
 * Vive fuera de `TablaCFDIEmpleados.tsx` por la misma razón que
 * `estilosCampo.ts` vive fuera de `Campo.tsx`: un módulo que exporta un
 * componente **y** otra cosa rompe el fast refresh de Vite.
 *
 * **Son los campos que `EmpleadoCartera` todavía no guarda.** El NSS sí está en
 * el modelo y aparece aquí porque el capturado tiene que poder ganarle al de la
 * ficha cuando la ficha lo trae vacío — que es el caso de casi toda la cartera.
 */

export interface DatosTrabajadorCaptura {
  rfc: string;
  curp: string;
  nss: string;
  codigo_postal: string;
}

export const CAPTURA_VACIA: DatosTrabajadorCaptura = {
  rfc: '',
  curp: '',
  nss: '',
  codigo_postal: '',
};
