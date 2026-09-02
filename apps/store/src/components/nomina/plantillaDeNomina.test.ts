/**
 * Quién entra a la nómina y quién no (G-01, G-02).
 *
 * POR QUÉ ESTE ARCHIVO EXISTE
 * ---------------------------
 * `useNominaCliente` decide, con tres líneas, **los dos criterios de la épica**:
 * que un empleado dado de alta hoy aparezca en el cálculo (G-01) y que uno sin
 * `employee_no` NO aparezca (G-02). Esa decisión tiene consecuencia fiscal —al
 * contador le falta gente en la nómina— y estaba **sin un solo test**: los seis
 * archivos de pantalla mockean la cartera con el doble vacío, así que ninguno
 * ejercita este camino. Se podía invertir el filtro a `!estaVinculado` y la
 * suite entera seguía verde.
 *
 * La lógica se extrajo a `plantillaDeNomina` para poder medirla sin montar un
 * árbol de React con cinco proveedores. El hook la llama y no la reimplementa.
 */

import { describe, expect, it } from 'vitest';
import { plantillaDeNomina } from './plantillaDeNomina';
import type { EmpleadoCartera } from '../../services/carteraApi';
import type { EmpleadoCliente } from '../../services/despachoApi';

function deCartera(over: Partial<EmpleadoCartera> = {}): EmpleadoCartera {
  return {
    empleado_no: 'E-01',
    nombre: 'ANA LOPEZ',
    puesto: 'Cajera',
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

function deFicha(over: Partial<EmpleadoCliente> = {}): EmpleadoCliente {
  return {
    empleado_no: 'F-01',
    nombre: 'DE LA FICHA',
    puesto: '',
    salario_diario: '400.00',
    salario_diario_integrado: '420.00',
    zona: 'general',
    fecha_alta: null,
    antiguedad_anios: null,
    factor: '1.0500',
    factor_implicito: true,
    ...over,
  };
}

describe('plantillaDeNomina · G-01, el alta nueva entra al cálculo', () => {
  it('cuando hay cartera, la plantilla sale de la cartera', () => {
    const plantilla = plantillaDeNomina([deFicha()], [deCartera()]);
    expect(plantilla.map((e) => e.empleado_no)).toEqual(['E-01']);
  });

  it('un empleado dado de alta hoy aparece en la plantilla', () => {
    // El criterio literal de G-01.
    const plantilla = plantillaDeNomina(
      [],
      [deCartera(), deCartera({ empleado_no: 'N-99', nombre: 'RECIEN CONTRATADO', employee_no: '99' })],
    );
    expect(plantilla.map((e) => e.nombre)).toContain('RECIEN CONTRATADO');
  });

  it('manda los cinco campos que el backend espera, y sólo esos', () => {
    // Ni `factor` ni `factor_implicito` inventados: `EmpleadoNominaRequest` es
    // la forma del request, no un `EmpleadoCliente` falsificado.
    const [e] = plantillaDeNomina([], [deCartera()]);
    expect(Object.keys(e).sort()).toEqual([
      'empleado_no', 'nombre', 'salario_diario', 'salario_diario_integrado', 'zona',
    ]);
  });

  it('el SBC que viaja es el de la cartera, no uno recalculado', () => {
    // §D9: el SDI es dato de entrada. Recalcularlo aquí contradiría el CFDI.
    const [e] = plantillaDeNomina([], [deCartera({ salario_diario_integrado: '999.99' })]);
    expect(e.salario_diario_integrado).toBe('999.99');
  });
});

describe('plantillaDeNomina · G-02, el no vinculado NO entra', () => {
  it('un empleado sin employee_no queda fuera del cálculo', () => {
    const plantilla = plantillaDeNomina(
      [],
      [deCartera(), deCartera({ empleado_no: 'N-01', nombre: 'SIN VINCULAR', employee_no: null })],
    );
    expect(plantilla.map((e) => e.empleado_no)).toEqual(['E-01']);
  });

  it('el filtro NO está invertido', () => {
    // La mutación que la suite anterior no cachaba: cambiar `estaVinculado` por
    // su negación dejaba fuera a TODOS los que sí tienen llave.
    const plantilla = plantillaDeNomina([], [deCartera({ employee_no: '7' })]);
    expect(plantilla).toHaveLength(1);
  });

  it('con todos sin vincular la plantilla queda vacía, no con llaves en blanco', () => {
    // La alternativa mala sería mandarlos con `employee_no: ""`: dos empleados
    // sin vincular colisionarían en el dedupe del almacén de checadas y uno se
    // comería las incidencias del otro.
    //
    // **La ficha va NO vacía a propósito.** Con `[]` en los dos lados este test
    // pasaba aunque la función cayera a la ficha cuando la cartera queda vacía
    // —un `deLaCartera && deLaCartera.length` de más—, y esa caída resucitaría
    // justo a los que se acaban de excluir. Lo destapó una mutación.
    const plantilla = plantillaDeNomina(
      [deFicha()],
      [deCartera({ employee_no: null }), deCartera({ empleado_no: 'N-02', employee_no: null })],
    );
    expect(plantilla).toEqual([]);
  });

  it('la llave que viaja es la del CÁLCULO, no la del checador', () => {
    // Son campos distintos y pueden tener valores distintos: el backend indexa
    // incidencias y recibos por `empleado_no`.
    const [e] = plantillaDeNomina([], [deCartera({ empleado_no: 'E-07', employee_no: '7' })]);
    expect(e.empleado_no).toBe('E-07');
  });
});

describe('plantillaDeNomina · sin cartera se cae a la ficha del backend', () => {
  it('una cartera VACÍA no se cae a la ficha: es un cliente sin empleados', () => {
    // `[]` y `null` significan cosas distintas y aquí se ve por qué. Un cliente
    // recién dado de alta tiene cartera vacía, y caer a la ficha del catálogo le
    // metería en su nómina los empleados de OTRO cliente. Con un
    // `deLaCartera && deLaCartera.length` de más, esto pasa; lo destapó una
    // mutación y por eso el caso está escrito.
    expect(plantillaDeNomina([deFicha()], [])).toEqual([]);
  });

  it('con la cartera todavía cargando usa la ficha, no una lista vacía', () => {
    // `null` = la cartera no ha llegado. Devolver [] aquí dejaría al contador
    // con una nómina de cero empleados durante el arranque.
    const plantilla = plantillaDeNomina([deFicha()], null);
    expect(plantilla.map((e) => e.empleado_no)).toEqual(['F-01']);
  });

  it('la ficha también se reduce a los cinco campos del request', () => {
    const [e] = plantillaDeNomina([deFicha()], null);
    expect(e).not.toHaveProperty('factor');
    expect(e).not.toHaveProperty('factor_implicito');
  });

  it('sin ficha y sin cartera, la plantilla es vacía y no revienta', () => {
    expect(plantillaDeNomina([], null)).toEqual([]);
  });
});
