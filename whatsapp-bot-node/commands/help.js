/**
 * Comando .! / .help / .ayuda
 * Muestra la ayuda del bot
 */

module.exports = function helpCommand() {
    return `*Bot de Cobertura Claro*

*Comandos:*

*.!* - Mostrar esta ayuda

*.delivery lat, lng*
Ejemplo: .delivery -12.046, -77.042

*.internet lat, lng*
Ejemplo: .internet -12.046, -77.042

*.ruc NUMERO_RUC*
Ejemplo: .ruc 20123456789

_Coordenadas de Google Maps_`;
};
