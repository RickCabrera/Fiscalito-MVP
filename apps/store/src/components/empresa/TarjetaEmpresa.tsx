import type { CarteraContextType } from '../../context/carteraStore';
import ConfiguracionEmpresa from './ConfiguracionEmpresa';

/**
 * La Configuración de empresa, o su esqueleto mientras carga.
 *
 * **No se monta la tarjeta mientras la cartera carga**, y no es cosmético: la
 * tarjeta siembra su estado local del prop, así que montarla con la empresa
 * todavía sin leer pinta cinco campos vacíos y un banner de "falta la razón
 * social" sobre una empresa que sí está configurada. El efecto de
 * resincronización lo repara un instante después — y ese instante es justo el
 * que el operador ve al entrar.
 */
export default function TarjetaEmpresa({ cartera }: { cartera: CarteraContextType }) {
  if (cartera.loading) {
    return (
      <div className="card" style={{ padding: 'var(--space-lg)' }} role="status">
        <span
          className="skeleton"
          aria-hidden="true"
          style={{ display: 'block', width: '100%', height: 96 }}
        />
        Cargando la configuración de la empresa…
      </div>
    );
  }
  /**
   * El `key` es la empresa GUARDADA, no la tecleada.
   *
   * Remonta la tarjeta —y con ella siembra sus campos— cuando el documento
   * cambia: al terminar la lectura inicial, y después de cada guardado. Nunca
   * mientras el operador escribe, porque su estado local no participa del key.
   *
   * Es la alternativa al `useEffect` de resincronización, que hacía `setState`
   * en cascada dentro de un efecto y agregaba un error de lint nuevo a un
   * presupuesto que esta corrida tiene que dejar donde lo encontró.
   */
  const e = cartera.empresa;
  const llave = [
    e.razonSocial, e.rfc, e.registroPatronal, e.primaRiesgo, e.claseRiesgo,
    e.guiaSubdelegacion, e.clavePeriodicidad, JSON.stringify(e.parametros),
  ].join('|');

  return (
    <ConfiguracionEmpresa
      key={llave}
      empresa={cartera.empresa}
      soloLectura={cartera.soloLectura}
      onGuardar={cartera.guardarEmpresa}
    />
  );
}
