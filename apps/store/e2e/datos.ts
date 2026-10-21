/**
 * Datos y utilidades del recorrido e2e (P6-04). Todo sintético: RFC con el prefijo `SIN`
 * de la guardia `tests/test_sin_rfc_reales.py`, CURP y NSS inventados (el NSS lleva su
 * dígito verificador Luhn para que la ficha lo acepte sin advertencia).
 */
import { execFileSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export const API = 'http://127.0.0.1:8765';
/** Debe coincidir con `E2E_RFC` de `levantar.sh` (los CFDI del SAT falso son de este RFC). */
export const RFC_CLIENTE = 'SIN010101AB1';
export const CLAVE_CLIENTE = 'sintetica';
export const RAZON_SOCIAL = 'Comercializadora Sintética SA de CV';
export const CORREO_CONTADORA = 'contadora@despacho-e2e.test';
/** El doble de auth (`src/e2e/firebaseAuthFalso.ts`) usa este uid como token. */
export const UID_CONTADORA = 'e2e-contadora-despacho-e2e-test';

export const EMPLEADO = {
  numero: 'E-01',
  nombre: 'Ana Sintética Prueba',
  paterno: 'SINTETICA',
  materno: 'PRUEBA',
  pila: 'ANA',
  rfc: 'SINT010101AB1',
  curp: 'SINT010101MDFNNN09',
  nss: '12345678903',
  correo: 'ana@trabajadora-e2e.test',
  checador: '101',
};

/** El mes anterior al de hoy: es el que `levantar.sh` llena de CFDI en el SAT falso. */
export function mesAnterior(hoy = new Date()): { anio: number; mes: number; aaaamm: string; desde: string; hasta: string } {
  const ultimo = new Date(hoy.getFullYear(), hoy.getMonth(), 0);
  const anio = ultimo.getFullYear();
  const mes = ultimo.getMonth() + 1;
  const aaaamm = `${anio}-${String(mes).padStart(2, '0')}`;
  return { anio, mes, aaaamm, desde: `${aaaamm}-01`, hasta: `${aaaamm}-${String(ultimo.getDate()).padStart(2, '0')}` };
}

/** e.firma y CSD de prueba del RFC del cliente (`e2e/certificados.py`). */
export function generarCertificados(): { dir: string; password: string } {
  const dir = mkdtempSync(join(tmpdir(), 'fiscalito-e2e-certs-'));
  const password = execFileSync(process.env.PYTHON ?? 'python', ['e2e/certificados.py', dir, RFC_CLIENTE], {
    encoding: 'utf8',
  }).trim();
  return { dir, password };
}

/** Días `AAAA-MM-DD` entre dos fechas, inclusive. */
export function diasEntre(inicio: string, fin: string): string[] {
  const dias: string[] = [];
  for (let d = new Date(`${inicio}T12:00:00Z`); d <= new Date(`${fin}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + 1)) {
    dias.push(d.toISOString().slice(0, 10));
  }
  return dias;
}

/**
 * Checadas de entrada y salida para cada día, con la forma `AcsEvent` del Hikvision. El
 * checador es un aparato: no tiene pantalla que clickear, así que se siembra por la API
 * igual que lo haría `scripts/simular_checador.py`.
 */
export function checadas(dias: string[], empleadoNo: string) {
  let serie = 1;
  const marca = (dia: string, hora: string, estado: 'checkIn' | 'checkOut') => ({
    major: 5, minor: 75, employeeNoString: empleadoNo, time: `${dia}T${hora}-06:00`,
    attendanceStatus: estado, serialNo: serie++,
  });
  const InfoList = dias.flatMap((dia) => [marca(dia, '08:55:00', 'checkIn'), marca(dia, '18:05:00', 'checkOut')]);
  return { AcsEvent: { InfoList } };
}
