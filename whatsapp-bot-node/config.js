/**
 * Configuración del Bot de WhatsApp
 */

module.exports = {
    // Credenciales ENTEL
    ENTEL_USERNAME: 'ventas.admin2@entelempresa.pe',
    ENTEL_PASSWORD: 'Interconexion123.',
    ENTEL_URL: 'https://entel.insolutions.pe/entelid-portal/Account/Login',

    // Credenciales Portal Factibilidad Claro
    FACTIBILIDAD_URL: 'https://172.19.90.243/portalfactibilidad/public/',
    FACTIBILIDAD_USERNAME: 'D99957628',
    FACTIBILIDAD_PASSWORD: 'Europa1234*',

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
