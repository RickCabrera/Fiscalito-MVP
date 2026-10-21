/**
 * Finiquito, aguinaldo y PTU del cliente (P4-06, P4-07, P4-08), más el ajuste anual.
 *
 * Captura lo que no está en la ficha (fecha y causa de la baja, renta gravable, días y
 * salarios del año) y pinta lo que devuelve el motor, con su desglose. Ningún importe se
 * calcula aquí. Cada cálculo queda en el historial del cliente.
 */

import { useState } from 'react';
import type { EmpleadoCartera } from '../../services/carteraApi';
import {
  calcularAguinaldo,
  calcularAjusteAnual,
  calcularFiniquito,
  calcularPTU,
  type CalculoExtraordinario,
} from '../../services/nominaApi';
import { labelStyle } from '../../utils/styles';
import ResultadoExtraordinario from './ResultadoExtraordinario';

export type TipoExtraordinaria = 'finiquito' | 'aguinaldo' | 'ptu';

const CAUSAS: [string, string][] = [
  ['renuncia', 'Renuncia voluntaria'],
  ['despido_injustificado', 'Despido injustificado (liquidación)'],
  ['despido_justificado', 'Despido justificado'],
  ['termino_contrato', 'Término de contrato'],
  ['muerte', 'Muerte del trabajador'],
];

const fila: React.CSSProperties = { display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', alignItems: 'flex-end' };

export default function NominaExtraordinaria({
  tipo,
  clienteId,
  empleados,
}: {
  tipo: TipoExtraordinaria;
  clienteId: string;
  empleados: EmpleadoCartera[];
}) {
  const anio = new Date().getFullYear();
  const [ejercicio, setEjercicio] = useState(tipo === 'ptu' ? anio - 1 : anio);
  const [fechaPago, setFechaPago] = useState(tipo === 'aguinaldo' ? `${anio}-12-15` : `${anio}-05-29`);
  const [empleado, setEmpleado] = useState(empleados[0]?.empleado_no ?? '');
  const [fechaBaja, setFechaBaja] = useState('');
  const [causa, setCausa] = useState('renuncia');
  const [renta, setRenta] = useState('');
  const [anual, setAnual] = useState<Record<string, { dias: string; salarios: string }>>({});
  const [resultado, setResultado] = useState<CalculoExtraordinario | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const correr = async (promesa: () => Promise<CalculoExtraordinario>) => {
    setOcupado(true);
    setError(null);
    try {
      setResultado(await promesa());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  const calcular = () => {
    if (tipo === 'aguinaldo') {
      return correr(() => calcularAguinaldo(clienteId, { ejercicio, fecha_pago: fechaPago }));
    }
    if (tipo === 'finiquito') {
      return correr(() => calcularFiniquito(clienteId, { empleado_no: empleado, fecha_baja: fechaBaja, causa }));
    }
    return correr(() =>
      calcularPTU(clienteId, {
        ejercicio,
        renta_gravable: renta,
        fecha_pago: fechaPago,
        trabajadores: empleados
          .filter((e) => anual[e.empleado_no]?.dias)
          .map((e) => ({
            empleado_no: e.empleado_no,
            dias_trabajados: Number(anual[e.empleado_no].dias),
            salarios_devengados: anual[e.empleado_no].salarios || '0',
          })),
      }),
    );
  };

  const campo = (etiqueta: string, control: React.ReactNode) => (
    <label style={{ flex: '0 1 200px' }}>
      <span style={labelStyle}>{etiqueta}</span>
      {control}
    </label>
  );

  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div style={fila}>
        {tipo !== 'finiquito' &&
          campo('Ejercicio', (
            <input className="input-field" type="number" value={ejercicio} onChange={(e) => setEjercicio(Number(e.target.value))} />
          ))}
        {tipo !== 'finiquito' &&
          campo('Fecha de pago', (
            <input className="input-field" type="date" value={fechaPago} onChange={(e) => setFechaPago(e.target.value)} />
          ))}
        {tipo === 'finiquito' &&
          campo('Empleado', (
            <select className="input-field" value={empleado} onChange={(e) => setEmpleado(e.target.value)}>
              {empleados.map((e) => (
                <option key={e.empleado_no} value={e.empleado_no}>
                  {e.nombre}
                </option>
              ))}
            </select>
          ))}
        {tipo === 'finiquito' &&
          campo('Fecha de baja', (
            <input className="input-field" type="date" value={fechaBaja} onChange={(e) => setFechaBaja(e.target.value)} />
          ))}
        {tipo === 'finiquito' &&
          campo('Causa', (
            <select className="input-field" value={causa} onChange={(e) => setCausa(e.target.value)}>
              {CAUSAS.map(([v, t]) => (
                <option key={v} value={v}>
                  {t}
                </option>
              ))}
            </select>
          ))}
        {tipo === 'ptu' &&
          campo('Renta gravable del ejercicio', (
            <input className="input-field" inputMode="decimal" value={renta} onChange={(e) => setRenta(e.target.value)} />
          ))}
      </div>
      {tipo === 'ptu' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}>
          <span style={labelStyle}>Días trabajados y salarios devengados en el ejercicio (Arts. 123 y 124 LFT)</span>
          {empleados.map((e) => (
            <div key={e.empleado_no} style={fila}>
              <span style={{ flex: '1 1 200px' }}>{e.nombre}</span>
              <input
                className="input-field"
                style={{ width: 90 }}
                aria-label={`Días de ${e.nombre}`}
                value={anual[e.empleado_no]?.dias ?? ''}
                onChange={(ev) => setAnual({ ...anual, [e.empleado_no]: { salarios: anual[e.empleado_no]?.salarios ?? '', dias: ev.target.value } })}
              />
              <input
                className="input-field"
                style={{ width: 130 }}
                aria-label={`Salarios de ${e.nombre}`}
                value={anual[e.empleado_no]?.salarios ?? ''}
                onChange={(ev) => setAnual({ ...anual, [e.empleado_no]: { dias: anual[e.empleado_no]?.dias ?? '', salarios: ev.target.value } })}
              />
            </div>
          ))}
        </div>
      )}
      <div style={fila}>
        <button className="btn-primary" disabled={ocupado || (tipo === 'finiquito' && !fechaBaja)} onClick={() => void calcular()}>
          Calcular {tipo}
        </button>
        {tipo === 'aguinaldo' && (
          <button className="btn-secondary" disabled={ocupado} onClick={() => void correr(() => calcularAjusteAnual(clienteId, ejercicio))}>
            Ajuste anual de ISR (Art. 97)
          </button>
        )}
      </div>
      {error && (
        <p role="alert" style={{ color: 'var(--danger)', margin: 0 }}>
          {error}
        </p>
      )}
      {resultado && <ResultadoExtraordinario calculo={resultado} />}
    </section>
  );
}
