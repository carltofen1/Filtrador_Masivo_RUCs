/**
 * Bot de WhatsApp - Cobertura Claro
 * Usando whatsapp-web.js con servidor Python para scrapers
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const http = require('http');
const path = require('path');

console.log('='.repeat(50));
console.log('   BOT DE WHATSAPP - COBERTURA CLARO (Node.js)');
console.log('='.repeat(50));
console.log();

// Cola de comandos
const commandQueue = [];
let isProcessing = false;

// Comandos disponibles
const COMANDOS = {
    '.!': 'help',
    '.help': 'help',
    '.ayuda': 'help',
    '.delivery': 'delivery',
    '.internet': 'internet',
    '.ruc': 'ruc',
    '.dni': 'dni'
};

// Crear cliente de WhatsApp con sesión persistente
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, '.wwebjs_auth')
    }),
    puppeteer: {
        headless: true,
        executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--disable-gpu',
            '--window-size=1920,1080'
        ]
    }
});

// Evento: QR Code
client.on('qr', (qr) => {
    console.log('Escanea el codigo QR con tu WhatsApp:');
    console.log();
    qrcode.generate(qr, { small: true });
});

// Evento: Autenticando
client.on('authenticated', () => {
    console.log('✅ Autenticado correctamente!');
});

// Evento: Listo
client.on('ready', () => {
    console.log();
    console.log('✅ Bot listo y escuchando mensajes!');
    console.log();
    console.log('-'.repeat(50));
    console.log('COMANDOS:');
    console.log('   .!                  - Ayuda');
    console.log('   .delivery lat, lng  - Cobertura delivery');
    console.log('   .internet lat, lng  - Cobertura internet');
    console.log('   .ruc NUMERO         - Datos SUNAT + telefono ENTEL');
    console.log('   .dni NUMERO         - Datos RENIEC por DNI');
    console.log('-'.repeat(50));
    console.log();
    console.log('(Ctrl+C para detener)');
    console.log();
});

// Procesar cola de comandos
async function processQueue() {
    if (isProcessing || commandQueue.length === 0) return;

    isProcessing = true;

    while (commandQueue.length > 0) {
        const { message, comando, args } = commandQueue.shift();

        try {
            let respuesta = null;

            switch (comando) {
                case 'help':
                    respuesta = getHelpMessage();
                    break;
                case 'ruc':
                    await message.reply('⏳ Consultando RUC...\nEspera un momento...');
                    respuesta = await llamarPythonServer('ruc', args);
                    break;
                case 'delivery':
                    await message.reply('⏳ Consultando cobertura de delivery...');
                    respuesta = await llamarPythonServer('delivery', args);
                    break;
                case 'internet':
                    await message.reply('⏳ Consultando cobertura de internet...');
                    respuesta = await llamarPythonServer('internet', args);
                    break;
                case 'dni':
                    await message.reply('⏳ Consultando DNI en RENIEC...');
                    respuesta = await llamarPythonServer('dni', args);
                    break;
            }

            if (respuesta) {
                await message.reply(respuesta);
                console.log('✅ Respuesta enviada');
            }

        } catch (error) {
            console.error(`❌ Error: ${error.message}`);
            await message.reply(`❌ Error: ${error.message}`);
        }
    }

    isProcessing = false;
}

// Llamar al servidor Python
function llamarPythonServer(comando, args) {
    return new Promise((resolve, reject) => {
        const data = JSON.stringify({ comando, args });

        const options = {
            hostname: 'localhost',
            port: 5555,
            path: '/',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(data)
            }
        };

        const req = http.request(options, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => {
                try {
                    const json = JSON.parse(body);
                    resolve(json.resultado);
                } catch (e) {
                    reject(new Error('Respuesta inválida del servidor'));
                }
            });
        });

        req.on('error', (e) => {
            reject(new Error('Servidor Python no disponible. Ejecuta: python python_server.py'));
        });

        req.setTimeout(90000, () => {
            req.destroy();
            reject(new Error('Timeout - consulta tardó demasiado'));
        });

        req.write(data);
        req.end();
    });
}

// Mensaje de ayuda
function getHelpMessage() {
    return `Bot de Cobertura Claro

Comandos:

.! - Mostrar esta ayuda

.delivery lat, lng
Ejemplo: .delivery -12.046, -77.042

.internet lat, lng
Ejemplo: .internet -12.046, -77.042

.ruc NUMERO_RUC
Ejemplo: .ruc 20123456789

.dni NUMERO_DNI
Ejemplo: .dni 12345678

Coord. de Google Maps`;
}

// Evento: Mensaje recibido
client.on('message', async (message) => {
    const texto = message.body.trim();

    // Solo procesar mensajes que empiecen con .
    if (!texto.startsWith('.')) return;

    console.log(`📩 COMANDO: ${texto}`);

    // Buscar comando
    let comando = null;
    let args = '';

    const textoLower = texto.toLowerCase();

    for (const [cmdKey, cmdValue] of Object.entries(COMANDOS)) {
        if (textoLower.startsWith(cmdKey)) {
            comando = cmdValue;
            args = texto.slice(cmdKey.length).trim().replace(/[{}\[\]]/g, '');
            break;
        }
    }

    if (!comando) return;

    // Agregar a la cola
    commandQueue.push({ message, comando, args });
    console.log(`   📋 Cola: ${commandQueue.length} pendientes`);

    // Procesar cola
    processQueue();
});

// Evento: Desconectado
client.on('disconnected', async (reason) => {
    console.log('❌ Cliente desconectado:', reason);

    // Si fue logout, limpiar sesión para evitar errores de lockfile
    if (reason === 'LOGOUT') {
        console.log('🧹 Limpiando sesión anterior...');
        const fs = require('fs');
        const authPath = path.join(__dirname, '.wwebjs_auth');

        try {
            if (fs.existsSync(authPath)) {
                fs.rmSync(authPath, { recursive: true, force: true });
                console.log('✅ Sesión limpiada. Reinicia el bot para escanear QR nuevamente.');
            }
        } catch (e) {
            console.log('⚠️ No se pudo limpiar sesión automáticamente.');
            console.log('   Ejecuta manualmente: rmdir /s /q .wwebjs_auth');
        }
    }
});

// Iniciar cliente
console.log('Iniciando cliente de WhatsApp...');
console.log('IMPORTANTE: Asegúrate de que el servidor Python esté corriendo!');
console.log('   En otra terminal: cd whatsapp-bot-node && python python_server.py');
console.log();
client.initialize();
