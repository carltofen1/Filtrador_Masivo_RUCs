/**
 * Comando .dni NUMERO
 * Consulta datos de RENIEC usando API Decolecta
 */

const axios = require('axios');

const PYTHON_SERVER = 'http://localhost:5555';

module.exports = async function dniCommand(args) {
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
            timeout: 15000,
            headers: { 'Content-Type': 'application/json' }
        });

        return response.data.resultado;

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
