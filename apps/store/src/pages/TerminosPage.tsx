/**
 * Términos y condiciones, página pública `/terminos` (P6-01). Plantilla genérica marcada
 * "REVISAR CON ABOGADO"; los datos del responsable salen de `services/responsable.ts`.
 */

import { Link } from 'react-router-dom';
import PaginaLegal, { Seccion } from '../components/legal/PaginaLegal';
import { responsable } from '../services/responsable';

export default function TerminosPage() {
  const r = responsable();
  return (
    <PaginaLegal titulo="Términos y condiciones" fecha={r.fechaAviso}>
      <Seccion titulo="1. Partes y aceptación">
        <p>
          Estos términos regulan el uso de {r.marca}, que opera {r.nombre} ({r.domicilio}). Al
          crear una cuenta, el despacho los acepta junto con el{' '}
          <Link to="/privacidad">aviso de privacidad</Link>.
        </p>
      </Seccion>
      <Seccion titulo="2. El servicio">
        <p>
          {r.marca} es una herramienta para despachos contables: bóveda de CFDI, contabilidad,
          cálculos de impuestos, nómina y timbrado por medio de un proveedor autorizado. Los
          cálculos son de apoyo: la revisión, la presentación de declaraciones y la
          responsabilidad frente a la autoridad son del despacho y de sus clientes.
        </p>
      </Seccion>
      <Seccion titulo="3. Cuenta y usuarios">
        <p>
          El dueño de la cuenta responde por los usuarios que invita y por los permisos que les
          da. Las credenciales (contraseñas, e.firma, CSD) son confidenciales y su resguardo es
          responsabilidad de quien las carga.
        </p>
      </Seccion>
      <Seccion titulo="4. Datos del despacho">
        <p>
          Los datos que el despacho carga son suyos. Puede exportarlos en cualquier momento y
          borrar su cuenta; el borrado es definitivo e incluye sus archivos y sus respaldos.
        </p>
      </Seccion>
      <Seccion titulo="5. Planes y pagos">
        <p>
          El precio y los límites de cada plan se muestran en la pantalla de Planes. Si el pago no
          se cubre, la cuenta pasa a solo lectura; exportar y borrar los datos siguen disponibles.
        </p>
      </Seccion>
      <Seccion titulo="6. Limitación de responsabilidad">
        <p>
          El servicio se presta "tal cual". El Responsable no responde por multas, recargos o
          daños derivados de información capturada con errores, de decisiones tomadas con base en
          los cálculos sin revisión profesional, ni de fallas de servicios de terceros (SAT, PAC,
          bancos).
        </p>
      </Seccion>
      <Seccion titulo="7. Contacto, cambios y jurisdicción">
        <p>
          Contacto: {r.correo}. Los cambios a estos términos se publican en esta página. Para su
          interpretación aplican las leyes federales de México.
        </p>
      </Seccion>
    </PaginaLegal>
  );
}
