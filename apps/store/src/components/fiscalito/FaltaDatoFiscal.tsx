/**
 * "Captura el RFC de este cliente", con acceso directo a editarlo (C-02).
 *
 * Lo pintan los tabs de Fiscalito en lugar del formulario cuando el cliente
 * activo no tiene con qué calcular. **No** es el "Completa tu perfil" del
 * contribuyente: al contador lo mandaba a un perfil que no tiene esos campos
 * (E-05) y que, aunque los tuviera, no son los del cliente.
 *
 * El acceso reusa `ModalCliente` (C-01) aquí mismo: al guardar, la cartera se
 * actualiza, el cliente activo trae su RFC y el tab aparece sin recargar. Si la
 * cartera no se puede escribir —catálogo de demostración— o no hay proveedor,
 * se manda a la ficha del cliente, que explica por qué no se edita.
 */

import { useContext, useState } from 'react';
import { Link } from 'react-router-dom';
import { Pencil, UserCog } from 'lucide-react';
import { CarteraContext } from '../../context/carteraStore';
import { REGIMEN_CLIENTE_POR_DEFECTO, sinEmpleados } from '../../services/carteraApi';
import { mensajeFalta, type PerfilFiscal } from '../../context/perfilFiscal';
import ModalCliente from '../cartera/ModalCliente';

const EXPLICACION: Record<'rfc' | 'regimen', string> = {
  rfc: 'Con su RFC se decide qué facturas emitió y cuáles recibió: sin él no hay cálculo que hacer.',
  regimen: `Sin régimen capturado no se calcula: los tabs que ves son los del ${REGIMEN_CLIENTE_POR_DEFECTO}, supuesto, y un impuesto calculado con un régimen supuesto no sirve para declarar.`,
};

export default function FaltaDatoFiscal({ perfil }: { perfil: PerfilFiscal }) {
  const cartera = useContext(CarteraContext);
  const [editando, setEditando] = useState(false);

  // 'cliente' (sin cliente elegido) no llega aquí: `FiscalitoServicePage` pinta
  // antes su propio estado vacío. Y 'perfil' es del contribuyente, que conserva
  // su mensaje de siempre dentro de cada tab.
  if (perfil.falta !== 'rfc' && perfil.falta !== 'regimen') return null;
  const completo = perfil.clienteId ? cartera?.clientePorId(perfil.clienteId) ?? null : null;
  const puedeEditar = cartera !== null && completo !== null && !cartera.soloLectura;

  return (
    <div className="card" style={{ textAlign: 'center', padding: 'var(--space-lg)' }}>
      <UserCog size={28} color="var(--warning)" />
      <h3 style={{ margin: '12px 0 6px', fontSize: '1rem', fontWeight: 600 }}>
        {mensajeFalta(perfil.falta)}
      </h3>
      <p style={{ margin: '0 0 16px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
        {perfil.nombre}: {EXPLICACION[perfil.falta]}
      </p>
      {puedeEditar ? (
        <button
          className="btn-primary"
          onClick={() => setEditando(true)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <Pencil size={14} /> Editar cliente
        </button>
      ) : (
        <Link className="btn-primary" to={`/app/clientes/${perfil.clienteId ?? ''}`} style={{ display: 'inline-block' }}>
          Ir a la ficha del cliente
        </Link>
      )}
      {editando && completo && cartera && (
        <ModalCliente
          cliente={sinEmpleados(completo)}
          idsExistentes={cartera.clientes.map((c) => c.id)}
          onGuardar={cartera.guardarCliente}
          onCerrar={() => setEditando(false)}
        />
      )}
    </div>
  );
}
