/**
 * La marca del producto, en un solo lugar. (O-02)
 *
 * POR QUÉ UNA CONSTANTE Y NO UN BUSCAR-Y-REEMPLAZAR
 * -------------------------------------------------
 * El producto se llamó "Fiscalito Store" mientras fue un marketplace de
 * servicios fiscales; con el pivote de la corrida O pasó a ser la nómina de
 * Orca Ordorica Cristal Templado, y **vuelve a ser Fiscalito**: la suite
 * fiscal, de nómina y de contabilidad que se le vende a un despacho. Que el
 * nombre cambie otra vez es probable, así que vive aquí y cada rebrand es **un
 * cambio en un archivo**, no cuarenta cadenas repartidas por la app. Este
 * tercer cambio de nombre costó exactamente eso, y es la prueba de que el
 * módulo valía la pena.
 *
 * QUÉ ES "TEXTO VISIBLE" Y QUÉ NO
 * -------------------------------
 * Sólo cambia lo que un usuario **lee en pantalla o en un PDF**. Los nombres
 * internos del repo NO se tocan:
 *
 * - nombres de archivo y de componente (`FiscalitoVoiceChat`,
 *   `FiscalitoServicePage`, `fiscalAgentApi.ts`),
 * - la ruta `/app/store/fiscalito/use` y el id `fiscalito` del catálogo de
 *   servicios,
 * - el tipo `TabFiscalito`,
 * - las llaves de `localStorage` (`fiscalito_cliente_activo`,
 *   `fiscalito_profile`) y las colecciones de Firestore.
 *
 * Renombrar cualquiera de esas rompería sesiones guardadas, enlaces y
 * documentos ya escritos a cambio de nada: nadie las ve. Que hoy coincidan con
 * la marca es una casualidad de este rebrand, no una regla nueva.
 *
 * **Y tampoco se toca la razón social de un CLIENTE.** "Orca Ordorica Cristal
 * Templado S.A. de C.V." sigue apareciendo como dato —es una empresa real
 * dada de alta en Firestore, y el `placeholder` de `ConfiguracionEmpresa` la
 * usa de ejemplo— porque es un REGISTRO, no la marca del producto.
 *
 * EL PREFIJO DE ARCHIVO ES APARTE, Y A PROPÓSITO
 * ----------------------------------------------
 * `PREFIJO_ARCHIVO` no lleva espacios, acentos ni guiones largos porque acaba
 * en el nombre de una descarga. Con esta marca coinciden; con la anterior
 * (`Orca Ordorica — Nómina` / `OrcaOrdorica`) no coincidían, y derivar uno del
 * otro con un `replace` metería la regla de saneamiento de nombres de archivo
 * en el módulo de la marca. Son dos cosas distintas y se quedan separadas.
 */

/** El nombre completo del producto. Encabezados, títulos y pies. */
export const MARCA = 'Fiscalito';

/**
 * Sólo el nombre corto, para cuando el contexto ya dice de qué se trata.
 *
 * Hoy es idéntico a `MARCA` porque la marca es de una sola palabra. Se
 * conserva como constante propia y no como alias porque las dos posiciones son
 * distintas —una es el título, la otra la etiqueta de un sidebar— y la marca
 * anterior sí las distinguía (`Orca Ordorica — Nómina` contra `Orca
 * Ordorica`). Colapsarlas ahora obligaría a volver a separarlas al siguiente
 * nombre compuesto.
 */
export const MARCA_CORTA = 'Fiscalito';

/**
 * El logotipo, que se pinta con el gradiente de la marca.
 *
 * Antes eran DOS mitades con estilos distintos (`MARCA_LOGO_1` en gradiente y
 * `MARCA_LOGO_2` en gris), porque el nombre tenía dos palabras. "Fiscalito"
 * tiene una: partirla daría un wordmark con una costura arbitraria a media
 * palabra. Se pinta entera y en gradiente.
 */
export const MARCA_LOGO = 'Fiscalito';

/** La inicial del sidebar en móvil, donde no cabe el nombre. */
export const MARCA_INICIAL = 'F';

/**
 * El asistente de voz y de texto.
 *
 * Es una entidad distinta del producto —se presenta, responde y firma— así que
 * tiene su propia constante aunque hoy se llame igual. El *system prompt* del
 * agente la usa: si dijera el nombre en duro, el bot seguiría presentándose
 * con el nombre viejo aunque toda la interfaz dijera otro, que es la peor
 * versión de un rebrand a medias.
 */
export const ASISTENTE = 'Fiscalito';

/** Prefijo de los archivos que se descargan. Sin espacios ni acentos. */
export const PREFIJO_ARCHIVO = 'Fiscalito';
