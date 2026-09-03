/**
 * La marca del producto, en un solo lugar. (O-02)
 *
 * POR QUÉ UNA CONSTANTE Y NO UN BUSCAR-Y-REEMPLAZAR
 * -------------------------------------------------
 * El producto se llamó "Fiscalito Store" mientras fue un marketplace de
 * servicios fiscales; con el pivote de la corrida O es la nómina de **Orca
 * Ordorica Cristal Templado**. Que vuelva a cambiar de nombre es probable —el
 * modo despacho se retomará en otro repo, y esto se puede licenciar a otra
 * empresa—, así que el nombre vive aquí y el próximo rebrand es **un cambio en
 * un archivo**, no cuarenta cadenas repartidas por la app.
 *
 * QUÉ ES "TEXTO VISIBLE" Y QUÉ NO
 * -------------------------------
 * Sólo cambia lo que un usuario **lee en pantalla o en un PDF**. Los nombres
 * internos del repo NO se tocan, y es una instrucción explícita de la tarea:
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
 * documentos ya escritos a cambio de nada: nadie las ve.
 *
 * EL PREFIJO DE ARCHIVO ES APARTE, Y A PROPÓSITO
 * ----------------------------------------------
 * `PREFIJO_ARCHIVO` no lleva espacios, acentos ni guiones largos porque acaba
 * en el nombre de una descarga. `MARCA` sí los lleva. Derivar uno del otro con
 * un `replace` metería la regla de saneamiento de nombres de archivo en el
 * módulo de la marca, y son dos cosas distintas.
 */

/** El nombre completo del producto. Encabezados, títulos y pies. */
export const MARCA = 'Orca Ordorica — Nómina';

/** Sólo la empresa, para cuando el contexto ya dice que es la nómina. */
export const MARCA_CORTA = 'Orca Ordorica';

/**
 * Las dos mitades del logotipo, que se pintan con estilos distintos: la primera
 * lleva el gradiente y la segunda va en gris.
 *
 * Se declaran partidas en vez de cortar `MARCA` en tiempo de render: un
 * `split()` sobre el nombre deja el logotipo a merced de que la marca siguiente
 * tenga exactamente dos palabras.
 */
export const MARCA_LOGO_1 = 'Orca';
export const MARCA_LOGO_2 = 'Ordorica';

/** La inicial del sidebar en móvil, donde no cabe el nombre. */
export const MARCA_INICIAL = 'O';

/**
 * El asistente de voz y de texto.
 *
 * Es una entidad distinta del producto —se presenta, responde y firma— así que
 * tiene su propia constante. El *system prompt* del agente la usa: si dijera
 * "Fiscalito" en duro, el bot seguiría presentándose con el nombre viejo aunque
 * toda la interfaz dijera otro, que es la peor versión de un rebrand a medias.
 */
export const ASISTENTE = 'Orca';

/** Prefijo de los archivos que se descargan. Sin espacios ni acentos. */
export const PREFIJO_ARCHIVO = 'OrcaOrdorica';
