/**
 * EL CUADRE: los importes de cada TXT cuadran al centavo con el PDF. (O-04)
 *
 * POR QUÉ ESTE ARCHIVO ESTÁ ESCRITO ASÍ, Y NO DE LA FORMA OBVIA
 * --------------------------------------------------------------
 * La forma obvia —hacer que el PDF y los TXT tomen sus totales de un módulo
 * común y compararlos entre sí— es **tautológica**, y un revisor lo bloqueó en
 * el plan antes de que se escribiera una línea: si los dos lados derivan del
 * mismo cálculo del front, la comparación sólo puede fallar cuando un generador
 * escribe el campo en la posición equivocada. **Un error en la suma pasa verde
 * en los dos lados.**
 *
 * Aquí hay TRES puntos, y el tercero no depende del navegador:
 *
 * 1. **Los bytes emitidos**, parseados de vuelta. No el objeto de dominio: se
 *    lee lo que de verdad se escribió, igual que F1-05 hizo con el XML —
 *    comparar propiedades del recibo contra sí mismas deja pasar un generador
 *    que escriba el atributo equivocado.
 * 2. **Lo que el PDF imprime**, capturado espiando `jspdf-autotable`: las filas
 *    que recibe son literalmente las que salen en el papel.
 * 3. **Los totales del MOTOR** (`total_percepciones`, `total_neto`,
 *    `total_isr`), que viajan en la respuesta desde O-04 y que ningún código
 *    del front produce.
 *
 * TODO SE COMPARA EN CENTAVOS ENTEROS
 * -----------------------------------
 * Nunca en `Number`. Un test que sume floats y compare "al centavo" es flaky
 * por construcción, y el criterio de la tarea es literalmente "totales
 * idénticos".
 *
 * LO QUE ESTE ARCHIVO **NO** PRUEBA
 * ---------------------------------
 * Que los layouts de los tres bancos sean correctos. No hay fuente publicada
 * contra la cual medirlos y están marcados `por-validar`. Lo que sí queda
 * medido de ellos son **los importes**: el neto que dispersan es, al centavo, el
 * mismo que el motor calculó. Si el layout está mal, el banco rechaza el
 * archivo; si el importe estuviera mal, pagaría de más o de menos.
 */

import { describe, expect, it, vi } from 'vitest';
import type { ClienteDetalle } from '../despachoApi';
import type { EmpleadoCartera } from '../carteraApi';
import type { NominaPeriodo, ReciboNomina } from '../nominaDemoApi';
import { aCentavos, sumaCentavos } from './dinero';
import { FORMATOS } from './registro';
import type { DatosExportacion } from './tipos';

/** Las filas que el PDF manda a `autoTable`: lo que sale impreso. */
const filasDelPdf: unknown[][] = [];
vi.mock('jspdf-autotable', () => ({
  default: (_doc: unknown, opciones: { body?: unknown[][] }) => {
    if (opciones.body) filasDelPdf.push(...opciones.body);
  },
}));

vi.mock('jspdf', () => {
  class FakeDoc {
    internal = { pageSize: { getWidth: () => 216, getHeight: () => 279 }, pages: [1] };
    lastAutoTable = { finalY: 100 };
    setFont() { return this; }
    setFontSize() { return this; }
    setTextColor() { return this; }
    setFillColor() { return this; }
    setDrawColor() { return this; }
    setPage() { return this; }
    getNumberOfPages() { return 1; }
    rect() { return this; }
    line() { return this; }
    addPage() { return this; }
    save() { return this; }
    text() { return this; }
    splitTextToSize(t: string) { return [t]; }
  }
  return { default: FakeDoc };
});

const { exportarNominaPDF } = await import('../pdfExportNomina');

// ── El cálculo, con importes que NO son redondos a propósito ──────────────

function recibo(
  no: string,
  nombre: string,
  sbc: string,
  percepciones: string,
  isr: string,
  obrera: string,
  patronal: string,
  neto: string,
): ReciboNomina {
  return {
    empleado_no: no,
    nombre,
    sbc,
    es_salario_minimo: false,
    dias_periodo: 16,
    dias_ausentismo: 0,
    dias_pagados: 16,
    percepciones: [],
    deducciones: [
      {
        tipo: '002', clave: '002', concepto: 'ISR', importe: isr,
        gravado: null, exento: null, subsidio_causado: null,
      },
      {
        tipo: '001', clave: '001', concepto: 'IMSS', importe: obrera,
        gravado: null, exento: null, subsidio_causado: null,
      },
    ],
    otros_pagos: [],
    total_percepciones: percepciones,
    total_deducciones: String(
      (aCentavos(isr) + aCentavos(obrera)) / 100,
    ),
    neto,
    cuota_obrera: obrera,
    cuota_patronal: patronal,
    absorbio_cuota_obrera: false,
    ramos: [],
  };
}

/**
 * Tres empleados con centavos que no cuadran a la primera.
 *
 * `5056.07 + 4838.93 + 3211.11` da un total cuyo tercer decimal habría que
 * redondear si alguien sumara en float — que es exactamente lo que este archivo
 * existe para impedir.
 */
const RECIBOS = [
  recibo('E-01', 'PERSONA UNA', '331.58', '5056.07', '34.68', '125.99', '600.11', '4895.40'),
  recibo('E-02', 'MUÑOZ PÉREZ', '412.33', '4838.93', '128.07', '140.03', '712.45', '4570.83'),
  recibo('E-03', 'PERSONA TRES', '524.65', '3211.11', '0.00', '99.01', '455.09', '3112.10'),
];

/** Los totales del MOTOR. Se calculan aquí una vez y no se re-derivan. */
const TOTAL_PERCEPCIONES = '13106.11';
const TOTAL_ISR = '162.75';
const TOTAL_NETO = '12578.33';

const NOMINA: NominaPeriodo = {
  cliente: 'empresa',
  periodo: { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' },
  fecha_pago_efectiva: '2026-08-31',
  origen_plantilla: 'request',
  recibos: RECIBOS,
  porcion_mensual: {
    periodicidad: 'mensual', por_ramo: {},
    total_patron: '1767.65', total_obrero: '365.03', total: '2132.68', empleados: 3,
  },
  porcion_bimestral: {
    periodicidad: 'bimestral', por_ramo: {},
    total_patron: '0.00', total_obrero: '0.00', total: '0.00', empleados: 3,
  },
  total_percepciones: TOTAL_PERCEPCIONES,
  total_neto: TOTAL_NETO,
  total_isr: TOTAL_ISR,
  advertencias: [],
};

const CLIENTE: ClienteDetalle = {
  id: 'empresa',
  nombre: 'Orca Ordorica Cristal Templado',
  giro: '',
  origen: 'propio',
  num_empleados: 3,
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
    nss: nss,
    employee_no: no,
    enrolamiento: 'enrolado',
  };
}

const DATOS: DatosExportacion = {
  nomina: NOMINA,
  cliente: CLIENTE,
  empleados: [
    empleado('E-01', 'PERSONA UNA PRIMERA', '01010101011'),
    empleado('E-02', 'MUÑOZ PÉREZ JOSÉ', '02020202022'),
    empleado('E-03', 'PERSONA TRES TERCERA', '03030303033'),
  ],
  registroPatronal: 'A1234567890',
  guia: '00001',
};

function texto(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => String.fromCharCode(b)).join('');
}

// ── Punto 3: el ancla que NO viene del front ──────────────────────────────

describe('los totales del motor son consistentes consigo mismos', () => {
  /**
   * Se comprueba primero que la fixture sea coherente. Sin esto, un error en
   * los números de arriba haría fallar los tres formatos y parecería un bug de
   * los exportadores.
   */
  it('la fixture cuadra: los totales son la suma de los recibos', () => {
    expect(aCentavos(TOTAL_PERCEPCIONES)).toBe(
      sumaCentavos(RECIBOS.map((r) => r.total_percepciones)),
    );
    expect(aCentavos(TOTAL_NETO)).toBe(sumaCentavos(RECIBOS.map((r) => r.neto)));
    expect(aCentavos(TOTAL_ISR)).toBe(
      sumaCentavos(RECIBOS.map((r) => r.deducciones.find((d) => d.tipo === '002')!.importe)),
    );
  });
});

// ── Punto 2: lo que el PDF imprime ────────────────────────────────────────

describe('el PDF imprime los importes del motor', () => {
  it('la suma de sus filas cuadra al centavo con `total_percepciones` y `total_neto`', () => {
    filasDelPdf.length = 0;
    exportarNominaPDF(NOMINA, CLIENTE, 0);

    // La tabla de recibos: [nombre, SBC, días, percepciones, ISR, obrera, neto].
    const deRecibos = filasDelPdf.filter((f) => f.length === 7);
    expect(deRecibos).toHaveLength(3);

    const aCent = (s: unknown) => aCentavos(String(s).replace(/[$,]/g, ''));
    expect(deRecibos.reduce((a, f) => a + aCent(f[3]), 0)).toBe(
      aCentavos(TOTAL_PERCEPCIONES),
    );
    expect(deRecibos.reduce((a, f) => a + aCent(f[6]), 0)).toBe(aCentavos(TOTAL_NETO));
    expect(deRecibos.reduce((a, f) => a + aCent(f[4]), 0)).toBe(aCentavos(TOTAL_ISR));
  });
});

// ── Punto 1: los bytes de cada TXT ────────────────────────────────────────

describe('el formato genérico cuadra al centavo con el motor', () => {
  const generico = FORMATOS.find((f) => f.id === 'generico')!;

  it('sus renglones suman exactamente los totales del motor', () => {
    const archivo = generico.generar(DATOS);
    const lineas = texto(archivo.bytes).trim().split('\r\n');
    // Encabezado + 3 empleados + TOTAL.
    expect(lineas).toHaveLength(5);

    const datos = lineas.slice(1, -1).map((l) => l.split('|'));
    expect(datos.reduce((a, c) => a + aCentavos(c[5]), 0)).toBe(
      aCentavos(TOTAL_PERCEPCIONES),
    );
    expect(datos.reduce((a, c) => a + aCentavos(c[7]), 0)).toBe(aCentavos(TOTAL_ISR));
    expect(datos.reduce((a, c) => a + aCentavos(c[10]), 0)).toBe(aCentavos(TOTAL_NETO));
  });

  it('y su renglón TOTAL es el del motor, no una suma del front', () => {
    const archivo = generico.generar(DATOS);
    const _renglones_total = texto(archivo.bytes).trim().split('\r\n');
    const total = _renglones_total[_renglones_total.length - 1].split('|');
    expect(total[0]).toBe('TOTAL');
    expect(total[5]).toBe(TOTAL_PERCEPCIONES);
    expect(total[7]).toBe(TOTAL_ISR);
    expect(total[10]).toBe(TOTAL_NETO);
  });
});

describe('la dispersión bancaria cuadra al centavo con el motor', () => {
  /**
   * El LAYOUT está por validar; **los importes no**. Si el layout está mal, el
   * banco rechaza el archivo. Si el importe estuviera mal, pagaría de más o de
   * menos — y de eso sí hay garantía.
   */
  const conCuenta: DatosExportacion = {
    ...DATOS,
    empleados: DATOS.empleados.map((e) => ({
      ...e,
      cuenta_bancaria: `0123456789${e.empleado_no.slice(-1)}`,
    })) as EmpleadoCartera[],
  };

  it.each(['dispersion-bbva', 'dispersion-banamex', 'dispersion-banorte'])(
    '%s: la suma de los netos dispersados es la del motor',
    (id) => {
      const formato = FORMATOS.find((f) => f.id === id)!;
      const archivo = formato.generar(conCuenta);
      const lineas = texto(archivo.bytes).trim().split('\r\n');
      expect(lineas).toHaveLength(3);

      // El importe va en centavos, sin punto: se lee del propio archivo.
      const anchos = { 'dispersion-bbva': [20, 15], 'dispersion-banamex': [18, 13], 'dispersion-banorte': [20, 12] };
      const [cuenta, importe] = anchos[id as keyof typeof anchos];
      const suma = lineas.reduce(
        (a, l) => a + Number(l.slice(cuenta, cuenta + importe)),
        0,
      );
      expect(suma).toBe(aCentavos(TOTAL_NETO));
    },
  );
});

describe('el archivo del IMSS cuadra su SBC con el del recibo', () => {
  /**
   * El único importe del layout afiliatorio es el SBC. Cuadra contra el del
   * RECIBO —el que se usó para calcular las cuotas de este periodo— y no contra
   * el de la ficha: el archivo tiene que decir lo mismo que el PDF.
   */
  const formato = FORMATOS.find((f) => f.id === 'imss')!;

  it('el SBC de cada renglón es el del recibo, con decimal implícito', () => {
    const archivo = formato.generar(DATOS);
    const lineas = texto(archivo.bytes).trim().split('\r\n');
    // Tres altas (todas con `fecha_alta` dentro del periodo) + cifras de control.
    expect(lineas).toHaveLength(4);

    const movimientos = lineas.slice(0, 3);
    const sbcs = movimientos.map((l) => Number(l.slice(103, 109)));
    expect(sbcs).toEqual(RECIBOS.map((r) => aCentavos(r.sbc)));
  });

  it('la suma de los SBC declarados es la de los recibos', () => {
    const archivo = formato.generar(DATOS);
    const lineas = texto(archivo.bytes).trim().split('\r\n').slice(0, 3);
    const suma = lineas.reduce((a, l) => a + Number(l.slice(103, 109)), 0);
    expect(suma).toBe(sumaCentavos(RECIBOS.map((r) => r.sbc)));
  });
});

// ── La forma del archivo, que el IMSS rechaza si falla ────────────────────

describe('el archivo del IMSS tiene la forma que el layout exige', () => {
  const formato = FORMATOS.find((f) => f.id === 'imss')!;

  it('cada renglón mide EXACTAMENTE 168 posiciones', () => {
    const archivo = formato.generar(DATOS);
    for (const linea of texto(archivo.bytes).trim().split('\r\n')) {
      expect(linea).toHaveLength(168);
    }
  });

  it('ningún byte pasa de 127: es ASCII, no UTF-8', () => {
    // "MUÑOZ PÉREZ" está en la fixture a propósito. Un byte alto en un campo
    // que el IMSS lee como ASCII es un archivo rechazado.
    const archivo = formato.generar(DATOS);
    expect(Math.max(...Array.from(archivo.bytes))).toBeLessThanOrEqual(127);
  });

  it('y lo transliterado se REPORTA, no se hace callando', () => {
    /**
     * "MUÑOZ" → "MUNOZ" en un movimiento afiliatorio no es una decisión de
     * codificación: es un cambio de apellido. La pantalla lo lista antes de
     * descargar.
     */
    const archivo = formato.generar(DATOS);
    expect(archivo.transliterados.length).toBeGreaterThan(0);
    expect(archivo.transliterados.join(' ')).toMatch(/MUÑOZ/);
  });

  it('el terminador es CR+LF', () => {
    const archivo = formato.generar(DATOS);
    expect(texto(archivo.bytes)).toContain('\r\n');
    expect(texto(archivo.bytes).endsWith('\r\n')).toBe(true);
  });

  it('las cifras de control cuentan los renglones QUE SE EMITIERON', () => {
    const archivo = formato.generar(DATOS);
    const _renglones_control = texto(archivo.bytes).trim().split('\r\n');
    const control = _renglones_control[_renglones_control.length - 1];
    expect(control.slice(0, 13)).toBe('*************');
    expect(Number(control.slice(56, 62))).toBe(3);
    expect(control.slice(167, 168)).toBe('9');
  });

  it('un empleado sin NSS no se emite, y sale en no exportables', () => {
    const sinNss: DatosExportacion = {
      ...DATOS,
      empleados: DATOS.empleados.map((e, i) => (i === 0 ? { ...e, nss: '' } : e)),
    };
    const archivo = formato.generar(sinNss);
    const lineas = texto(archivo.bytes).trim().split('\r\n');

    expect(lineas).toHaveLength(3); // dos altas + control
    expect(Number(lineas[lineas.length - 1].slice(56, 62))).toBe(2);
    expect(archivo.noExportables).toHaveLength(1);
    expect(archivo.noExportables[0].motivo).toMatch(/el NSS/);
  });

  it('los no exportables NO se escriben dentro del archivo', () => {
    /**
     * Un layout de longitud fija no admite un pie en prosa —rompería las 168
     * posiciones— y además metería nombres de personas dentro del documento que
     * se presenta al IMSS. Van sólo en pantalla.
     */
    const sinNss: DatosExportacion = {
      ...DATOS,
      empleados: DATOS.empleados.map((e, i) => (i === 0 ? { ...e, nss: '' } : e)),
    };
    const archivo = formato.generar(sinNss);
    expect(texto(archivo.bytes)).not.toMatch(/NSS/);
    expect(texto(archivo.bytes)).not.toMatch(/PERSONA UNA/);
  });
});

// ── Que cada formato declare su fuente ────────────────────────────────────

describe('todo formato declara su fuente o su estado "por validar"', () => {
  it.each(FORMATOS.map((f) => [f.id, f] as const))('%s', (_id, formato) => {
    expect(['oficial', 'por-validar']).toContain(formato.fuente.estado);
    expect(formato.fuente.cita.length).toBeGreaterThan(40);
  });

  it('los tres bancos están marcados POR VALIDAR, y el del IMSS no', () => {
    const porValidar = FORMATOS.filter((f) => f.fuente.estado === 'por-validar');
    expect(porValidar.map((f) => f.id).sort()).toEqual([
      'dispersion-banamex',
      'dispersion-banorte',
      'dispersion-bbva',
    ]);
    expect(FORMATOS.find((f) => f.id === 'imss')!.fuente.estado).toBe('oficial');
  });

  it('el archivo de un formato por validar lo dice en su NOMBRE', () => {
    // Quien lo encuentre en Descargas dentro de tres meses tiene que saberlo
    // sin abrir la app.
    const bbva = FORMATOS.find((f) => f.id === 'dispersion-bbva')!;
    expect(bbva.generar(DATOS).nombre).toMatch(/PORVALIDAR/);
  });
});

describe('sin los datos del patrón el archivo NO se emite', () => {
  /**
   * El registro patronal y la guía van en **cada renglón** y los asigna el
   * IMSS. Un archivo con esos campos en blanco lo rechaza el IMSS entero y
   * **sin decir cuál de los dos faltaba**, así que el error tiene que salir
   * aquí, con el nombre del campo y dónde se captura.
   *
   * Es el mismo criterio que el resto del módulo: levantar en vez de emitir
   * algo que parece un archivo y no lo es.
   */
  const formato = FORMATOS.find((f) => f.id === 'imss')!;

  it('sin registro patronal levanta, diciendo dónde se captura', () => {
    expect(() => formato.generar({ ...DATOS, registroPatronal: '' })).toThrow(
      /Configuración de empresa/,
    );
  });

  it('con un registro patronal de 10 también: falta el dígito verificador', () => {
    // El error clásico: se teclea el registro y se olvida el verificador.
    expect(() => formato.generar({ ...DATOS, registroPatronal: 'A123456789' })).toThrow(
      /11 caracteres/,
    );
  });

  it('sin guía de la subdelegación levanta', () => {
    expect(() => formato.generar({ ...DATOS, guia: '' })).toThrow(/guía de la subdelegación/);
  });
});

describe('truncar está prohibido', () => {
  /**
   * Cortar un apellido produce un movimiento afiliatorio sobre alguien que no
   * es; cortar un NSS, sobre nadie. Y las dos cosas pasan en silencio: el
   * archivo mide 168 posiciones igual y el IMSS lo acepta.
   */
  const formato = FORMATOS.find((f) => f.id === 'imss')!;

  it('un apellido de más de 27 posiciones LEVANTA en vez de recortarse', () => {
    const largo = 'APELLIDOEXTREMADAMENTELARGOQUENOCABE';
    expect(largo.length).toBeGreaterThan(27);
    const datos: DatosExportacion = {
      ...DATOS,
      empleados: DATOS.empleados.map((e, i) =>
        i === 0 ? { ...e, apellido_paterno: largo } : e,
      ),
    };
    expect(() => formato.generar(datos)).toThrow(/no cabe en el campo/);
  });
});
