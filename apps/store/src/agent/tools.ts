/**
 * Ejecutores de las tools del agente que operan la PANTALLA.
 *
 * P5-07: el catálogo que ve el LLM (nombres, descripciones y esquemas) vive en el SERVIDOR
 * (`apps/api/app/asistente/herramientas.py`); el navegador ya no manda esquemas. Aquí quedan
 * los ejecutores, que vuelven a validar sus argumentos, y `RUTAS_BASE`, espejo de
 * `RUTAS_NAVEGAR` del servidor.
 *
 * Día 1 — tres tools:
 *   1. navegar               → cambia de ruta (reemplaza tags [NAVEGAR:])
 *   2. cargar_xmls_demo      → lee XMLs de /public/demo-xmls/{año}/{mes}/
 *   3. calcular_predeclaracion → llama al Fiscal Agent API con perfil + CFDIs
 */

import type { NavigateFunction } from 'react-router-dom';
import type { UserProfile } from '../context/ProfileContext';
import { mensajeFalta, type PerfilFiscal } from '../context/perfilFiscal';
import { parseMultipleCFDI } from '../services/cfdiParser';
import {
  calcularPreDeclaracion,
  type CFDI,
  type PreDeclaracionRequest, facturasFiscales } from '../services/fiscalAgentApi';
import { guardarDeclaracion } from '../services/declaracionesHistory';
import { getAgentActions, getAgentSnapshot } from './AgentContext';
import type { ToolName, ToolResult } from './types';

// ────────────────────────────────────────────────────────────
// Rutas válidas de `navegar`
// ────────────────────────────────────────────────────────────

/**
 * Rutas válidas que la tool `navegar` puede recibir. El servidor las anuncia como `enum`
 * y el ejecutor las vuelve a revisar: el LLM puede mandar cualquier cadena.
 */
function rutasValidas(): string[] {
  return [...RUTAS_BASE];
}

const RUTAS_BASE = [
  // E-01: la cartera del despacho. Es también la entrada (`/app` redirige aquí).
  '/app/clientes',
  // R-05: empleados y dispositivos del cliente activo.
  '/app/empleados',
  '/app/dispositivos',
  // E-07: el calendario PATRONAL de los clientes del despacho. Sin esto,
  // "llévame al calendario" mandaba a un contador al tab de contribuyente, que
  // desde E-05 ni siquiera puede cargar (no hay RFC ni régimen que capturar).
  '/app/calendario',
  // E-03: resuelve el cliente activo y redirige a su nómina. Va esta ruta y no
  // `/app/clientes/{id}/nomina` porque el enum es cerrado y no admite un id.
  '/app/nomina',
  '/app/store',
  '/app/store/fiscalito/use',
  '/app/store/contabilito/use',
  '/app/profile',
  // Tabs internos de Fiscalito
  '/app/store/fiscalito/use?tab=declaracion',
  '/app/store/fiscalito/use?tab=anual',
  '/app/store/fiscalito/use?tab=calendario',
  '/app/store/fiscalito/use?tab=comparar',
  '/app/store/fiscalito/use?tab=diot',
  '/app/store/fiscalito/use?tab=retenciones',
  '/app/store/fiscalito/use?tab=multiperiodo',
  '/app/store/fiscalito/use?tab=estado-cuenta',
  '/app/store/fiscalito/use?tab=deducciones',
  '/app/store/fiscalito/use?tab=pagospm',
] as const;

// ────────────────────────────────────────────────────────────
// Dependencias inyectadas a los ejecutores
// ────────────────────────────────────────────────────────────

export interface ToolDeps {
  navigate: NavigateFunction;
  profile: UserProfile;
  /** K: el cliente activo del despacho. Sobre él se calcula todo. */
  perfilFiscal: PerfilFiscal;
  uid: string | null;
}

// ────────────────────────────────────────────────────────────
// Ejecutores
// ────────────────────────────────────────────────────────────

async function ejecutarNavegar(
  args: { ruta: string },
  deps: ToolDeps,
): Promise<ToolResult> {
  // Se vuelve a consultar aquí y no se confía en el enum del schema: el LLM
  // puede mandar cualquier cadena.
  if (!rutasValidas().includes(args.ruta)) {
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
  deps: ToolDeps,
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

  // B-01: una factura de compra también es TipoDeComprobante="I" (lo emite el
  // proveedor), así que contar por tipo daba siempre "0 egreso(s)". Lo que
  // distingue emitidas de recibidas es el RFC del cliente activo: emitida si él
  // es el emisor, recibida si él es el receptor. Sin RFC capturado, el tipo del
  // comprobante es lo único que hay.
  const { ingresos, egresos } = contarEmitidasYRecibidas(nuevas, deps.perfilFiscal.rfc);

  return {
    ok: true,
    summary:
      `Cargué ${nuevas.length} factura(s) demo de ${mesPadded}/${año} ` +
      `(${ingresos} emitida(s), ${egresos} recibida(s)). ` +
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

/**
 * Cuenta facturas emitidas (ingresos) y recibidas (egresos) por RFC del
 * contribuyente. Si no hay RFC, cae al tipo de comprobante (I/E).
 */
export function contarEmitidasYRecibidas(
  facturas: CFDI[],
  rfcContribuyente: string | undefined,
): { ingresos: number; egresos: number } {
  const rfc = (rfcContribuyente ?? '').trim().toUpperCase();
  if (!rfc) {
    return {
      ingresos: facturas.filter((f) => f.tipo === 'I').length,
      egresos: facturas.filter((f) => f.tipo === 'E').length,
    };
  }
  const ingresos = facturas.filter((f) => f.rfc_emisor.toUpperCase() === rfc).length;
  const egresos = facturas.filter(
    (f) => f.rfc_emisor.toUpperCase() !== rfc && f.rfc_receptor.toUpperCase() === rfc,
  ).length;
  return { ingresos, egresos };
}

async function ejecutarCalcularPredeclaracion(
  args: { año: number; mes: number },
  deps: ToolDeps,
): Promise<ToolResult> {
  const { perfilFiscal } = deps;
  const snapshot = getAgentSnapshot();

  // K: se calcula sobre el CLIENTE ACTIVO del despacho, nunca sobre el despacho.
  if (perfilFiscal.falta) {
    return {
      ok: false,
      summary: 'Faltan datos del cliente para calcular',
      error: `${mensajeFalta(perfilFiscal.falta)} Explícaselo al contador; el cliente se ` +
        'elige y se edita en /app/clientes.',
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
      rfc: perfilFiscal.rfc,
      regimen: perfilFiscal.regimen,
      nombre: perfilFiscal.nombre,
      contributor_type: perfilFiscal.contributorType,
    },
    // T4: los recibos de nómina no son facturas del contribuyente.
    facturas: facturasFiscales(snapshot.facturas),
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
    }, 'predeclaracion', perfilFiscal.clienteId ?? undefined).catch(() => { /* fire-and-forget */ });
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

// Firma en forma de método para que cada ejecutor declare sus argumentos
// concretos (`{ año, mes }`) y aun así quepa en el registro: los parámetros de
// un método son bivariantes, los de un tipo función no.
type ToolExecutor = {
  ejecutar(args: Record<string, unknown>, deps: ToolDeps): Promise<ToolResult>;
}['ejecutar'];

export const TOOL_EXECUTORS: Record<ToolName, ToolExecutor> = {
  navegar: ejecutarNavegar,
  cargar_xmls_demo: ejecutarCargarXmlsDemo,
  calcular_predeclaracion: ejecutarCalcularPredeclaracion,
};

/** Verifica si el nombre devuelto por el LLM es una tool registrada. */
export function isRegisteredTool(name: string): name is ToolName {
  return name in TOOL_EXECUTORS;
}
