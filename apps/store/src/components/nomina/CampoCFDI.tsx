/**
 * Un campo de captura del CFDI de nómina (T4).
 *
 * Existe aparte porque `PanelCFDINomina` pinta **once** campos entre el patrón
 * y cada trabajador, y el `<label>` + `<input>` repetido once veces se come el
 * archivo entero. Es presentacional: no sabe qué campo es ni valida nada.
 *
 * `faltante` lo pinta con borde de advertencia. **No es un error**: es un dato
 * que el modelo de la cartera todavía no guarda y que el CFDI exige, así que la
 * pantalla lo señala en vez de dejar que el operador descubra el 422 al final.
 */

import { campoInput, etiquetaCampo } from '../cartera/estilosCampo';

interface Props {
  etiqueta: string;
  valor: string;
  onChange: (valor: string) => void;
  /** Lo que el SAT espera, en corto: `XAXX010101000`, `91090`, `VER`… */
  ejemplo?: string;
  faltante?: boolean;
  maxLength?: number;
  /**
   * Teclear en minúsculas un RFC o una CURP y que el XML los lleve así es un
   * rechazo del PAC, así que se suben a mayúsculas mientras se escribe. **La
   * razón social se exceptúa**: transformarle el nombre a alguien en silencio
   * es la misma clase de cambio que `layoutImss.ts` documenta para "MUÑOZ".
   */
  mayusculas?: boolean;
}

export default function CampoCFDI({
  etiqueta,
  valor,
  onChange,
  ejemplo,
  faltante,
  maxLength,
  mayusculas = true,
}: Props) {
  return (
    <label style={{ display: 'block' }}>
      <span style={etiquetaCampo}>{etiqueta}</span>
      <input
        className="input-field"
        aria-label={etiqueta}
        value={valor}
        maxLength={maxLength}
        placeholder={ejemplo}
        onChange={(e) => onChange(mayusculas ? e.target.value.toUpperCase() : e.target.value)}
        style={{
          ...campoInput,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '0.8rem',
          borderColor: faltante ? 'var(--warning-border)' : 'var(--border)',
        }}
      />
    </label>
  );
}
