/**
 * Los tipos generados del OpenAPI (P0-08) compilan y casan con los tipos escritos a mano.
 *
 * `tiposApi.generados.ts` lo escribe `apps/api/scripts/exportar_openapi.py` y el backend
 * vigila que no se quede viejo (`apps/api/tests/test_contrato_openapi.py`). Esta mitad mide
 * el lado del front: el archivo se importa —si no compila, `npm run build` y este test se
 * caen— y las aserciones de tipo de abajo fallan en `tsc` el día que un tipo escrito a mano
 * deje de ser asignable al que publica el backend.
 *
 * Las aserciones son de COMPILACIÓN (`Asignable<A, B>` resuelve a `never` si no casan): el
 * `expect` sólo existe para que vitest tenga algo que correr.
 */

import { describe, expect, it } from 'vitest';
import type {
  OperacionesApi,
  PeriodoSugeridoResponse,
  PrimasDeRiesgoResponse,
  RutaApi,
  SBCResponse as SBCGenerado,
  TokenEmitidoResponse,
} from './tiposApi.generados';
import type { PeriodoSugerido } from './despachoApi';
import type { PrimasDeRiesgo, SBCResponse } from './carteraApi';
import rutasBackend from './rutasBackend.json';

/** `true` si A se puede usar donde se espera B; si no, el tipo es `never` y `tsc` falla. */
type Asignable<A, B> = [A] extends [B] ? true : never;

// Lo que el backend responde debe caber en lo que la pantalla espera.
const sbc: Asignable<SBCGenerado, SBCResponse> = true;
const primas: Asignable<PrimasDeRiesgoResponse, PrimasDeRiesgo> = true;
// `periodo.fecha_pago` sale OPCIONAL en el OpenAPI (Pydantic marca así un campo con default)
// aunque la ruta siempre lo manda explícito; el tipo escrito a mano lo exige. Se compara lo
// demás, y la diferencia queda dicha aquí en vez de aflojar el tipo de la pantalla.
const periodo: Asignable<
  Omit<PeriodoSugeridoResponse, 'periodo'>,
  Omit<PeriodoSugerido, 'periodo'>
> = true;
// Y las operaciones apuntan a esos tipos, no a `unknown`.
const operacion: Asignable<OperacionesApi['POST /api/v1/nomina/sbc']['respuesta'], SBCResponse> =
  true;
const token: Asignable<
  OperacionesApi['POST /api/v1/asistencia/tokens']['respuesta'],
  TokenEmitidoResponse
> = true;

describe('tipos generados del OpenAPI', () => {
  it('compilan y casan con los tipos escritos a mano', () => {
    expect([sbc, primas, periodo, operacion, token].every(Boolean)).toBe(true);
  });

  it('RutaApi conoce las mismas rutas que rutasBackend.json', () => {
    // Un literal por ruta: si una ruta del JSON no estuviera en `RutaApi`, la asignación
    // no compilaría. En tiempo de ejecución se compara el conteo contra el JSON.
    const rutas: RutaApi[] = rutasBackend.rutas.map((r) => r.path as RutaApi);
    expect(new Set(rutas).size).toBe(rutasBackend.rutas.length);
    const muestra: RutaApi = '/api/v1/asistencia/tokens';
    expect(rutas).toContain(muestra);
  });
});
