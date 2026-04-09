/** Servicio para guardar y leer declaraciones/cálculos de Firestore */

import {
  collection,
  doc,
  setDoc,
  deleteDoc,
  query,
  orderBy,
  limit as firestoreLimit,
  where,
  getDocs,
  Timestamp,
} from 'firebase/firestore';
import { db } from './firebase';
import type { DIOTResponse, RetencionesResponse, MultiPeriodoResponse, EstadoCuentaResponse } from './fiscalAgentApi';

// ── Tipos ──

export type HistorialCategoria =
  | 'predeclaracion'
  | 'diot'
  | 'retenciones'
  | 'multiperiodo'
  | 'estado_cuenta'
  | 'deducciones';

export interface DesgloseRecord {
  total_ingresos_facturados: number;
  total_ingresos_gravados: number;
  cantidad_facturas_ingreso: number;
  total_egresos: number;
  total_deducciones_autorizadas: number;
  cantidad_facturas_egreso: number;
  base_isr: number;
  tasa_isr: number;
  isr_causado: number;
  isr_retenido: number;
  isr_a_pagar: number;
  iva_trasladado_cobrado: number;
  iva_trasladado_pagado: number;
  iva_retenido: number;
  iva_a_pagar: number;
  total_a_pagar: number;
}

export interface DeclaracionRecord {
  id?: string;
  categoria: HistorialCategoria;
  tipo: string;
  periodo: string;
  regimen: string;
  fecha_calculo: Timestamp | Date;
  // Pre-declaración / deducciones fields
  desglose?: DesgloseRecord;
  explicacion?: string | null;
  advertencias?: string[];
  recomendaciones?: string[];
  facturas_count?: number;
  // DIOT fields
  proveedores?: { rfc: string; nombre: string; total_operaciones: number; iva_pagado: number; cantidad_facturas: number }[];
  total_operaciones?: number;
  total_iva?: number;
  // Retenciones fields
  terceros?: { rfc: string; nombre: string; total_pagado: number; isr_retenido: number; iva_retenido: number; cantidad_facturas: number }[];
  total_isr_retenido?: number;
  total_iva_retenido?: number;
  // Multi-periodo fields
  resultados?: { periodo: string; isr: number; iva: number; total: number; facturas: number }[];
  acumulado?: { total_isr: number; total_iva: number; total_general: number; promedio: number; tendencia: string };
  // Estado de cuenta fields
  estado_cuenta?: {
    ingresos_acumulados: number;
    egresos_acumulados: number;
    isr_estimado: number;
    isr_retenido: number;
    isr_faltante: number;
    iva_neto: number;
  };
}

export interface DashboardStats {
  totalDeclaraciones: number;
  declaracionesEsteMes: number;
  ultimoISR: number;
  ultimoIVA: number;
  ultimoTotal: number;
  saldoFavorAcumulado: number;
  promedioMensual: number;
}

// ── Helpers ──

function declaracionesRef(uid: string) {
  return collection(db, 'users', uid, 'declaraciones');
}

// ── Upsert helper ──

function generarDocId(categoria: string, periodo: string): string {
  const raw = `${categoria}_${periodo}`;
  return raw
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9_]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '');
}

async function upsertDeclaracion(
  uid: string,
  categoria: HistorialCategoria,
  periodo: string,
  docData: Record<string, unknown>
): Promise<string> {
  const docId = generarDocId(categoria, periodo);
  await setDoc(doc(declaracionesRef(uid), docId), docData);
  return docId;
}

// ── Guardar pre-declaración (backward compatible) ──

export async function guardarDeclaracion(
  uid: string,
  data: Omit<DeclaracionRecord, 'id' | 'categoria'>,
  categoria: HistorialCategoria = 'predeclaracion'
): Promise<string> {
  const docData = {
    ...data,
    categoria,
    fecha_calculo: Timestamp.now(),
  };
  return upsertDeclaracion(uid, categoria, data.periodo, docData);
}

// ── Guardar DIOT ──

export async function guardarDIOT(
  uid: string,
  res: DIOTResponse,
  facturasCount: number
): Promise<string> {
  return upsertDeclaracion(uid, 'diot', res.periodo, {
    categoria: 'diot' as HistorialCategoria,
    tipo: 'diot',
    periodo: res.periodo,
    regimen: '',
    fecha_calculo: Timestamp.now(),
    facturas_count: facturasCount,
    proveedores: res.proveedores.map((p) => ({
      rfc: p.rfc, nombre: p.nombre, total_operaciones: p.total_operaciones,
      iva_pagado: p.iva_pagado, cantidad_facturas: p.cantidad_facturas,
    })),
    total_operaciones: res.total_operaciones,
    total_iva: res.total_iva,
  });
}

// ── Guardar Retenciones ──

export async function guardarRetenciones(
  uid: string,
  res: RetencionesResponse,
  facturasCount: number
): Promise<string> {
  return upsertDeclaracion(uid, 'retenciones', res.periodo, {
    categoria: 'retenciones' as HistorialCategoria,
    tipo: 'retenciones',
    periodo: res.periodo,
    regimen: '',
    fecha_calculo: Timestamp.now(),
    facturas_count: facturasCount,
    terceros: res.terceros.map((t) => ({
      rfc: t.rfc, nombre: t.nombre, total_pagado: t.total_pagado,
      isr_retenido: t.isr_retenido, iva_retenido: t.iva_retenido,
      cantidad_facturas: t.cantidad_facturas,
    })),
    total_isr_retenido: res.total_isr_retenido,
    total_iva_retenido: res.total_iva_retenido,
  });
}

// ── Guardar Multi-periodo ──

export async function guardarMultiPeriodo(
  uid: string,
  res: MultiPeriodoResponse
): Promise<string> {
  return upsertDeclaracion(uid, 'multiperiodo', `Año ${res.year}`, {
    categoria: 'multiperiodo' as HistorialCategoria,
    tipo: 'multiperiodo',
    periodo: `Año ${res.year}`,
    regimen: '',
    fecha_calculo: Timestamp.now(),
    resultados: res.resultados.map((r) => ({
      periodo: r.periodo,
      isr: r.desglose.isr_a_pagar,
      iva: r.desglose.iva_a_pagar,
      total: r.desglose.total_a_pagar,
      facturas: r.desglose.cantidad_facturas_ingreso ?? 0,
    })),
    acumulado: {
      total_isr: res.acumulado.total_isr_pagado,
      total_iva: res.acumulado.total_iva_pagado,
      total_general: res.acumulado.total_general_pagado,
      promedio: res.acumulado.promedio_mensual,
      tendencia: res.acumulado.tendencia,
    },
  });
}

// ── Guardar Estado de cuenta ──

export async function guardarEstadoCuenta(
  uid: string,
  res: EstadoCuentaResponse
): Promise<string> {
  const ivaNeto = res.iva_cobrado_acumulado - res.iva_pagado_acumulado - res.iva_retenido_acumulado;
  return upsertDeclaracion(uid, 'estado_cuenta', `Año ${res.year}`, {
    categoria: 'estado_cuenta' as HistorialCategoria,
    tipo: 'estado_cuenta',
    periodo: `Año ${res.year}`,
    regimen: '',
    fecha_calculo: Timestamp.now(),
    advertencias: res.advertencias,
    estado_cuenta: {
      ingresos_acumulados: res.ingresos_acumulados,
      egresos_acumulados: res.egresos_acumulados,
      isr_estimado: res.isr_anual_estimado,
      isr_retenido: res.isr_retenido_acumulado,
      isr_faltante: res.isr_faltante,
      iva_neto: ivaNeto,
    },
  });
}

// ── Leer historial ──

export async function obtenerHistorial(
  uid: string,
  maxResults = 20,
  categoria?: HistorialCategoria
): Promise<DeclaracionRecord[]> {
  const q = categoria
    ? query(
        declaracionesRef(uid),
        where('categoria', '==', categoria),
        orderBy('fecha_calculo', 'desc'),
        firestoreLimit(maxResults)
      )
    : query(
        declaracionesRef(uid),
        orderBy('fecha_calculo', 'desc'),
        firestoreLimit(maxResults)
      );
  const snapshot = await getDocs(q);
  return snapshot.docs.map((doc) => {
    const data = doc.data();
    return {
      id: doc.id,
      ...data,
      // Backward compatible: old records without categoria default to 'predeclaracion'
      categoria: data.categoria ?? 'predeclaracion',
    } as DeclaracionRecord;
  });
}

// ── Limpieza de duplicados históricos ──

const MESES: Record<string, number> = {
  enero: 1, febrero: 2, marzo: 3, abril: 4, mayo: 5, junio: 6,
  julio: 7, agosto: 8, septiembre: 9, octubre: 10, noviembre: 11, diciembre: 12,
};

export async function limpiarDuplicados(uid: string): Promise<number> {
  const q = query(declaracionesRef(uid), orderBy('fecha_calculo', 'desc'));
  const snapshot = await getDocs(q);

  const grupos = new Map<string, { id: string; fecha: Date }[]>();

  for (const d of snapshot.docs) {
    const data = d.data();
    const key = `${data.categoria ?? 'predeclaracion'}_${data.periodo ?? ''}`;
    const fecha = data.fecha_calculo instanceof Timestamp
      ? data.fecha_calculo.toDate()
      : new Date(data.fecha_calculo);
    if (!grupos.has(key)) grupos.set(key, []);
    grupos.get(key)!.push({ id: d.id, fecha });
  }

  let eliminados = 0;
  for (const entries of grupos.values()) {
    if (entries.length <= 1) continue;
    entries.sort((a, b) => b.fecha.getTime() - a.fecha.getTime());
    for (let i = 1; i < entries.length; i++) {
      await deleteDoc(doc(declaracionesRef(uid), entries[i].id));
      eliminados++;
    }
  }
  return eliminados;
}

// ── Helper para parsear periodos ──

function parsearPeriodo(periodo: string): { month: number; year: number } | null {
  const parts = periodo.toLowerCase().trim().split(/\s+/);
  if (parts.length < 2) return null;
  // "Bimestre 1 2026" → último mes del bimestre
  if (parts[0] === 'bimestre') {
    const bim = parseInt(parts[1]);
    const year = parseInt(parts[2]);
    if (!bim || isNaN(year)) return null;
    return { month: bim * 2, year };
  }
  // "Enero 2026"
  const month = MESES[parts[0]];
  const year = parseInt(parts[parts.length - 1]);
  if (!month || isNaN(year)) return null;
  return { month, year };
}

// ── Obtener acumulado de meses anteriores (Art. 106) ──

export async function obtenerAcumuladoAnterior(
  uid: string,
  year: number,
  currentMonth: number
): Promise<{
  ingresos_acumulados: number;
  deducciones_acumuladas: number;
  isr_pagado_anterior: number;
  isr_retenido_acumulado: number;
  meses_encontrados: number[];
  meses_faltantes: number[];
}> {
  const q = query(
    declaracionesRef(uid),
    where('categoria', '==', 'predeclaracion')
  );
  const snapshot = await getDocs(q);

  let ingresos = 0;
  let deducciones = 0;
  let isrPagado = 0;
  let isrRetenido = 0;
  const mesesEncontrados: number[] = [];

  for (const d of snapshot.docs) {
    const data = d.data();
    const periodo: string = data.periodo ?? '';
    const parsed = parsearPeriodo(periodo);
    if (!parsed || parsed.year !== year) continue;
    if (parsed.month >= currentMonth) continue; // Solo anteriores

    const desg = data.desglose;
    if (!desg) continue;

    ingresos += desg.total_ingresos_gravados ?? 0;
    deducciones += desg.total_deducciones_autorizadas ?? 0;
    isrPagado += desg.isr_a_pagar ?? 0;
    isrRetenido += desg.isr_retenido ?? 0;
    mesesEncontrados.push(parsed.month);
  }

  const mesesRequeridos = Array.from({ length: currentMonth - 1 }, (_, i) => i + 1);
  const mesesFaltantes = mesesRequeridos.filter((m) => !mesesEncontrados.includes(m));

  return {
    ingresos_acumulados: ingresos,
    deducciones_acumuladas: deducciones,
    isr_pagado_anterior: isrPagado,
    isr_retenido_acumulado: isrRetenido,
    meses_encontrados: mesesEncontrados.sort((a, b) => a - b),
    meses_faltantes: mesesFaltantes,
  };
}

// ── Obtener ISR pagado en meses anteriores del mismo año ──

export async function obtenerISRPagadoAnterior(
  uid: string,
  year: number,
  currentMonth: number
): Promise<number> {
  const q = query(
    declaracionesRef(uid),
    where('categoria', '==', 'predeclaracion')
  );
  const snapshot = await getDocs(q);
  let suma = 0;

  for (const d of snapshot.docs) {
    const data = d.data();
    const periodo: string = data.periodo ?? '';
    // Parsear "Enero 2026", "Bimestre 1 2026", etc.
    const parts = periodo.toLowerCase().split(' ');
    let mes = 0;
    let anio = 0;

    if (parts[0] === 'bimestre') {
      // "Bimestre 1 2026" → último mes del bimestre
      const bim = parseInt(parts[1]) || 0;
      mes = bim * 2;
      anio = parseInt(parts[2]) || 0;
    } else {
      // "Enero 2026"
      mes = MESES[parts[0]] || 0;
      anio = parseInt(parts[1]) || 0;
    }

    if (anio === year && mes > 0 && mes < currentMonth && data.desglose?.isr_a_pagar != null) {
      suma += data.desglose.isr_a_pagar;
    }
  }

  return suma;
}

// ── Borrar todas las declaraciones de un usuario ──

export async function borrarTodasDeclaraciones(uid: string): Promise<number> {
  const snapshot = await getDocs(declaracionesRef(uid));
  if (snapshot.empty) return 0;
  await Promise.all(snapshot.docs.map((d) => deleteDoc(doc(declaracionesRef(uid), d.id))));
  return snapshot.size;
}

// ── Estadísticas (solo pre-declaraciones) ──

export async function obtenerEstadisticas(uid: string): Promise<DashboardStats> {
  const declaraciones = await obtenerHistorial(uid, 100);
  // Filter to only predeclaracion/deducciones for stats
  const predeclaraciones = declaraciones.filter(
    (d) => d.categoria === 'predeclaracion' || d.categoria === 'deducciones' || !d.categoria
  );

  const ahora = new Date();
  const mesActual = ahora.getMonth();
  const anioActual = ahora.getFullYear();

  const declaracionesEsteMes = declaraciones.filter((d) => {
    const fecha = d.fecha_calculo instanceof Timestamp
      ? d.fecha_calculo.toDate()
      : new Date(d.fecha_calculo);
    return fecha.getMonth() === mesActual && fecha.getFullYear() === anioActual;
  }).length;

  const ultima = predeclaraciones[0] ?? null;

  let saldoFavorAcumulado = 0;
  let sumaTotal = 0;

  for (const d of predeclaraciones) {
    if (!d.desglose) continue;
    sumaTotal += d.desglose.total_a_pagar;
    if (d.desglose.isr_a_pagar <= 0 && d.desglose.isr_retenido > 0) {
      saldoFavorAcumulado += d.desglose.isr_retenido - d.desglose.isr_causado;
    }
  }

  return {
    totalDeclaraciones: declaraciones.length,
    declaracionesEsteMes,
    ultimoISR: ultima?.desglose?.isr_a_pagar ?? 0,
    ultimoIVA: ultima?.desglose?.iva_a_pagar ?? 0,
    ultimoTotal: ultima?.desglose?.total_a_pagar ?? 0,
    saldoFavorAcumulado,
    promedioMensual: predeclaraciones.length > 0 ? sumaTotal / predeclaraciones.length : 0,
  };
}
