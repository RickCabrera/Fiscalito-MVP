/**
 * Cliente activo del despacho (E-02, R-06).
 *
 * Es lo que hace verdadero el criterio de E-02 —"cambio de cliente y todo lo
 * demás cambia con él"—: el resto de las pantallas leen de aquí cuál es el
 * cliente en foco.
 *
 * R-06: LA CUARTA COSTURA, QUE LEÍA EL CATÁLOGO DEL BACKEND
 * ---------------------------------------------------------
 * Hasta aquí este proveedor llamaba a `obtenerClientes()` —o sea
 * `GET /api/v1/despacho/clientes`, los tres clientes de demostración— y
 * `carteraStore` lo documentaba como decisión: *"sólo necesita resúmenes para
 * el selector del header"*, justificada con que *"el cliente en foco existe en
 * las dos fuentes"*.
 *
 * Esa frase era verdadera **sólo por el fallback** que R-06 elimina. Sin
 * cambiarlo, una cuenta nueva vería su lista de clientes correctamente vacía
 * **y el selector de arriba mostrando los tres de demostración**, con
 * `/app/nomina` llevando a `demo`: exactamente los datos que no son suyos, en
 * la barra superior y en la nómina, que es donde más caro sale.
 *
 * Ahora los resúmenes salen de la CARTERA. Un solo origen para "qué clientes
 * existen", y de paso se cierra el agujero simétrico que ya existía: un cliente
 * dado de alta por el contador no aparecía en el selector, porque el backend no
 * lo conoce.
 *
 * **Esto obliga a que `CarteraProvider` esté POR FUERA** de este proveedor en
 * `main.tsx`. El orden estaba al revés y el comentario que lo justificaba dejó
 * de ser cierto.
 *
 * SÓLO PARA UN CONTADOR. Un contribuyente no tiene cartera.
 */

import { useCallback, useEffect, useMemo, useState, ReactNode } from 'react';
import { useProfile } from './ProfileContext';
import { esContador } from '../services/navigation';
import type { ClienteResumen } from '../services/despachoApi';
import type { ClienteCartera } from '../services/carteraApi';
import { useCartera } from './carteraStore';
import { ClienteActivoContext } from './clienteActivoStore';

const STORAGE_KEY = 'fiscalito_cliente_activo';

/**
 * Proyección de la cartera al resumen que consumen el selector y `AppLayout`.
 *
 * `ClienteCartera` es un superconjunto de `ClienteResumen`, así que esto es
 * estrechar, no inventar: `num_empleados` sale de contar los que trae, que es
 * la misma equivalencia que `ClienteDetallePage` ya hacía.
 */
function comoResumen(c: ClienteCartera): ClienteResumen {
  return {
    id: c.id,
    nombre: c.nombre,
    giro: c.giro,
    origen: c.origen,
    num_empleados: c.empleados.length,
    // T1: el régimen viaja al resumen porque `FiscalitoServicePage` filtra sus
    // tabs con él. Sin esta línea el selector afirma un cliente y la pantalla
    // le aplica el régimen de otro — o el default, callando que lo hace.
    regimen: c.regimen,
    // C-02: y el RFC por la misma razón. Los tabs de Fiscalito clasifican
    // emitidas y recibidas con él (`usePerfilFiscal`); sin esta línea tendrían
    // que ir a la cartera por su cuenta, que sería una segunda costura.
    rfc: c.rfc,
    prima_riesgo: c.prima_riesgo,
    clase_riesgo: c.clase_riesgo,
    clave_periodicidad: c.clave_periodicidad,
    zona: c.zona,
  };
}

function leerGuardado(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    // Modo privado o storage bloqueado: se arranca sin preferencia.
    return null;
  }
}

function guardar(id: string) {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // Que no se pueda recordar la preferencia no es motivo para romper la app.
  }
}

/**
 * Cliente en foco: el guardado si sigue existiendo, si no el primero.
 *
 * Un id viejo en `localStorage` —cartera cambiada entre sesiones— dejaría a la
 * app pidiendo la ficha de un cliente fantasma, que responde 404.
 */
function elegirActivo(clientes: ClienteResumen[], preferido: string | null): string | null {
  if (preferido && clientes.some((c) => c.id === preferido)) return preferido;
  return clientes[0]?.id ?? null;
}

export function ClienteActivoProvider({ children }: { children: ReactNode }) {
  const { profile } = useProfile();
  const habilitado = esContador(profile.contributorType);
  const cartera = useCartera();

  const [preferido, setPreferido] = useState<string | null>(leerGuardado);

  const setClienteId = useCallback((id: string) => {
    setPreferido(id);
    guardar(id);
  }, []);

  const valor = useMemo(() => {
    const clientes = habilitado ? cartera.clientes.map(comoResumen) : [];
    const clienteId = elegirActivo(clientes, preferido);
    return {
      clientes,
      clienteId,
      cliente: clientes.find((c) => c.id === clienteId) ?? null,
      loading: habilitado && cartera.loading,
      error: cartera.error,
      setClienteId,
      recargar: cartera.recargar,
    };
  }, [habilitado, cartera, preferido, setClienteId]);

  /**
   * Persiste el cliente elegido, para que la preferencia sobreviva a la
   * recarga. Va en un efecto y no dentro del `useMemo`: `useMemo` puede
   * recalcularse o descartarse, y un efecto secundario ahí es de las cosas que
   * funcionan hasta que React decide otra cosa. Sólo escribe `localStorage`,
   * así que no dispara renders en cascada.
   */
  useEffect(() => {
    if (valor.clienteId && valor.clienteId !== preferido) guardar(valor.clienteId);
  }, [valor.clienteId, preferido]);

  return (
    <ClienteActivoContext.Provider value={valor}>
      {children}
    </ClienteActivoContext.Provider>
  );
}
