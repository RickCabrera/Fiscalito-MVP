/**
 * Quién es la persona: número, nombre y los tres campos del IMSS. (O-04)
 *
 * SE EXTRAJO PORQUE O-04 CRECIÓ EL MODAL, NO PARA REORDENAR
 * ----------------------------------------------------------
 * `ModalEmpleado.tsx` ya estaba en 477 líneas contra el tope de 300 de
 * `apps/store/CLAUDE.md` —deuda declarada en `backlog.md` §G punto 4— y los tres
 * campos nuevos lo llevaban a 556. La regla de la casa es no sumar a esa pila:
 * lo que esta tarea engorda, esta tarea lo parte.
 *
 * LOS APELLIDOS SE CAPTURAN; NO SE PARTEN
 * ---------------------------------------
 * El layout de movimientos afiliatorios del IMSS pide apellido paterno, materno
 * y nombre(s) en **tres campos de 27 posiciones** (23-49, 50-76, 77-103). La
 * app ya guarda el nombre completo, así que la tentación es partirlo.
 *
 * No se hace, y no es purismo: en español el **apellido compuesto es la norma**
 * ("SANTA CRUZ", "DE LA TORRE", "MARIA DE LOS ANGELES"), y cualquier heurística
 * falla en una parte grande de la plantilla. Un movimiento afiliatorio con el
 * apellido mal partido va sobre **otra persona** ante el IMSS. Es la misma
 * política del NSS y de `fecha_alta`: vacío cuando no se conoce, y **nunca
 * inventado**.
 *
 * Quien los tenga vacíos no se exporta, y el exportador lo dice con su razón —
 * en vez de quedar fuera en silencio, que es el modo de falla que este repo
 * lleva cinco épicas evitando.
 */

import Campo from './Campo';
import { campoInput as campo } from './estilosCampo';
import type { EmpleadoCartera } from '../../services/carteraApi';

export default function IdentidadEmpleado({
  datos,
  esAlta,
  set,
}: {
  datos: EmpleadoCartera;
  /** El número es la llave del cálculo: no se puede cambiar en una edición. */
  esAlta: boolean;
  set: <K extends keyof EmpleadoCartera>(campo: K, valor: EmpleadoCartera[K]) => void;
}) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
      <Campo label="Número de empleado *">
        <input
          style={campo}
          value={datos.empleado_no}
          disabled={!esAlta}
          onChange={(e) => set('empleado_no', e.target.value)}
          placeholder="E-10"
        />
      </Campo>
      <Campo label="Nombre *" ancho="2 1 320px">
        <input
          style={campo}
          value={datos.nombre}
          onChange={(e) => set('nombre', e.target.value)}
        />
      </Campo>

      <Campo label="Apellido paterno (IMSS)">
        <input
          style={campo}
          value={datos.apellido_paterno ?? ''}
          onChange={(e) => set('apellido_paterno', e.target.value)}
        />
      </Campo>
      <Campo label="Apellido materno (IMSS)">
        <input
          style={campo}
          value={datos.apellido_materno ?? ''}
          onChange={(e) => set('apellido_materno', e.target.value)}
        />
      </Campo>
      <Campo label="Nombre(s) de pila (IMSS)">
        <input
          style={campo}
          value={datos.nombres ?? ''}
          onChange={(e) => set('nombres', e.target.value)}
        />
      </Campo>

      <Campo label="Puesto">
        <input style={campo} value={datos.puesto} onChange={(e) => set('puesto', e.target.value)} />
      </Campo>
    </div>
  );
}
