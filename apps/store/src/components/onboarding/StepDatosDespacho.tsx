/**
 * Paso de datos del despacho (E-05).
 *
 * TRES CAMPOS, Y NINGUNO MÁS. Un despacho no declara por sí mismo en esta app:
 * el sujeto del cálculo es su CLIENTE. Pedirle RFC, régimen, actividad
 * económica o código postal era pedirle datos que nada usa —y que además
 * hacían creer que la app le calcularía su propia declaración.
 *
 * Ver `docs/decisiones-nomina.md` §D21 para la consecuencia: la app ya no
 * calcula las obligaciones fiscales propias del despacho.
 */

import { labelStyle } from './styles';

interface StepDatosDespachoProps {
  nombre: string;
  setNombre: (v: string) => void;
  nombreDespacho: string;
  setNombreDespacho: (v: string) => void;
  telefono: string;
  setTelefono: (v: string) => void;
}

export default function StepDatosDespacho({
  nombre, setNombre, nombreDespacho, setNombreDespacho, telefono, setTelefono,
}: StepDatosDespachoProps) {
  return (
    <div>
      <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 8 }}>
        Datos del despacho
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 32 }}>
        Con esto basta. Los datos fiscales que se usan para calcular son los de cada
        cliente, no los del despacho.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div>
          <label style={labelStyle}>
            Nombre del contador <span style={{ color: 'var(--danger)' }}>*</span>
          </label>
          <input
            className="input-field"
            placeholder="Tu nombre completo"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
          />
        </div>
        <div>
          <label style={labelStyle}>
            Nombre del despacho <span style={{ color: 'var(--danger)' }}>*</span>
          </label>
          <input
            className="input-field"
            placeholder="Despacho Contable Ejemplo"
            value={nombreDespacho}
            onChange={(e) => setNombreDespacho(e.target.value)}
          />
        </div>
        <div>
          <label style={labelStyle}>
            Telefono <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(opcional)</span>
          </label>
          <input
            className="input-field"
            placeholder="10 digitos"
            value={telefono}
            onChange={(e) => setTelefono(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
