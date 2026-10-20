/**
 * El front no lleva NINGUNA llave ni llamada directa a un proveedor de IA. (P5-07, S-00)
 *
 * POR QUÉ EXISTE
 * --------------
 * `voiceChatService.ts` leía la llave de OpenAI de una variable `VITE_*` y llamaba a
 * Whisper, al chat y a TTS desde el navegador. Vite incrusta TODA variable `VITE_*` en el
 * JavaScript que se descarga, así que la llave viajaba a cada visitante: el 2026-08-31 estaba
 * en texto plano en el bundle publicado y hubo que revocarla. Desde P5-07 la voz y el chat
 * pasan por el backend (`services/asistenteApi.ts`), que guarda la llave en su entorno.
 *
 * Este test recorre `src/` y los `.env*` de ejemplo y falla si reaparece cualquiera de las
 * dos cosas: una variable de llave de LLM con prefijo `VITE_`, o una URL de API de proveedor.
 * Los patrones se arman por partes para que este mismo archivo no se encuentre a sí mismo.
 * Los archivos de prueba (`*.test.*` y `src/test/`) no entran al bundle y se excluyen:
 * `src/test/setup.test.ts`, por ejemplo, usa la URL de OpenAI para probar que la red de la
 * suite está cerrada.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ_STORE = resolve(AQUI, '..');

const V = 'VITE' + '_';
const PROHIBIDOS: Array<[string, RegExp]> = [
  ['variable VITE de llave de LLM', new RegExp(`${V}(OPENAI|ANTHROPIC|LLM|WHISPER)`, 'i')],
  ['URL de la API de OpenAI', new RegExp('api\\.' + 'openai\\.com')],
  ['URL de la API de Anthropic', new RegExp('api\\.' + 'anthropic\\.com')],
  ['llave con forma de OpenAI/Anthropic', new RegExp('\\bsk-' + '(proj-|ant-)?[A-Za-z0-9_-]{16,}')],
];

function archivos(dir: string): string[] {
  return readdirSync(dir).flatMap((nombre) => {
    const ruta = join(dir, nombre);
    if (statSync(ruta).isDirectory()) return nombre === 'test' ? [] : archivos(ruta);
    if (/\.test\.[jt]sx?$/.test(nombre)) return [];
    return /\.(ts|tsx|js|jsx|json|html|css)$/.test(nombre) ? [ruta] : [];
  });
}

function hallazgos(rutas: string[]): string[] {
  return rutas.flatMap((ruta) => {
    const texto = readFileSync(ruta, 'utf8');
    return PROHIBIDOS.filter(([, re]) => re.test(texto))
      .map(([que]) => `${relative(RAIZ_STORE, ruta)}: ${que}`);
  });
}

describe('sin llaves de LLM en el navegador', () => {
  it('ningún archivo de src/ tiene llave, variable VITE de LLM ni URL de proveedor', () => {
    expect(hallazgos(archivos(AQUI))).toEqual([]);
  });

  it('los .env de ejemplo no declaran llaves de LLM', () => {
    const ejemplos = readdirSync(RAIZ_STORE)
      .filter((n) => n.startsWith('.env') && n !== '.env' && !n.endsWith('.local'))
      .map((n) => join(RAIZ_STORE, n));
    expect(ejemplos.length).toBeGreaterThan(0);
    expect(hallazgos(ejemplos)).toEqual([]);
  });

  it('el detector sí detecta (no pasa en verde por estar roto)', () => {
    const muestra = `const k = import.meta.env.${V}OPENAI_API_KEY; fetch('https://api.` +
      'openai.com/v1/x\')';
    expect(PROHIBIDOS.filter(([, re]) => re.test(muestra))).toHaveLength(2);
  });
});
