/**
 * Aviso de privacidad integral (LFPDPPP), página pública `/privacidad` (P6-01).
 *
 * Plantilla genérica: los datos del responsable salen de `services/responsable.ts`
 * (`VITE_RESPONSABLE_*`) y la página dice en una banda que debe revisarla un abogado.
 */

import PaginaLegal, { Seccion } from '../components/legal/PaginaLegal';
import { responsable } from '../services/responsable';

export default function AvisoPrivacidadPage() {
  const r = responsable();
  return (
    <PaginaLegal titulo="Aviso de privacidad" fecha={r.fechaAviso}>
      <Seccion titulo="1. Responsable">
        <p>
          {r.nombre}, con domicilio en {r.domicilio} (en adelante, "el Responsable"), opera {r.marca}{' '}
          y es responsable del tratamiento de los datos personales que se recaban por medio de la
          plataforma, conforme a la Ley Federal de Protección de Datos Personales en Posesión de
          los Particulares (LFPDPPP) y su Reglamento.
        </p>
      </Seccion>
      <Seccion titulo="2. Datos que se tratan">
        <p>
          De los usuarios del despacho: nombre, correo electrónico y teléfono. De los clientes del
          despacho y sus trabajadores, que el despacho captura o carga: nombre o razón social,
          RFC, CURP, NSS, domicilio fiscal, comprobantes fiscales (CFDI), datos de nómina
          (salarios, percepciones, deducciones), datos bancarios para dispersión (CLABE y número
          de cuenta) y certificados de e.firma y CSD.
        </p>
        <p>
          Respecto de los datos de sus clientes y trabajadores, el despacho es el responsable y el
          Responsable de {r.marca} actúa como encargado que los trata por cuenta del despacho.
        </p>
      </Seccion>
      <Seccion titulo="3. Finalidades">
        <p>
          Primarias (necesarias para el servicio): crear y administrar la cuenta; llevar la
          contabilidad, los cálculos fiscales y la nómina de los clientes del despacho; timbrar
          comprobantes por medio de un proveedor autorizado; enviar documentos que el despacho
          ordene; dar soporte y cumplir obligaciones legales.
        </p>
        <p>
          Secundarias: avisos sobre nuevas funciones. Puede negarse a ellas escribiendo a {r.correo}{' '}
          sin que eso afecte el servicio.
        </p>
      </Seccion>
      <Seccion titulo="4. Transferencias y encargados">
        <p>
          Los datos se comunican sólo a proveedores necesarios para prestar el servicio
          (alojamiento, almacenamiento, correo, mensajería, timbrado y autenticación) y a las
          autoridades cuando la ley lo exija. Los proveedores actúan como encargados y no usan los
          datos para fines propios.
        </p>
      </Seccion>
      <Seccion titulo="5. Seguridad">
        <p>
          Los datos sensibles para la operación (llaves privadas de e.firma y CSD, contraseñas,
          CLABE y números de cuenta) se guardan cifrados. Se hacen respaldos diarios con
          retención limitada y se lleva una bitácora de quién hizo cada cambio.
        </p>
      </Seccion>
      <Seccion titulo="6. Derechos ARCO y revocación del consentimiento">
        <p>
          Puede acceder, rectificar, cancelar u oponerse al tratamiento de sus datos, o revocar su
          consentimiento, escribiendo a {r.correo}. El dueño de la cuenta puede además exportar
          todos los datos del despacho y borrar la cuenta desde Perfil → Datos de la cuenta. La
          solicitud se responde en los plazos que marca la LFPDPPP.
        </p>
      </Seccion>
      <Seccion titulo="7. Cookies y tecnologías similares">
        <p>
          La plataforma usa almacenamiento local del navegador para mantener la sesión y
          preferencias (tema, cliente activo). No se usan para publicidad.
        </p>
      </Seccion>
      <Seccion titulo="8. Cambios al aviso">
        <p>
          Cualquier cambio se publica en esta misma página con su fecha de actualización.
        </p>
      </Seccion>
    </PaginaLegal>
  );
}
