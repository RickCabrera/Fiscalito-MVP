/**
 * El modelo de dispositivos y, sobre todo, sus tres cruces. (R-04)
 *
 * LOS CRUCES SON EL VALOR DE LA PANTALLA, NO LA TABLA
 * ---------------------------------------------------
 * G-02 dejó dos lados de un triángulo y R-04 cierra el tercero. Los tres
 * responden preguntas distintas y con sólo dos de ellos hay gente que
 * desaparece del cálculo sin que nadie lo note:
 *
 * 1. **No vinculado** (`EmpleadosTab`): está en la cartera, sin `employee_no`.
 *    No entra al cálculo.
 * 2. **Desconocido** (`TablaIncidencias`): checó, no está en la plantilla.
 * 3. **Fantasma** (aquí): enrolado en el aparato, ausente de la cartera. Es el
 *    que EXPLICA de dónde salen los desconocidos del punto 2.
 *
 * Y uno más que ninguno cubría: **vinculado pero sin aparato** — entra al
 * cálculo, no va a checar nunca, y sale con falta en todos los días laborables.
 * Ése es el que produce una nómina completa y creíble con menos días pagados,
 * que es el modo de falla que `D-DEMO-CHECADOR.md` advierte que no parece error.
 */

import { describe, expect, it } from 'vitest';
import {
  cruzarEnrolamiento,
  dispositivoVacio,
  ipValida,
  sinAparato,
  validarDispositivo,
  type DispositivoChecador,
} from './dispositivosApi';
import type { EmpleadoCartera } from './carteraApi';

function emp(over: Partial<EmpleadoCartera> = {}): EmpleadoCartera {
  return {
    empleado_no: 'E-01',
    nombre: 'ANA LOPEZ',
    puesto: '',
    salario_diario: '316.00',
    salario_diario_integrado: '331.58',
    zona: 'general',
    fecha_alta: null,
    tipo_contrato: 'indeterminado',
    prestaciones: { dias_aguinaldo: 15, dias_vacaciones: 0, prima_vacacional: '0.25' },
    nss: '',
    employee_no: 'E-01',
    enrolamiento: 'enrolado',
    ...over,
  };
}

function disp(over: Partial<DispositivoChecador> = {}): DispositivoChecador {
  return { ...dispositivoVacio(), id: 'd1', nombre: 'Entrada', ...over };
}

describe('ipValida', () => {
  it.each(['192.168.1.64', '10.0.0.1', '0.0.0.0', '255.255.255.255'])('acepta %s', (ip) => {
    expect(ipValida(ip)).toBe(true);
  });

  it.each([
    ['999.1.1.1', 'octeto fuera de rango — el regex ingenuo de dígitos y puntos lo deja pasar'],
    ['192.168.1', 'faltan octetos'],
    ['192.168.1.1.1', 'sobran octetos'],
    ['192.168.1.a', 'no numérico'],
    ['', 'vacío'],
  ])('rechaza %s (%s)', (ip) => {
    expect(ipValida(ip)).toBe(false);
  });
});

describe('validarDispositivo', () => {
  it('exige nombre: es lo que sirve para encontrar el aparato', () => {
    const p = validarDispositivo(disp({ nombre: '  ' }), []);
    expect(p.map((x) => x.campo)).toContain('nombre');
  });

  it('la IP es OPCIONAL: un aparato puede registrarse antes de instalarse', () => {
    expect(validarDispositivo(disp({ ip: '' }), [])).toEqual([]);
  });

  it('pero si se captura, tiene que ser una dirección', () => {
    const p = validarDispositivo(disp({ ip: '999.1.1.1' }), []);
    expect(p.map((x) => x.campo)).toContain('ip');
  });

  it('rechaza un serial ya usado por otro aparato del mismo cliente', () => {
    const p = validarDispositivo(disp({ serial: 'ABC123' }), ['ABC123']);
    expect(p.map((x) => x.campo)).toContain('serial');
  });

  it('un serial vacío no cuenta como repetido aunque haya otros vacíos', () => {
    // Si no, dos aparatos sin serial capturado se bloquearían entre sí.
    expect(validarDispositivo(disp({ serial: '' }), ['', ''])).toEqual([]);
  });

  it.each([0, -1, 70000, 1.5])('rechaza el puerto %s', (puerto) => {
    const p = validarDispositivo(disp({ puerto }), []);
    expect(p.map((x) => x.campo)).toContain('puerto');
  });
});

describe('cruzarEnrolamiento — el tercer lado del triángulo de G-02', () => {
  it('separa a los enrolados que existen de los que no', () => {
    const empleados = [emp({ empleado_no: 'E-01', employee_no: '7' })];
    const d = disp({ employee_nos: ['7', '99'] });

    const { enrolados, fantasmas } = cruzarEnrolamiento(d, empleados);
    expect(enrolados.map((e) => e.empleado_no)).toEqual(['E-01']);
    expect(fantasmas).toEqual(['99']);
  });

  it('NO invierte el cruce', () => {
    // La mutación obvia es intercambiar las dos ramas, y con un solo caso en
    // cada conjunto el test de arriba la detecta pero no dice cuál es cuál.
    // Aquí el conteo es asimétrico: invertirlo da 2 y 1 en vez de 1 y 2.
    const empleados = [emp({ empleado_no: 'E-01', employee_no: '7' })];
    const d = disp({ employee_nos: ['7', '98', '99'] });

    const { enrolados, fantasmas } = cruzarEnrolamiento(d, empleados);
    expect(enrolados).toHaveLength(1);
    expect(fantasmas).toHaveLength(2);
  });

  it('cruza por la llave del CHECADOR, no por la del cálculo', () => {
    // Es la separación de G-02, y fundirlas fue el defecto fiscal más grave de
    // aquella corrida. Aquí el empleado `E-01` tiene número de aparato `7`:
    // enrolar `E-01` NO debe encontrarlo.
    const empleados = [emp({ empleado_no: 'E-01', employee_no: '7' })];

    expect(cruzarEnrolamiento(disp({ employee_nos: ['7'] }), empleados).enrolados).toHaveLength(1);
    expect(cruzarEnrolamiento(disp({ employee_nos: ['E-01'] }), empleados).enrolados).toHaveLength(0);
  });

  it('un empleado sin employee_no no se cruza con nada', () => {
    const empleados = [emp({ empleado_no: 'E-02', employee_no: null })];
    const { enrolados, fantasmas } = cruzarEnrolamiento(disp({ employee_nos: [''] }), empleados);
    expect(enrolados).toHaveLength(0);
    expect(fantasmas).toEqual(['']);
  });
});

describe('sinAparato — vinculado, en el cálculo, y no va a checar nunca', () => {
  it('encuentra al vinculado que no está en ningún aparato', () => {
    const empleados = [
      emp({ empleado_no: 'E-01', employee_no: '7' }),
      emp({ empleado_no: 'E-02', employee_no: '8' }),
    ];
    const dispositivos = [disp({ employee_nos: ['7'] })];

    expect(sinAparato(empleados, dispositivos).map((e) => e.empleado_no)).toEqual(['E-02']);
  });

  it('los NO vinculados no cuentan aquí: son el otro aviso', () => {
    // Un empleado sin `employee_no` ya lo marca `EmpleadosTab` y además NO
    // entra al cálculo, así que listarlo también aquí diluiría el aviso con
    // gente que no tiene este problema.
    const empleados = [emp({ empleado_no: 'E-03', employee_no: null })];
    expect(sinAparato(empleados, [])).toEqual([]);
  });

  it('con varios aparatos, basta estar en uno', () => {
    const empleados = [emp({ empleado_no: 'E-01', employee_no: '7' })];
    const dispositivos = [disp({ id: 'a', employee_nos: [] }), disp({ id: 'b', employee_nos: ['7'] })];
    expect(sinAparato(empleados, dispositivos)).toEqual([]);
  });
});
