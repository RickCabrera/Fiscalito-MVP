/**
 * El gemelo de despacho: **el exportador de O-04 con el flag apagado.**
 *
 * QUÉ DEFECTO EXISTE PORQUE ESTE ARCHIVO NO EXISTÍA
 * -------------------------------------------------
 * O-04 montó `SelectorExportacion` en el paso 4 sin guarda de modo, y lo
 * alimentó con `cartera.empresa.registroPatronal` y `.guiaSubdelegacion`. En
 * modo despacho ese objeto se proyecta del documento con id `'empresa'`, que en
 * una cuenta de despacho **no existe**: los dos campos salían vacíos siempre.
 *
 * La cadena completa, que es lo que la hacía fea: el contador pulsaba Exportar,
 * el generador levantaba —correctamente— diciendo *"captúralo en Perfil →
 * Configuración de empresa"*, el contador iba a Perfil, y esa tarjeta **no se
 * renderiza con el flag apagado** (`ProfilePage` la condiciona a
 * `empresaUnica && esDespacho`). Un callejón sin salida, nuevo de esta corrida,
 * en el modo que Ricardo pidió conservar entero.
 *
 * Y no lo medía nada: `SelectorExportacion.test.tsx` no declara modo y
 * `cuadre.test.ts` inyecta el registro patronal a mano, así que ninguno de los
 * dos ve nunca la cadena vacía. Lo encontró el revisor de cierre.
 *
 * EL ARREGLO ES DE DÓNDE SE LEE, NO UNA GUARDA
 * ---------------------------------------------
 * Apagar el exportador en despacho habría sido recortar. El registro patronal
 * es **de cada patrón**: en despacho sale de la ficha del cliente activo, y se
 * captura en `ModalCliente`. Usar el de otro cliente presentaría los
 * movimientos afiliatorios bajo el patrón equivocado.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import type { ClienteCartera, EmpleadoCartera } from '../services/carteraApi';
import { modoDespacho } from '../test/modoDespacho';

modoDespacho();

const perfil: UserProfile = {
  contributorType: 'contador',
  rfc: '', regimen: '', nombre: 'Contadora', actividad: '', cp: '',
  telefono: '', nombreNegocio: '', numEmpleados: '', nombreDespacho: 'Despacho Ejemplo',
  onboardingComplete: true,
};

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'uid-1', email: 'contadora@ejemplo.mx' }, loading: false }),
}));
vi.mock('../context/ProfileContext', () => ({
  useProfile: () => ({ profile: perfil, loading: false, setProfile: vi.fn() }),
}));

const PERIODO = { inicio: '2026-08-16', fin: '2026-08-31', fecha_pago: '2026-08-31' };
const CLIENTE_ID = 'taller';

/** Un empleado dado de alta DENTRO del periodo: es el que genera el registro 08. */
const EMPLEADO: EmpleadoCartera = {
  empleado_no: 'E-77',
  nombre: 'PERSONA DE PRUEBA UNICA',
  apellido_paterno: 'PERSONA',
  apellido_materno: 'DE PRUEBA',
  nombres: 'UNICA',
  puesto: '',
  salario_diario: '500.00',
  salario_diario_integrado: '524.65',
  zona: 'general',
  fecha_alta: '2026-08-20',
  tipo_contrato: 'indeterminado',
  prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
  nss: '01010101011',
  employee_no: 'E-77',
  enrolamiento: 'enrolado',
};

/** La ficha del cliente del despacho, con sus propios datos del IMSS. */
const FICHA: Omit<ClienteCartera, 'empleados'> = {
  id: CLIENTE_ID,
  nombre: 'Taller Del Cliente',
  giro: '',
  origen: 'propio',
  rfc: 'TDC010101AAA',
  // Los dos datos del hallazgo. Son del CLIENTE, no del despacho.
  registro_patronal: 'B9876543210',
  guia_subdelegacion: '00042',
  prima_riesgo: '0.0113065',
  clase_riesgo: 3,
  clave_periodicidad: '04',
  zona: 'general',
  periodo_sugerido: PERIODO,
};

vi.mock('../services/cartera', () => ({
  cargarCartera: async () => ({
    clientes: [{ ...FICHA, empleados: [EMPLEADO] } as ClienteCartera],
    origen: 'firestore' as const,
    error: null,
  }),
  guardarCliente: vi.fn(),
  borrarCliente: vi.fn(),
  guardarEmpleado: vi.fn(),
  borrarEmpleado: vi.fn(),
  sembrarDemo: vi.fn(),
}));

/** En despacho la pantalla pide la ficha al backend; devuelve la misma. */
vi.mock('../services/despachoApi', async () => {
  const real = await vi.importActual<typeof import('../services/despachoApi')>(
    '../services/despachoApi',
  );
  return {
    ...real,
    obtenerCliente: vi.fn(async () => ({
      ...FICHA,
      num_empleados: 1,
      fecha_referencia: '',
      empleados: [EMPLEADO],
    })),
  };
});

vi.mock('../services/nominaDemoApi', () => ({
  obtenerEventos: vi.fn(async () => ({ eventos: [] })),
  cerrarPeriodo: vi.fn(async () => ({
    exito: true,
    cliente: CLIENTE_ID,
    periodo: { inicio: PERIODO.inicio, fin: PERIODO.fin },
    incidencias: [
      {
        empleado_no: 'E-77', dias_periodo: 16, dias_laborables: 11, dias_trabajados: 11,
        faltas: 0, dias_ausentismo: 0, retardos: 0, dias_cotizados: 16, detalle: [],
      },
    ],
    empleados_desconocidos: [],
  })),
  obtenerPlantillaDemo: vi.fn(),
  calcularNomina: vi.fn(async () => ({
    cliente: CLIENTE_ID,
    periodo: PERIODO,
    fecha_pago_efectiva: '2026-08-31',
    origen_plantilla: 'request',
    recibos: [
      {
        empleado_no: 'E-77', nombre: 'PERSONA DE PRUEBA UNICA', sbc: '524.65',
        es_salario_minimo: false, dias_periodo: 16, dias_ausentismo: 0, dias_pagados: 16,
        percepciones: [], deducciones: [], otros_pagos: [],
        total_percepciones: '8000.00', total_deducciones: '900.00', neto: '7100.00',
        cuota_obrera: '200.00', cuota_patronal: '1500.00',
        absorbio_cuota_obrera: false, ramos: [],
      },
    ],
    porcion_mensual: {
      periodicidad: 'mensual', por_ramo: {}, total_patron: '1500.00',
      total_obrero: '200.00', total: '1700.00', empleados: 1,
    },
    porcion_bimestral: {
      periodicidad: 'bimestral', por_ramo: {}, total_patron: '0.00',
      total_obrero: '0.00', total: '0.00', empleados: 1,
    },
    total_percepciones: '8000.00',
    total_neto: '7100.00',
    total_isr: '0.00',
    advertencias: [],
  })),
}));

vi.mock('../services/pdfExportNomina', () => ({ exportarNominaPDF: vi.fn() }));

const { CarteraProvider } = await import('../context/CarteraContext');
const { default: NominaClientePage } = await import('./NominaClientePage');

vi.mock('../context/clienteActivoStore', async () => {
  const { useCartera } = await import('../context/carteraStore');
  return {
    useClienteActivo: () => {
      const { clientes, loading } = useCartera();
      const c = clientes[0] ?? null;
      return {
        clientes: c ? [{ ...c, num_empleados: c.empleados.length }] : [],
        clienteId: c?.id ?? null,
        cliente: c ? { ...c, num_empleados: c.empleados.length } : null,
        loading, error: null, setClienteId: vi.fn(), recargar: vi.fn(),
      };
    },
  };
});

/** CR+LF, como pide el layout. Escrito así para no meter un salto real aquí. */
const FIN_DE_LINEA = String.fromCharCode(13, 10);

/** Lo que el navegador habría descargado, con sus bytes. */
let descargado: { nombre: string } | null = null;
let blobEmitido: Blob | null = null;

beforeEach(() => {
  descargado = null;
  blobEmitido = null;
  // Se intercepta el Blob para poder LEER lo que se emitió. Comprobar sólo que
  // "no hubo alerta" dejaría pasar un archivo con el registro patronal de otro.
  URL.createObjectURL = vi.fn((b: Blob) => {
    blobEmitido = b;
    return 'blob:x';
  }) as unknown as typeof URL.createObjectURL;
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    descargado = { nombre: this.download };
  });
});

afterEach(cleanup);

function pintar() {
  return render(
    <MemoryRouter>
      <CarteraProvider>
        <NominaClientePage clienteId={CLIENTE_ID} />
      </CarteraProvider>
    </MemoryRouter>,
  );
}

/**
 * Cierra el periodo y calcula, que es como se llega al paso 4.
 *
 * El periodo no tiene checadas —`obtenerEventos` devuelve vacío— así que la
 * pantalla pide confirmación antes de cerrar (R-06). Se confirma: aquí lo que
 * se mide es la exportación, no la guarda del cierre.
 */
async function hastaElPaso4() {
  pintar();
  const cerrar = await screen.findByRole('button', { name: /Cerrar quincena/ });
  await waitFor(() => expect((cerrar as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(cerrar);

  const confirmar = await screen.findByRole('button', { name: /Cerrar de todos modos/ });
  fireEvent.click(confirmar);

  const calcular = await screen.findByRole('button', { name: /Calcular nómina/ });
  await waitFor(() => expect((calcular as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(calcular);
  await waitFor(() => expect(screen.getByLabelText('Formato de exportación')).toBeTruthy());
}

describe('en modo despacho el TXT del IMSS sale con los datos DEL CLIENTE', () => {
  it('exporta de verdad, en vez de mandar a una pantalla que no existe', async () => {
    await hastaElPaso4();

    fireEvent.change(screen.getByLabelText('Formato de exportación'), {
      target: { value: 'imss' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Exportar TXT/ }));

    // Antes del arreglo aquí salía el error "El registro patronal son 11
    // caracteres y hoy hay 0. Captúralo en Perfil → Configuración de empresa",
    // una pantalla que con el flag apagado no se renderiza.
    expect(screen.queryByRole('alert')).toBeNull();
    expect(descargado).not.toBeNull();
  });

  it('el error, si lo hubiera, NO manda a Configuración de empresa', async () => {
    // La aserción que sobrevive aunque el flujo cambie: en despacho esa
    // pantalla no existe, así que ningún mensaje puede nombrarla.
    await hastaElPaso4();
    fireEvent.click(screen.getByRole('button', { name: /Exportar TXT/ }));
    const alerta = screen.queryByRole('alert');
    if (alerta) expect(alerta.textContent).not.toMatch(/Configuración de empresa/);
  });
});

describe('el registro patronal que viaja al archivo es el del cliente activo', () => {
  it('los BYTES emitidos empiezan con el registro patronal de la ficha', async () => {
    await hastaElPaso4();
    fireEvent.change(screen.getByLabelText('Formato de exportación'), {
      target: { value: 'imss' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Exportar TXT/ }));

    await waitFor(() => expect(blobEmitido).not.toBeNull());
    const texto = await (blobEmitido as unknown as Blob).text();

    // Posiciones 01-11 de cada renglón: los 10 del registro más su verificador.
    // Se lee lo que DE VERDAD se escribió, no la propiedad del objeto.
    expect(texto.slice(0, 11)).toBe('B9876543210');
    // Y la guía en 134-138, también del cliente.
    expect(texto.slice(133, 138)).toBe('00042');
    expect(texto).toMatch(/PERSONA/);
  });

  it('el archivo lleva 168 posiciones por renglón, como pide el layout', async () => {
    await hastaElPaso4();
    fireEvent.change(screen.getByLabelText('Formato de exportación'), {
      target: { value: 'imss' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Exportar TXT/ }));

    await waitFor(() => expect(blobEmitido).not.toBeNull());
    const texto = await (blobEmitido as unknown as Blob).text();
    for (const linea of texto.split(FIN_DE_LINEA).filter(Boolean)) {
      expect(linea).toHaveLength(168);
    }
  });
});
