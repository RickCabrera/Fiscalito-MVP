/**
 * Las acciones de la pantalla de nómina: cerrar el periodo y calcular. (E-06 → P4)
 *
 * Salieron de `useNominaCliente` por el tope de 300 líneas. Las GUARDAS viven en los
 * handlers, no en el `disabled` del botón (ver `useNominaCliente.guardas.test.ts`):
 * `disabled` es una propiedad del DOM, no una garantía.
 *
 * - Cerrar mientras la cartera carga usaría las llaves del catálogo en vez de las del
 *   aparato (bug de G-02 por la puerta del tiempo). Las tres puertas —`pedirCierre`,
 *   `cerrar` y el "Cerrar de todos modos" del diálogo— se guardan.
 * - Calcular un cliente ajeno a la cartera se niega con mensaje (R-06).
 * - La llave del dato es `clienteId` (el de la ruta), no `cliente.id` (F-02).
 *
 * P4-01: el cálculo ya no manda la plantilla; la lee el backend de la cartera.
 */

import type { Dispatch, SetStateAction } from 'react';
import type { ClienteDetalle } from '../../services/despachoApi';
import type { EmpleadoCartera } from '../../services/carteraApi';
import { cerrarPeriodo, type CierrePeriodo, type EmpleadoNominaRequest } from '../../services/nominaDemoApi';
import { calcularNomina, type NominaCalculada, type TipoNomina, type VariablesEmpleado } from '../../services/nominaApi';
import { incidenciasConLlaveDeCalculo, llavesParaElCierre } from './llavesDelCierre';

export type DeCliente<T> = { id: string; valor: T };
type Setter<T> = Dispatch<SetStateAction<DeCliente<T> | null>>;

/**
 * Qué fecha de pago mandar (§D18). Si el operador movió el periodo, `null`: la resuelve
 * el backend y la respuesta trae `fecha_pago_efectiva`. Mandar la sugerida calcularía
 * con la vigencia de otro mes.
 */
export function fechaDePago(cliente: ClienteDetalle, inicio: string, fin: string): string | null {
  const sugerido = cliente.periodo_sugerido;
  return inicio === sugerido.inicio && fin === sugerido.fin ? sugerido.fecha_pago : null;
}

interface Entradas {
  clienteId: string;
  cliente: ClienteDetalle | null;
  cierre: CierrePeriodo | null;
  carteraCargando: boolean;
  ajenoALaCartera: boolean;
  plantilla: EmpleadoNominaRequest[];
  empleadosCartera: EmpleadoCartera[] | null;
  inicio: string;
  fin: string;
  sinChecadasEnElPeriodo: boolean;
  tipo: TipoNomina;
  variables: VariablesEmpleado[];
  setCierreDe: Setter<CierrePeriodo | null>;
  setNominaDe: Setter<NominaCalculada | null>;
  setErrorDe: Setter<string | null>;
  setOcupado: (v: boolean) => void;
  setConfirmarPara: (v: string | null) => void;
}

export function useAccionesNomina(e: Entradas) {
  /** El cierre vuelve con la llave del checador; los recibos se indexan por la del cálculo. */
  const conLlaveDeCalculo = (resultado: CierrePeriodo): CierrePeriodo =>
    e.empleadosCartera
      ? { ...resultado, incidencias: incidenciasConLlaveDeCalculo(resultado.incidencias, e.empleadosCartera) }
      : resultado;

  const cerrar = async () => {
    if (!e.cliente) return;
    if (e.carteraCargando || e.ajenoALaCartera) return;
    const id = e.clienteId;
    e.setConfirmarPara(null);
    e.setOcupado(true);
    e.setErrorDe(null);
    try {
      e.setNominaDe({ id, valor: null });
      // La llave del CHECADOR: `cerrar_periodo` casa el `employeeNoString` del aparato.
      const resultado = await cerrarPeriodo(id, llavesParaElCierre(e.plantilla, e.empleadosCartera), {
        inicio: e.inicio,
        fin: e.fin,
      });
      e.setCierreDe({ id, valor: conLlaveDeCalculo(resultado) });
    } catch (err) {
      e.setErrorDe({ id, valor: (err as Error).message });
    } finally {
      e.setOcupado(false);
    }
  };

  const calcular = async () => {
    // Asimilados no checan (P4-04): se calculan sin cierre, con el periodo completo.
    if (!e.cliente || (!e.cierre && e.tipo !== 'asimilados')) return;
    if (e.ajenoALaCartera) {
      e.setErrorDe({
        id: e.clienteId,
        valor:
          'Este cliente no está en la cartera de tu cuenta, así que no se puede calcular su ' +
          'nómina: la plantilla saldría del catálogo de demostración y no de tus empleados. ' +
          'Ábrelo desde tu lista de clientes.',
      });
      return;
    }
    const id = e.clienteId;
    e.setOcupado(true);
    e.setErrorDe(null);
    try {
      e.setNominaDe({
        id,
        valor: await calcularNomina(
          id,
          { inicio: e.inicio, fin: e.fin, fecha_pago: fechaDePago(e.cliente, e.inicio, e.fin) },
          e.cierre?.incidencias ?? [],
          e.cliente,
          { tipo: e.tipo, variables: e.variables },
        ),
      });
    } catch (err) {
      e.setErrorDe({ id, valor: (err as Error).message });
    } finally {
      e.setOcupado(false);
    }
  };

  const pedirCierre = () => {
    if (!e.cliente || e.carteraCargando || e.ajenoALaCartera) return;
    // Sin checadas EN EL PERIODO el cálculo no sale en ceros: mejor preguntar.
    if (e.sinChecadasEnElPeriodo) e.setConfirmarPara(e.cliente.id);
    else void cerrar();
  };

  return { cerrar, calcular, pedirCierre };
}
