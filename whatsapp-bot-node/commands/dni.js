/**
 * Comando .dni NUMERO
 * Consulta datos de RENIEC usando API + Stalking Mode (Foto LinkedIn/Facebook)
 */

const axios = require('axios');
const { MessageMedia } = require('whatsapp-web.js');

const PYTHON_SERVER = 'http://localhost:5555';

module.exports = async function dniCommand(args, msg) {
    // Extraer DNI (solo dígitos)
    const dni = args.replace(/\D/g, '');

    if (!dni || dni.length !== 8) {
        return `*Formato incorrecto*

Uso: .dni NUMERO_DNI
Ejemplo: .dni 12345678

_El DNI debe tener 8 dígitos_`;
    }

    console.log(`   → Consultando RENIEC para DNI ${dni}...`);

    try {
        // Enviar al servidor Python
        const response = await axios.post(PYTHON_SERVER, {
            comando: 'dni',
            args: dni
        }, {
            timeout: 30000, // 30s para dar tiempo al stalking
            headers: { 'Content-Type': 'application/json' }
        });

        const resultado = response.data.resultado;

        // Manejar nuevo formato: {texto, foto_url}
        if (typeof resultado === 'object' && resultado.texto) {
            // Si hay foto, enviarla primero
            if (resultado.foto_url) {
                try {
                    console.log(`   🖼️ Enviando foto de perfil...`);
                    const media = await MessageMedia.fromUrl(resultado.foto_url);
                    await msg.reply(media, undefined, { caption: resultado.texto });
                    return null; // Ya enviamos el mensaje con foto
                } catch (photoError) {
                    console.error('   ⚠️ No se pudo enviar la foto:', photoError.message);
                    // Si falla la foto, solo enviar texto
                    return resultado.texto;
                }
            }

            // Sin foto, solo texto
            return resultado.texto;
        }

        // Retrocompatibilidad: si devuelve string directo
        return resultado;

    } catch (error) {
        console.error('Error consultando DNI:', error.message);

        if (error.code === 'ECONNREFUSED') {
            return `*Error:* Servidor Python no disponible

El servidor de scrapers no está corriendo.
Ejecuta: python python_server.py`;
        }

        return `*Error consultando DNI:* ${error.message}`;
    }
};
