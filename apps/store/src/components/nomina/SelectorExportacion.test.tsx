/**
 * El paso 4 tiene que DECIR tres cosas antes de que el archivo salga. (O-04)
 *
 * `cuadre.test.ts` prueba que los importes cuadren al centavo. Esto prueba lo
 * otro: que el operador **vea** lo que está a punto de mandarle al IMSS o a su
 * banco. Las tres son afirmaciones sobre el mundo, no adornos de UI:
 *
 * 1. Un layout `por-validar` lo dice **antes** de descargarse. Mandarle a un
 *    banco un archivo con el orden de campos sin confirmar y que el operador
 *    crea que está respaldado es el modo de falla caro de esta pantalla.
 * 2. Quien quedó fuera, sale con nombre y razón. Un empleado sin NSS no se
 *    exporta, y si eso pasa en silencio se presenta una nómina incompleta ante
 *    el IMSS sin que nadie se entere.
 * 3. Qué apellidos se cambiaron al transliterar a ASCII. Quitarle la eñe a un
 *    apellido en un movimiento afiliatorio es un cambio en un documento de
 *    identidad laboral.
 *
 * Y una cuarta, la que evita el desastre callado: cuando el generador
 * **levanta** —porque falta el registro patronal, o porque un apellido no cabe
 * en su campo— la pantalla enseña el error y **no descarga nada**. Un archivo a
 * medias mide 168 posiciones igual y el IMSS lo acepta.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import SelectorExportacion from './SelectorExportacion';
import { FORMATOS } from '../../services/exportadores/registro';
import type { DatosExportacion } from '../../services/exportadores/tipos';
import type { ClienteDetalle } from '../../services/despachoApi';
import type { EmpleadoCartera } from '../../services/carteraApi';
import type { NominaPeriodo, ReciboNomina } from '../../services/nominaDemoApi';

// ── Fixture mínima: un periodo con tres personas ──────────────────────────
//
// Deliberadamente NO se importa la de `cuadre.test.ts`. Un fixture compartido
// entre dos archivos de prueba hace que arreglar uno rompa el otro, y aquí
// hacen falta cosas que allá no: alguien sin NSS y alguien con eñe.

function recibo(no: string, nombre: string): ReciboNomina {
  return {
    empleado_no: no,
    nombre,
    sbc: '412.33',
    es_salario_minimo: false,
    dias_periodo: 16,
    dias_ausentismo: 0,
    dias_pagados: 16,
    percepciones: [],
    deducciones: [
      {
        tipo: '002', clave: '002', concepto: 'ISR', importe: '100.00',
        gravado: null, exento: null, subsidio_causado: null,
      },
    ],
    otros_pagos: [],
    total_percepciones: '5000.00',
    total_deducciones: '100.00',
    neto: '4900.00',
    cuota_obrera: '0.00',
    cuota_patronal: '0.00',
    absorbio_cuota_obrera: false,
    ramos: [],
  };
}

const NOMINA: NominaPeriodo = {
  cliente: 'empresa',
  periodo: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
  fecha_pago_efectiva: '2026-08-31',
  origen_plantilla: 'request',
  recibos: [recibo('E-01', 'MUÑOZ PÉREZ JOSÉ'), recibo('E-02', 'PERSONA DOS SEGUNDA')],
  porcion_mensual: {
    periodicidad: 'mensual', por_ramo: {},
    total_patron: '0.00', total_obrero: '0.00', total: '0.00', empleados: 2,
  },
  porcion_bimestral: {
    periodicidad: 'bimestral', por_ramo: {},
    total_patron: '0.00', total_obrero: '0.00', total: '0.00', empleados: 2,
  },
  total_percepciones: '10000.00',
  total_neto: '9800.00',
  total_isr: '200.00',
  advertencias: [],
};

const CLIENTE: ClienteDetalle = {
  id: 'empresa',
  nombre: 'Orca Ordorica Cristal Templado',
  giro: '',
  origen: 'propio',
  num_empleados: 2,
  prima_riesgo: '0.0113065',
  clase_riesgo: 3,
  clave_periodicidad: '04',
  zona: 'general',
  fecha_referencia: '',
  empleados: [],
  periodo_sugerido: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
};

function empleado(no: string, nombre: string, nss: string): EmpleadoCartera {
  const [paterno, materno, ...pila] = nombre.split(' ');
  return {
    empleado_no: no,
    nombre,
    apellido_paterno: paterno,
    apellido_materno: materno,
    nombres: pila.join(' ') || 'NOMBRE',
    puesto: '',
    salario_diario: '400.00',
    salario_diario_integrado: '420.00',
    zona: 'general',
    fecha_alta: '2026-08-20',
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss,
    employee_no: no,
    enrolamiento: 'enrolado',
  };
}

const DATOS: DatosExportacion = {
  nomina: NOMINA,
  cliente: CLIENTE,
  empleados: [
    // Con eñe y acentos: se va a transliterar, y la pantalla tiene que decirlo.
    empleado('E-01', 'MUÑOZ PÉREZ JOSÉ', '01010101011'),
    // Sin NSS: no se exporta, y la pantalla tiene que decir quién y por qué.
    empleado('E-02', 'PERSONA DOS SEGUNDA', ''),
  ],
  registroPatronal: 'A1234567890',
  guia: '00001',
};

const ID_IMSS = 'imss';
const ID_BANCO = FORMATOS.find((f) => f.fuente.estado === 'por-validar')!.id;

/** Elige un formato en el `<select>` del paso 4. */
function elegir(id: string): void {
  fireEvent.change(screen.getByLabelText('Formato de exportación'), { target: { value: id } });
}

function exportar(): void {
  fireEvent.click(screen.getByRole('button', { name: /Exportar TXT/ }));
}

let descargas: string[];
let click: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  descargas = [];
  // jsdom no implementa ninguna de las dos.
  URL.createObjectURL = vi.fn(() => 'blob:x');
  URL.revokeObjectURL = vi.fn();
  click = vi
    .spyOn(HTMLAnchorElement.prototype, 'click')
    .mockImplementation(function (this: HTMLAnchorElement) {
      descargas.push(this.download);
    });
});

afterEach(() => {
  // El setup del repo no activa `globals`, así que RTL no registra su
  // auto-limpieza: sin esto el DOM se acumula entre pruebas y `getByRole`
  // encuentra dos botones.
  cleanup();
  click.mockRestore();
});

describe('el selector se pinta desde FORMATOS, no de una lista aparte', () => {
  /**
   * El punto de extensión documentado dice que agregar un formato es un archivo
   * y un renglón en `registro.ts`. Si el selector tuviera su propia lista, esa
   * promesa sería falsa y el formato nuevo no aparecería.
   */
  it('aparecen TODOS los formatos registrados', () => {
    render(<SelectorExportacion datos={DATOS} deshabilitado={false} />);
    const opciones = screen
      .getAllByRole('option')
      .map((o) => (o as HTMLOptionElement).value);
    expect(opciones).toEqual(FORMATOS.map((f) => f.id));
  });

  it('los "por validar" se marcan en la propia lista, sin abrir nada', () => {
    render(<SelectorExportacion datos={DATOS} deshabilitado={false} />);
    for (const formato of FORMATOS) {
      const opcion = screen
        .getAllByRole('option')
        .find((o) => (o as HTMLOptionElement).value === formato.id)!;
      // La marca cuelga de `fuente.estado`, no de una lista de ids a mano: un
      // formato nuevo sin fuente nace marcado.
      expect(/por validar/.test(opcion.textContent ?? '')).toBe(
        formato.fuente.estado === 'por-validar',
      );
    }
  });
});

describe('un layout sin fuente publicada lo dice ANTES de descargarse', () => {
  it('el formato oficial NO trae la advertencia de "por validar"', () => {
    render(<SelectorExportacion datos={DATOS} deshabilitado={false} />);
    elegir(ID_IMSS);
    expect(screen.queryByText(/Por validar contra el manual vigente del banco/)).toBeNull();
  });

  it('el layout bancario SÍ la trae, y sin haber exportado todavía', () => {
    render(<SelectorExportacion datos={DATOS} deshabilitado={false} />);
    elegir(ID_BANCO);
    expect(screen.getByText(/Por validar contra el manual vigente del banco/)).toBeTruthy();
    // Sin clicks: la advertencia es previa a la descarga, no un reporte de ella.
    expect(descargas).toEqual([]);
  });
});

describe('quien queda fuera sale con nombre y razón', () => {
  it('el empleado sin NSS se nombra después de exportar', () => {
    render(<SelectorExportacion datos={DATOS} deshabilitado={false} />);
    elegir(ID_IMSS);
    exportar();
    expect(screen.getByText(/PERSONA DOS SEGUNDA/)).toBeTruthy();
    expect(screen.getByText(/el NSS/)).toBeTruthy();
  });

  it('el archivo sí se descarga: quedar fuera no cancela la exportación', () => {
    // El archivo con los demás es válido y útil; lo que no puede pasar es que
    // el faltante se vaya en silencio.
    render(<SelectorExportacion datos={DATOS} deshabilitado={false} />);
    elegir(ID_IMSS);
    exportar();
    expect(descargas).toHaveLength(1);
  });
});

describe('los apellidos que se cambiaron se listan', () => {
  it('MUÑOZ PÉREZ aparece en el aviso de transliteración', () => {
    render(<SelectorExportacion datos={DATOS} deshabilitado={false} />);
    elegir(ID_IMSS);
    exportar();
    expect(screen.getByText(/Se quitaron acentos y eñes/)).toBeTruthy();
    expect(screen.getByText(/MUÑOZ PÉREZ JOSÉ/)).toBeTruthy();
  });
});

describe('cuando el generador levanta, no sale archivo', () => {
  /**
   * Es la mitad que importa. Los generadores levantan en vez de truncar
   * —un apellido cortado es un movimiento sobre otra persona— y esa decisión no
   * sirve de nada si la pantalla se traga la excepción y descarga igual.
   */
  it('sin registro patronal: se pinta el error y NO se descarga nada', () => {
    render(
      <SelectorExportacion datos={{ ...DATOS, registroPatronal: '' }} deshabilitado={false} />,
    );
    elegir(ID_IMSS);
    exportar();
    expect(screen.getByRole('alert').textContent).toMatch(/Configuración de empresa/);
    expect(descargas).toEqual([]);
  });

  it('el error se limpia al cambiar de formato, en vez de quedarse pegado', () => {
    render(
      <SelectorExportacion datos={{ ...DATOS, registroPatronal: '' }} deshabilitado={false} />,
    );
    elegir(ID_IMSS);
    exportar();
    expect(screen.queryByRole('alert')).not.toBeNull();
    elegir(ID_BANCO);
    // Un error del formato anterior colgado sobre otro formato dice que este
    // también falló, y no es cierto.
    expect(screen.queryByRole('alert')).toBeNull();
  });
});

describe('sin periodo calculado o con el paso bloqueado, el botón no exporta', () => {
  /**
   * El handler trae su propia guarda (`if (!datos || deshabilitado) return;`),
   * pero **no se puede alcanzar desde la UI**: en los dos casos el botón va
   * `disabled`, y React no invoca `onClick` sobre un control deshabilitado. Se
   * comprobó con mutación —quitarle la guarda al handler no mata ningún test— y
   * en vez de fabricar un disparo artificial que la alcance, aquí se afirma **lo
   * que de verdad protege al operador**: que el botón está apagado.
   *
   * Por eso cada prueba mide las dos mitades. Sólo "no hubo descarga" pasaría
   * igual si alguien borrara el `disabled`, porque la guarda del handler
   * atajaría en silencio; y sólo "está deshabilitado" no dice que no se exportó.
   */
  function boton(): HTMLButtonElement {
    return screen.getByRole('button', { name: /Exportar TXT/ }) as HTMLButtonElement;
  }

  it('con el paso bloqueado: apagado, y sin descarga', () => {
    render(<SelectorExportacion datos={DATOS} deshabilitado />);
    expect(boton().disabled).toBe(true);
    exportar();
    expect(descargas).toEqual([]);
  });

  it('sin datos del periodo: apagado, y sin descarga', () => {
    render(<SelectorExportacion datos={null} deshabilitado={false} />);
    expect(boton().disabled).toBe(true);
    exportar();
    expect(descargas).toEqual([]);
  });
});
