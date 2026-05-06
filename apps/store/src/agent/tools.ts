/**
 * Definición de tools del agente Fiscalito + ejecutores.
 *
 * Schema en formato OpenAI tool calling (chat completions API).
 * Ver: https://platform.openai.com/docs/guides/function-calling
 *
 * Día 1 — tres tools:
 *   1. navegar               → cambia de ruta (reemplaza tags [NAVEGAR:])
 *   2. cargar_xmls_demo      → lee XMLs de /public/demo-xmls/{año}/{mes}/
 *   3. calcular_predeclaracion → llama al Fiscal Agent API con perfil + CFDIs
 */

import type { NavigateFunction } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import { parseMultipleCFDI } from '../services/cfdiParser';
import {
  calcularPreDeclaracion,
  type CFDI,
  type PreDeclaracionRequest,
} from '../services/fiscalAgentApi';
import { guardarDeclaracion } from '../services/declaracionesHistory';
import { getAgentActions, getAgentSnapshot } from './AgentContext';
import type { ToolName, ToolResult } from './types';

// ────────────────────────────────────────────────────────────
// Schema OpenAI
// ────────────────────────────────────────────────────────────

/** Rutas válidas que la tool `navegar` puede recibir. Se enumeran para que
 *  el LLM no invente rutas inexistentes. */
const RUTAS_VALIDAS = [
  '/app',
  '/app/historial',
  '/app/store',
  '/app/store/fiscalito/use',
  '/app/profile',
  // Tabs internos de Fiscalito
  '/app/store/fiscalito/use?tab=declaracion',
  '/app/store/fiscalito/use?tab=calendario',
  '/app/store/fiscalito/use?tab=comparar',
  '/app/store/fiscalito/use?tab=diot',
  '/app/store/fiscalito/use?tab=retenciones',
  '/app/store/fiscalito/use?tab=multiperiodo',
  '/app/store/fiscalito/use?tab=estado-cuenta',
  '/app/store/fiscalito/use?tab=deducciones',
] as const;

export const TOOLS_OPENAI = [
  {
    type: 'function' as const,
    function: {
      name: 'navegar',
      description:
        'Navega a una sección específica de la aplicación cambiando la ruta del navegador. ' +
        'Úsala cuando el usuario pida ver, ir, entrar, mostrar o acceder a cualquier sección o tab.',
      parameters: {
        type: 'object',
        properties: {
          ruta: {
            type: 'string',
            enum: RUTAS_VALIDAS,
            description:
              'Ruta exacta a la que navegar. Para tabs internos de Fiscalito ' +
              'usa la ruta con ?tab=... Por ejemplo, "/app/store/fiscalito/use?tab=declaracion" ' +
              'lleva al tab de pre-declaración.',
          },
        },
        required: ['ruta'],
      },
    },
  },
  {
    type: 'function' as const,
    function: {
      name: 'cargar_xmls_demo',
      description:
        'Carga un conjunto de facturas CFDI de demostración para un periodo dado. ' +
        'Lee archivos XML de /demo-xmls/{año}/{mes}/ y los parsea como CFDIs listos para calcular. ' +
        'Úsala cuando el usuario pida calcular una pre-declaración pero no tenga facturas cargadas, ' +
        'o cuando esté demostrando el sistema. Las facturas cargadas quedan disponibles para ' +
        'la tool calcular_predeclaracion.',
      parameters: {
        type: 'object',
        properties: {
          año: { type: 'integer', description: 'Año del periodo (ej: 2026)', minimum: 2020, maximum: 2030 },
          mes: { type: 'integer', description: 'Mes del periodo (1-12)', minimum: 1, maximum: 12 },
        },
        required: ['año', 'mes'],
      },
    },
  },
  {
    type: 'function' as const,
    function: {
      name: 'calcular_predeclaracion',
      description:
        'Calcula una pre-declaración mensual de ISR e IVA llamando al Fiscal Agent API. ' +
        'Usa el perfil del contribuyente actual y las facturas que ya están cargadas en el agente ' +
        '(ya sea por el usuario manualmente o por la tool cargar_xmls_demo). ' +
        'Devuelve el desglose con montos a pagar y la explicación generada por IA. ' +
        'IMPORTANTE: si no hay facturas cargadas, esta tool fallará — primero llama a cargar_xmls_demo.',
      parameters: {
        type: 'object',
        properties: {
          año: { type: 'integer', description: 'Año del periodo a declarar', minimum: 2020, maximum: 2030 },
          mes: { type: 'integer', description: 'Mes del periodo a declarar (1-12)', minimum: 1, maximum: 12 },
        },
        required: ['año', 'mes'],
      },
    },
  },
] as const;

// ────────────────────────────────────────────────────────────
// Dependencias inyectadas a los ejecutores
// ────────────────────────────────────────────────────────────

export interface ToolDeps {
  navigate: NavigateFunction;
  profile: UserProfile;
  uid: string | null;
}

// ────────────────────────────────────────────────────────────
// Ejecutores
// ────────────────────────────────────────────────────────────

async function ejecutarNavegar(
  args: { ruta: string },
  deps: ToolDeps,
): Promise<ToolResult> {
  if (!RUTAS_VALIDAS.includes(args.ruta as typeof RUTAS_VALIDAS[number])) {
    return {
      ok: false,
      summary: `Ruta inválida: ${args.ruta}`,
      error: `La ruta "${args.ruta}" no está en la lista de rutas válidas.`,
    };
  }
  deps.navigate(args.ruta);
  return {
    ok: true,
    summary: `Navegando a ${args.ruta}`,
    data: { ruta: args.ruta },
  };
}

async function ejecutarCargarXmlsDemo(
  args: { año: number; mes: number },
  _deps: ToolDeps,
): Promise<ToolResult> {
  const { año, mes } = args;
  const mesPadded = String(mes).padStart(2, '0');
  const indexUrl = `/demo-xmls/${año}/${mesPadded}/index.json`;

  // Convención: cada carpeta /demo-xmls/{año}/{mes}/ tiene un index.json con la
  // lista de archivos disponibles. Esto evita un listing de directorio que en
  // un static host como Firebase Hosting no existe.
  let lista: string[];
  try {
    const resp = await fetch(indexUrl);
    if (!resp.ok) {
      return {
        ok: false,
        summary: `No hay XMLs demo para ${mesPadded}/${año}`,
        error:
          `El index ${indexUrl} no existe (HTTP ${resp.status}). ` +
          `Asegúrate de que /public/demo-xmls/${año}/${mesPadded}/ exista y tenga index.json.`,
      };
    }
    const data = await resp.json();
    lista = Array.isArray(data) ? data : data.files ?? [];
  } catch (e) {
    return {
      ok: false,
      summary: 'Error al leer index de XMLs demo',
      error: e instanceof Error ? e.message : String(e),
    };
  }

  if (lista.length === 0) {
    return {
      ok: false,
      summary: `La carpeta /demo-xmls/${año}/${mesPadded}/ está vacía`,
      error: 'No hay XMLs registrados en index.json.',
    };
  }

  const files: File[] = [];
  for (const filename of lista) {
    try {
      const resp = await fetch(`/demo-xmls/${año}/${mesPadded}/${filename}`);
      if (!resp.ok) continue;
      const text = await resp.text();
      files.push(new File([text], filename, { type: 'text/xml' }));
    } catch {
      // un XML que falla no debe romper toda la carga
    }
  }

  if (files.length === 0) {
    return {
      ok: false,
      summary: 'Ningún XML del index pudo descargarse',
      error: 'Verifica que los archivos listados en index.json existan.',
    };
  }

  const parsed = await parseMultipleCFDI(files);
  if (parsed.success.length === 0) {
    return {
      ok: false,
      summary: 'Los XMLs descargados no son CFDIs válidos',
      error: parsed.errors.map((e) => `${e.fileName}: ${e.error}`).join(' | '),
    };
  }

  // Empujar al estado del agente: las facturas cargadas se acumulan y se
  // reflejan en el tab activo gracias a useSyncTabToAgent.
  const { setFacturas, setPeriodo } = getAgentActions();
  const previas = getAgentSnapshot().facturas;
  const uuidsExistentes = new Set(previas.map((f: CFDI) => f.uuid));
  const nuevas = parsed.success.filter((f) => !uuidsExistentes.has(f.uuid));
  setFacturas([...previas, ...nuevas]);
  setPeriodo(año, mes);

  const ingresos = nuevas.filter((f) => f.tipo === 'I').length;
  const egresos = nuevas.filter((f) => f.tipo === 'E').length;

  return {
    ok: true,
    summary:
      `Cargué ${nuevas.length} factura(s) demo de ${mesPadded}/${año} ` +
      `(${ingresos} ingreso(s), ${egresos} egreso(s)). ` +
      `Total acumulado: ${previas.length + nuevas.length} factura(s).`,
    data: {
      cargadas: nuevas.length,
      ingresos,
      egresos,
      total_acumulado: previas.length + nuevas.length,
      periodo: `${mesPadded}/${año}`,
    },
  };
}

async function ejecutarCalcularPredeclaracion(
  args: { año: number; mes: number },
  deps: ToolDeps,
): Promise<ToolResult> {
  const { profile } = deps;
  const snapshot = getAgentSnapshot();

  if (!profile.rfc || !profile.regimen) {
    return {
      ok: false,
      summary: 'Falta RFC o régimen en el perfil del contribuyente',
      error: 'Pídele al usuario que complete su perfil (RFC y régimen) en /app/profile antes de calcular.',
    };
  }

  if (snapshot.facturas.length === 0) {
    return {
      ok: false,
      summary: 'No hay facturas cargadas',
      error: 'No hay CFDIs en el estado del agente. Llama primero a cargar_xmls_demo o pídele al usuario que suba sus XMLs.',
    };
  }

  const request: PreDeclaracionRequest = {
    contribuyente: {
      rfc: profile.rfc,
      regimen: profile.regimen,
      nombre: profile.nombre,
      contributor_type: profile.contributorType,
      actividad_economica: profile.actividad,
    },
    facturas: snapshot.facturas,
    periodo_year: args.año,
    periodo_month: args.mes,
    incluir_explicacion: true,
  };

  let resp;
  try {
    resp = await calcularPreDeclaracion(request);
  } catch (e) {
    return {
      ok: false,
      summary: 'El Fiscal Agent API rechazó el cálculo',
      error: e instanceof Error ? e.message : String(e),
    };
  }

  // Persistir en AgentContext para que el tab muestre el resultado.
  const { setResultado, setPeriodo } = getAgentActions();
  setResultado(resp);
  setPeriodo(args.año, args.mes);

  // Persistencia en Firestore (mismo upsert que el handler manual).
  if (deps.uid && resp.exito !== false) {
    const facturasCount = getAgentSnapshot().facturas.length;
    guardarDeclaracion(deps.uid, {
      tipo: 'mensual',
      periodo: resp.periodo,
      regimen: resp.regimen,
      fecha_calculo: new Date(),
      desglose: {
        total_ingresos_facturados: resp.desglose.total_ingresos_facturados,
        total_ingresos_gravados: resp.desglose.total_ingresos_gravados,
        cantidad_facturas_ingreso: resp.desglose.cantidad_facturas_ingreso ?? 0,
        total_egresos: resp.desglose.total_egresos ?? 0,
        total_deducciones_autorizadas: resp.desglose.total_deducciones_autorizadas ?? 0,
        cantidad_facturas_egreso: resp.desglose.cantidad_facturas_egreso ?? 0,
        base_isr: resp.desglose.base_isr,
        tasa_isr: resp.desglose.tasa_isr,
        isr_causado: resp.desglose.isr_causado,
        isr_retenido: resp.desglose.isr_retenido ?? 0,
        isr_a_pagar: resp.desglose.isr_a_pagar,
        iva_trasladado_cobrado: resp.desglose.iva_trasladado_cobrado ?? 0,
        iva_trasladado_pagado: resp.desglose.iva_trasladado_pagado ?? 0,
        iva_retenido: resp.desglose.iva_retenido ?? 0,
        iva_a_pagar: resp.desglose.iva_a_pagar,
        total_a_pagar: resp.desglose.total_a_pagar,
      },
      explicacion: resp.explicacion ?? null,
      advertencias: resp.advertencias ?? [],
      recomendaciones: resp.recomendaciones ?? [],
      facturas_count: facturasCount,
    }).catch(() => { /* fire-and-forget */ });
  }

  // Opción A — navegar al tab de declaración si el usuario no está ya allí.
  const RUTA_DECLARACION = '/app/store/fiscalito/use?tab=declaracion';
  const enRutaCorrecta =
    window.location.pathname.includes('/store/fiscalito/use') &&
    window.location.search.includes('tab=declaracion');
  if (!enRutaCorrecta) {
    deps.navigate(RUTA_DECLARACION);
  }

  // `exito` es opcional en el response: sólo lo tratamos como fallo cuando
  // viene explícitamente `false`. Si es `undefined` o `true`, es éxito.
  if (resp.exito === false) {
    return {
      ok: false,
      summary: 'El cálculo falló: ' + (resp.advertencias?.join(' | ') ?? 'sin detalle'),
      data: { advertencias: resp.advertencias ?? [] },
    };
  }

  const d = resp.desglose;
  return {
    ok: true,
    summary:
      `Pre-declaración de ${args.mes}/${args.año} calculada. ` +
      `ISR a pagar: $${d.isr_a_pagar.toFixed(2)}. IVA a pagar: $${d.iva_a_pagar.toFixed(2)}. ` +
      `Total: $${(d.isr_a_pagar + d.iva_a_pagar).toFixed(2)}.`,
    data: {
      isr_a_pagar: d.isr_a_pagar,
      iva_a_pagar: d.iva_a_pagar,
      total_a_pagar: d.isr_a_pagar + d.iva_a_pagar,
      base_isr: d.base_isr,
      ingresos_gravados: d.total_ingresos_gravados,
      facturas_count: snapshot.facturas.length,
    },
  };
}

// ────────────────────────────────────────────────────────────
// Registry: nombre → ejecutor
// ────────────────────────────────────────────────────────────

type ToolExecutor = (args: any, deps: ToolDeps) => Promise<ToolResult>;

export const TOOL_EXECUTORS: Record<ToolName, ToolExecutor> = {
  navegar: ejecutarNavegar,
  cargar_xmls_demo: ejecutarCargarXmlsDemo,
  calcular_predeclaracion: ejecutarCalcularPredeclaracion,
};

/** Verifica si el nombre devuelto por el LLM es una tool registrada. */
export function isRegisteredTool(name: string): name is ToolName {
  return name in TOOL_EXECUTORS;
}
