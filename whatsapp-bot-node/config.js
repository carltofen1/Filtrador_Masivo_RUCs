/**
 * Configuración del Bot de WhatsApp
 */

module.exports = {
    // Credenciales ENTEL (configurar en variables de entorno)
    ENTEL_USERNAME: process.env.ENTEL_USERNAME || '',
    ENTEL_PASSWORD: process.env.ENTEL_PASSWORD || '',
    ENTEL_URL: 'https://entel.insolutions.pe/entelid-portal/Account/Login',

    // Credenciales Portal Factibilidad Claro (configurar en variables de entorno)
    FACTIBILIDAD_URL: 'https://172.19.90.243/portalfactibilidad/public/',
    FACTIBILIDAD_USERNAME: process.env.FACTIBILIDAD_USERNAME || '',
    FACTIBILIDAD_PASSWORD: process.env.FACTIBILIDAD_PASSWORD || '',

    // URL SUNAT
    SUNAT_URL: 'https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/jcrS00Alias',

    // Comandos disponibles
    COMANDOS: {
        '.!': 'help',
        '.help': 'help',
        '.ayuda': 'help',
        '.delivery': 'delivery',
        '.internet': 'internet',
        '.ruc': 'ruc'
    }
};
