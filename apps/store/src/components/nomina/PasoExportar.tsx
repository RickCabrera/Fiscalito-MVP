/**
 * Paso 4 de la nómina: PDF, TXT para el IMSS y el banco, y XML del CFDI sin timbrar.
 *
 * Salió de `NominaClientePage` por el tope de 300 líneas (P4). El orden importa: el PDF
 * es el documento que leen el contador y el patrón; los TXT son para las máquinas (O-04);
 * el XML va al final porque es lo menos terminado (T4).
 */

import { FileDown } from 'lucide-react';
import type { EmpleadoCartera } from '../../services/carteraApi';
import type { ClienteDetalle } from '../../services/despachoApi';
import type { NominaPeriodo } from '../../services/nominaDemoApi';
import { exportarNominaPDF } from '../../services/pdfExportNomina';
import PanelCFDINomina from './PanelCFDINomina';
import PasoNomina, { type EstadoPaso } from './PasoNomina';
import SelectorExportacion from './SelectorExportacion';

const ACCION: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 8 };

export default function PasoExportar({
  estado,
  nomina,
  cliente,
  empleados,
  registroPatronal,
  guia,
  sinVincular,
}: {
  estado: EstadoPaso;
  nomina: NominaPeriodo | null;
  cliente: ClienteDetalle | null;
  empleados: EmpleadoCartera[];
  registroPatronal: string;
  guia: string;
  sinVincular: number;
}) {
  // Guarda propia, no sólo `disabled`: el botón se renderiza siempre (E-06).
  const exportar = () => {
    if (!nomina || !cliente) return;
    exportarNominaPDF(nomina, cliente, sinVincular);
  };

  return (
    <PasoNomina
      numero={4}
      titulo="Exportar"
      descripcion="El PDF con los recibos y las cuotas, los archivos TXT para el IMSS y el banco, y el XML del CFDI de nómina sin timbrar."
      estado={estado}
      motivoBloqueo="Calcula la nómina primero (paso 3)."
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
        <div>
          <button className="btn-secondary" onClick={exportar} disabled={!nomina || !cliente} style={ACCION}>
            <FileDown size={16} /> Exportar PDF
          </button>
        </div>
        <SelectorExportacion
          deshabilitado={!nomina || !cliente}
          datos={nomina && cliente ? { nomina, cliente, empleados, registroPatronal, guia } : null}
        />
        <PanelCFDINomina
          nomina={nomina}
          cliente={cliente}
          empleados={empleados}
          registroPatronal={registroPatronal}
          deshabilitado={!nomina || !cliente}
        />
      </div>
    </PasoNomina>
  );
}
