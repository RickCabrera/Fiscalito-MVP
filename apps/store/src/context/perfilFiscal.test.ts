/**
 * De quién es el RFC y el régimen con que se calcula (C-02).
 *
 * Lo que este archivo protege:
 *  1. Que el CONTRIBUYENTE no cambió en nada: su perfil, literal.
 *  2. Que un CONTADOR calcula con el RFC y el régimen de su cliente activo.
 *  3. Que un cliente sin RFC o sin régimen NO calcula con un dato inventado.
 */

import { describe, expect, it } from 'vitest';
import type { UserProfile } from './ProfileContext';
import type { ClienteResumen } from '../services/despachoApi';
import { contribuyenteParaApi, mensajeFalta, resolverPerfilFiscal } from './perfilFiscal';

const PERFIL: UserProfile = {
  contributorType: 'independiente',
  rfc: 'XAXX010101000',
  regimen: '612',
  nombre: 'Contribuyente Demo',
  actividad: '', cp: '', telefono: '', nombreNegocio: '', numEmpleados: '',
  nombreDespacho: '', onboardingComplete: true,
};

const CONTADOR: UserProfile = {
  ...PERFIL, contributorType: 'contador', rfc: 'DES010101AAA', regimen: '', nombre: 'Despacho',
};

/** RFC de pruebas del SAT (persona física): sintético, no es de nadie. */
const CLIENTE: ClienteResumen = {
  id: 'taller', nombre: 'Taller Nogal', giro: 'Reparación', origen: 'sintetico',
  num_empleados: 12, prima_riesgo: '0.0259840', clase_riesgo: 3,
  clave_periodicidad: '04', zona: 'general', regimen: '612', rfc: 'XIQB891116QE4',
};

describe('resolverPerfilFiscal — contribuyente', () => {
  it('usa su perfil tal cual, con el tipo que ya viajaba al API', () => {
    const p = resolverPerfilFiscal(PERFIL, CLIENTE);
    expect(p).toMatchObject({
      sujeto: 'contribuyente', rfc: 'XAXX010101000', regimen: '612',
      nombre: 'Contribuyente Demo', contributorType: 'independiente',
      clienteId: null, regimenParaTabs: '612', regimenSupuesto: false, falta: null,
    });
    // El cliente activo NO le aplica: un contribuyente no tiene cartera.
    expect(contribuyenteParaApi(p)).toEqual({
      rfc: 'XAXX010101000', regimen: '612', contributor_type: 'independiente',
    });
  });

  it('con contributorType null sigue siendo "igual que hoy", literal', () => {
    const p = resolverPerfilFiscal({ ...PERFIL, contributorType: null }, null);
    expect(p.sujeto).toBe('contribuyente');
    expect(contribuyenteParaApi(p)).toEqual({ rfc: 'XAXX010101000', regimen: '612', contributor_type: null });
  });

  it('no normaliza su RFC: se manda como lo capturó, como antes', () => {
    expect(resolverPerfilFiscal({ ...PERFIL, rfc: 'xaxx010101000' }, null).rfc).toBe('xaxx010101000');
  });

  it('sin RFC o sin régimen le falta "perfil", con el mismo mensaje de siempre', () => {
    expect(resolverPerfilFiscal({ ...PERFIL, rfc: '' }, null).falta).toBe('perfil');
    expect(resolverPerfilFiscal({ ...PERFIL, regimen: '' }, null).falta).toBe('perfil');
    expect(mensajeFalta('perfil')).toBe('Completa tu RFC y régimen en tu perfil.');
  });
});

describe('resolverPerfilFiscal — contador', () => {
  it('calcula con el RFC y el régimen del CLIENTE, nunca con los del despacho', () => {
    const p = resolverPerfilFiscal(CONTADOR, CLIENTE);
    expect(p).toMatchObject({
      sujeto: 'cliente', rfc: 'XIQB891116QE4', regimen: '612', nombre: 'Taller Nogal',
      contributorType: null, clienteId: 'taller', regimenParaTabs: '612',
      regimenSupuesto: false, falta: null,
    });
    expect(contribuyenteParaApi(p)).toEqual({ rfc: 'XIQB891116QE4', regimen: '612', contributor_type: null });
  });

  it('normaliza el RFC del cliente: mayúsculas y sin espacios', () => {
    expect(resolverPerfilFiscal(CONTADOR, { ...CLIENTE, rfc: ' xiqb891116qe4 ' }).rfc).toBe('XIQB891116QE4');
  });

  it('cliente sin RFC → falta "rfc" y "Captura el RFC de este cliente"', () => {
    const p = resolverPerfilFiscal(CONTADOR, { ...CLIENTE, rfc: undefined });
    expect(p.falta).toBe('rfc');
    expect(mensajeFalta('rfc')).toBe('Captura el RFC de este cliente.');
    // No el del contribuyente: el despacho no tiene esos campos en su perfil.
    expect(mensajeFalta('rfc')).not.toMatch(/perfil/);
  });

  it('cliente sin régimen → NO calcula con el 612 supuesto, aunque los tabs sí lo usen', () => {
    const p = resolverPerfilFiscal(CONTADOR, { ...CLIENTE, regimen: undefined });
    expect(p.falta).toBe('regimen');
    expect(p.regimen).toBe('');
    expect(p.regimenParaTabs).toBe('612');
    expect(p.regimenSupuesto).toBe(true);
  });

  it('sin cliente elegido le falta "cliente" y no hay régimen para los tabs', () => {
    const p = resolverPerfilFiscal(CONTADOR, null);
    expect(p).toMatchObject({ sujeto: 'cliente', falta: 'cliente', clienteId: null, regimenParaTabs: null, rfc: '' });
  });
});
