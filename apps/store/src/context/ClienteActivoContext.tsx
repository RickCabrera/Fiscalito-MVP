/**
 * Cliente activo del despacho (E-02).
 *
 * Es lo que hace verdadero el criterio de la tarea —"cambio de cliente y todo
 * lo demás cambia con él"—: la cartera se carga una vez y el resto de las
 * pantallas leen de aquí cuál es el cliente en foco.
 *
 * SÓLO CARGA PARA UN CONTADOR. Un contribuyente no tiene cartera, y pedirla
 * dispararía un fetch a un endpoint que no le sirve en cada arranque de sesión.
 *
 * POR QUÉ UN SOLO `estado` Y NO CUATRO `useState`
 * -----------------------------------------------
 * El efecto no llama a `setState` en su cuerpo: sólo dentro de los callbacks de
 * la promesa. `loading` se DERIVA de `estado.status`, así que habilitar la carga
 * (cuando el perfil termina de llegar) no necesita un `setLoading(true)`
 * síncrono, que es lo que dispara renders en cascada.
 *
 * DEMO — se borra en F2.
 */

import { useCallback, useEffect, useMemo, useState, ReactNode } from 'react';
import { useProfile } from './ProfileContext';
import { esContador } from '../services/navigation';
import { obtenerClientes, type ClienteResumen } from '../services/despachoApi';
import { ClienteActivoContext } from './clienteActivoStore';

const STORAGE_KEY = 'fiscalito_cliente_activo';

type Estado =
  | { status: 'idle' }
  | { status: 'listo'; clientes: ClienteResumen[] }
  | { status: 'error'; mensaje: string };

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

  const [estado, setEstado] = useState<Estado>({ status: 'idle' });
  const [preferido, setPreferido] = useState<string | null>(leerGuardado);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    if (!habilitado) return;

    let cancelado = false;
    obtenerClientes()
      .then((lista) => {
        if (cancelado) return;
        setEstado({ status: 'listo', clientes: lista });
        const elegido = elegirActivo(lista, leerGuardado());
        if (elegido) {
          guardar(elegido);
          setPreferido(elegido);
        }
      })
      .catch((e: unknown) => {
        if (cancelado) return;
        setEstado({
          status: 'error',
          mensaje: e instanceof Error ? e.message : 'Error al cargar la cartera',
        });
      });

    return () => { cancelado = true; };
  }, [habilitado, intento]);

  const setClienteId = useCallback((id: string) => {
    setPreferido(id);
    guardar(id);
  }, []);

  const recargar = useCallback(() => setIntento((n) => n + 1), []);

  const valor = useMemo(() => {
    const clientes = habilitado && estado.status === 'listo' ? estado.clientes : [];
    const clienteId = elegirActivo(clientes, preferido);
    return {
      clientes,
      clienteId,
      cliente: clientes.find((c) => c.id === clienteId) ?? null,
      loading: habilitado && estado.status === 'idle',
      error: estado.status === 'error' ? estado.mensaje : null,
      setClienteId,
      recargar,
    };
  }, [habilitado, estado, preferido, setClienteId, recargar]);

  return (
    <ClienteActivoContext.Provider value={valor}>
      {children}
    </ClienteActivoContext.Provider>
  );
}
