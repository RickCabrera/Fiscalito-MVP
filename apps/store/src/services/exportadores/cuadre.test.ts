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
  /**
   * Las cuotas van PARTIDAS en dos porciones, y la bimestral NO es cero.
   *
   * Se entera en fechas distintas —EyM, RT y guardería son mensuales; Retiro,
   * CEAV e Infonavit, bimestrales— y por eso la respuesta las manda separadas.
   * Pero `recibo.cuota_obrera` trae **la suma de las dos**, y el motor define el
   * total igual.
   *
   * Con la bimestral en ceros, un exportador que sumara sólo la mensual daba el
   * mismo número y el error era invisible: es justo el defecto que el revisor
   * del cuadre encontró en el renglón TOTAL del genérico. La fixture lo hace
   * imposible.
   */
  porcion_mensual: {
    periodicidad: 'mensual', por_ramo: {},
    total_patron: '1267.65', total_obrero: '265.03', total: '1532.68', empleados: 3,
  },
  porcion_bimestral: {
    periodicidad: 'bimestral', por_ramo: {},
    total_patron: '500.00', total_obrero: '100.00', total: '600.00', empleados: 3,
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

/**
 * La misma plantilla, con cuenta bancaria inventada.
 *
 * `cuenta_bancaria` **no existe en `EmpleadoCartera`** —ni en el backend, ni en
 * ninguna pantalla— y por eso hace falta el cast. **Eso es el hallazgo, no un
 * detalle del test:** en un periodo real ningún empleado la tiene, así que la
 * dispersión no exporta a nadie. Lo que se mide aquí es que **los importes**
 * cuadren el día que el dato exista; que hoy no exista se prueba aparte, y el
 * generador levanta en vez de emitir un archivo vacío.
 */
const CON_CUENTA: DatosExportacion = {
  ...DATOS,
  empleados: DATOS.empleados.map((e) => ({
    ...e,
    cuenta_bancaria: `0123456789${e.empleado_no.slice(-1)}`,
  })) as EmpleadoCartera[],
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
  it.each(['dispersion-bbva', 'dispersion-banamex', 'dispersion-banorte'])(
    '%s: la suma de los netos dispersados es la del motor',
    (id) => {
      const formato = FORMATOS.find((f) => f.id === id)!;
      const archivo = formato.generar(CON_CUENTA);
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
    expect(bbva.generar(CON_CUENTA).nombre).toMatch(/PORVALIDAR/);
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

describe('las cuotas del renglón TOTAL son las DOS porciones, no sólo la mensual', () => {
  /**
   * El defecto que esto mata: el renglón TOTAL tomaba
   * `porcion_mensual.total_obrero` y ya. Las cuotas se enteran en dos fechas
   * —EyM, RT y guardería mensuales; Retiro, CEAV e Infonavit bimestrales— pero
   * el motor define el total como la suma de las dos, y la columna por empleado
   * ya las trae juntas.
   *
   * El resultado era un formato llamado "todos los conceptos" cuyo TOTAL no
   * cuadraba con su propia columna, corto justo por Infonavit (5% del SBC) y
   * Retiro (2%). Lo encontró el revisor del cuadre; aquí queda medido.
   */
  const generico = FORMATOS.find((f) => f.id === 'generico')!;

  function renglones(): string[][] {
    return texto(generico.generar(DATOS).bytes).trim().split('\r\n').map((l) => l.split('|'));
  }

  it('la fixture tiene porción bimestral: sin eso esta prueba no mediría nada', () => {
    // Con la bimestral en ceros las dos ramas dan el mismo número y el test
    // pasaría por la razón equivocada.
    expect(aCentavos(NOMINA.porcion_bimestral.total_obrero)).toBeGreaterThan(0);
    expect(aCentavos(NOMINA.porcion_bimestral.total_patron)).toBeGreaterThan(0);
  });

  it('la cuota obrera del TOTAL es mensual + bimestral', () => {
    const filas = renglones();
    const total = filas[filas.length - 1];
    expect(aCentavos(total[8])).toBe(
      sumaCentavos([NOMINA.porcion_mensual.total_obrero, NOMINA.porcion_bimestral.total_obrero]),
    );
    // Y explícitamente NO la mensual sola, que es como estaba.
    expect(aCentavos(total[8])).not.toBe(aCentavos(NOMINA.porcion_mensual.total_obrero));
  });

  it('la cuota patronal del TOTAL es mensual + bimestral', () => {
    const filas = renglones();
    const total = filas[filas.length - 1];
    expect(aCentavos(total[9])).toBe(
      sumaCentavos([NOMINA.porcion_mensual.total_patron, NOMINA.porcion_bimestral.total_patron]),
    );
    expect(aCentavos(total[9])).not.toBe(aCentavos(NOMINA.porcion_mensual.total_patron));
  });

  it('y el TOTAL cuadra con la suma de sus propias columnas de cuotas', () => {
    // La prueba que el operador haría en Excel: seleccionar la columna y sumar.
    const filas = renglones();
    const cuerpo = filas.slice(1, -1);
    const total = filas[filas.length - 1];
    expect(cuerpo.reduce((a, c) => a + aCentavos(c[8]), 0)).toBe(aCentavos(total[8]));
    expect(cuerpo.reduce((a, c) => a + aCentavos(c[9]), 0)).toBe(aCentavos(total[9]));
  });
});

describe('el TOTAL sale del motor aunque difiera de la suma de los recibos', () => {
  /**
   * Sin esto, el punto 3 del cuadre era prosa.
   *
   * En la fixture normal los totales del motor **son** exactamente la suma de
   * los recibos —como debe ser—, así que leer `nomina.total_percepciones` y
   * sumar los recibos en el front dan el mismo string: las dos
   * implementaciones son indistinguibles y el test que dice "es el del motor,
   * no una suma del front" no medía la diferencia. Lo cazó el revisor del
   * cuadre.
   *
   * Aquí los totales se separan **un centavo** a propósito. No es un periodo
   * realista: es una sonda, y es la única forma de distinguir las dos ramas.
   * Si alguien vuelve a recomponer los totales en el front, esto muere.
   */
  const DESVIADA: NominaPeriodo = {
    ...NOMINA,
    total_percepciones: '13106.12',
    total_isr: '162.76',
    total_neto: '12578.34',
  };
  const DATOS_DESVIADOS: DatosExportacion = { ...DATOS, nomina: DESVIADA };
  const generico = FORMATOS.find((f) => f.id === 'generico')!;

  it('la sonda de verdad difiere de la suma de los recibos', () => {
    expect(aCentavos(DESVIADA.total_percepciones)).not.toBe(
      sumaCentavos(RECIBOS.map((r) => r.total_percepciones)),
    );
  });

  it('el renglón TOTAL imprime el número del motor, no el recompuesto', () => {
    const filas = texto(generico.generar(DATOS_DESVIADOS).bytes).trim().split('\r\n');
    const total = filas[filas.length - 1].split('|');
    expect(total[5]).toBe('13106.12');
    expect(total[7]).toBe('162.76');
    expect(total[10]).toBe('12578.34');
  });
});

describe('la dispersión no emite un archivo vacío cuando no hay a quién pagar', () => {
  /**
   * Y hoy ese es el caso NORMAL: `cuenta_bancaria` no existe en el modelo, así
   * que en un periodo real todos los empleados caen en `noExportables` y esto
   * producía un `.txt` de **0 bytes** que el navegador descargaba sin decir
   * nada. Un archivo vacío parece un archivo: se manda al banco y el rechazo
   * llega días después.
   */
  it.each(['dispersion-bbva', 'dispersion-banamex', 'dispersion-banorte'])(
    '%s: sin cuentas capturadas LEVANTA en vez de emitir 0 bytes',
    (id) => {
      const formato = FORMATOS.find((f) => f.id === id)!;
      // DATOS es la plantilla REAL: ningún empleado tiene cuenta, porque el
      // campo no existe todavía en la ficha.
      expect(() => formato.generar(DATOS)).toThrow(/no se puede emitir todavía/);
    },
  );

  it('el mensaje dice cuántos y por qué, no "error al exportar"', () => {
    const bbva = FORMATOS.find((f) => f.id === 'dispersion-bbva')!;
    expect(() => bbva.generar(DATOS)).toThrow(/3 empleados sin cuenta bancaria/);
  });
});

describe('un NSS incompleto no se recorta: queda fuera y se dice', () => {
  /**
   * El NSS se parte en 10 posiciones más su dígito verificador, y se partía con
   * `slice` — que recorta en silencio. Con 10 dígitos, el `slice(10,11)` da
   * vacío y el movimiento sale sobre **otra persona**, en un archivo que mide
   * 168 posiciones y que el IMSS acepta.
   *
   * El backend ya valida el formato, pero era el único punto del módulo donde
   * un dato se acortaba sin que `escribirRegistro` levantara.
   */
  const imss = FORMATOS.find((f) => f.id === 'imss')!;

  it.each([['0101010101'], ['010101010111'], ['0101010101X']])(
    'NSS "%s" no se exporta',
    (nss) => {
      const datos: DatosExportacion = {
        ...DATOS,
        empleados: DATOS.empleados.map((e, i) => (i === 0 ? { ...e, nss } : e)),
      };
      const archivo = imss.generar(datos);
      const fuera = archivo.noExportables.find((n) => n.empleadoNo === 'E-01');
      expect(fuera?.motivo).toMatch(/11 dígitos/);
    },
  );

  it('con los 11 dígitos sí sale', () => {
    const archivo = imss.generar(DATOS);
    expect(archivo.noExportables.find((n) => n.empleadoNo === 'E-01')).toBeUndefined();
  });
});
