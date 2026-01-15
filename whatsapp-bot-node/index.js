/**
 * Bot de WhatsApp - Cobertura Claro
 * Usando whatsapp-web.js con servidor Python para scrapers
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const http = require('http');
const path = require('path');

console.log('==================================================');
console.log('   BOT DE WHATSAPP - COBERTURA CLARO (Node.js)');
console.log('==================================================');
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

// Crear cliente de WhatsApp
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(process.cwd(), '.wwebjs_auth')
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
            '--window-size=1920,1080',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
        ]
    }
});

// Evento: QR Code
client.on('qr', (qr) => {
    console.log('Escanea el codigo QR con tu WhatsApp:');
    console.log();
    qrcode.generate(qr, { small: true });
});

// Evento: Autenticado
client.on('authenticated', () => {
    console.log('[OK] Autenticado correctamente');
});

// Evento: Listo
client.on('ready', () => {
    console.log();
    console.log('[OK] Bot listo y escuchando mensajes');
    console.log();
    console.log('--------------------------------------------------');
    console.log('COMANDOS:');
    console.log('   .!                  - Ayuda');
    console.log('   .delivery lat, lng  - Cobertura delivery');
    console.log('   .internet lat, lng  - Cobertura internet');
    console.log('   .ruc NUMERO         - Datos SUNAT + telefono ENTEL');
    console.log('   .dni NUMERO         - Datos RENIEC por DNI');
    console.log('--------------------------------------------------');
    console.log();
    console.log('(Ctrl+C para detener)');
    console.log();
});

// Funcion para enviar mensaje con reintentos
async function safeReply(message, text) {
    const MAX_REINTENTOS = 3;
    const chatId = message.from || message.id?.remote;

    console.log('[SEND] Destino:', chatId);
    console.log('[SEND] Texto:', text.substring(0, 50) + '...');

    for (let intento = 1; intento <= MAX_REINTENTOS; intento++) {
        // Intentar con reply()
        try {
            console.log('[INTENTO ' + intento + '/' + MAX_REINTENTOS + '] Usando reply()...');
            await message.reply(text);
            console.log('[OK] reply() exitoso');
            return true;
        } catch (replyError) {
            console.log('[FAIL] reply() error:', replyError.message);

            // Intentar con sendMessage()
            try {
                if (!chatId) {
                    console.log('[ERROR] No hay chatId disponible');
                    continue;
                }
                console.log('[INTENTO ' + intento + '/' + MAX_REINTENTOS + '] Usando sendMessage()...');
                await client.sendMessage(chatId, text);
                console.log('[OK] sendMessage() exitoso');
                return true;
            } catch (sendError) {
                console.log('[FAIL] sendMessage() error:', sendError.message);

                if (intento < MAX_REINTENTOS) {
                    console.log('[WAIT] Esperando 2 segundos antes de reintentar...');
                    await new Promise(r => setTimeout(r, 2000));
                }
            }
        }
    }

    console.log('[FATAL] No se pudo enviar el mensaje despues de ' + MAX_REINTENTOS + ' intentos');
    return false;
}

// Procesar cola de comandos
async function processQueue() {
    if (isProcessing || commandQueue.length === 0) return;

    isProcessing = true;

    try {
        while (commandQueue.length > 0) {
            const { message, comando, args } = commandQueue.shift();

            try {
                let respuesta = null;

                switch (comando) {
                    case 'help':
                        respuesta = getHelpMessage();
                        break;
                    case 'ruc':
                        await safeReply(message, 'Consultando RUC...\nEspera un momento...');
                        respuesta = await llamarPythonServer('ruc', args);
                        break;
                    case 'delivery':
                        await safeReply(message, 'Consultando cobertura de delivery...');
                        respuesta = await llamarPythonServer('delivery', args);
                        break;
                    case 'internet':
                        await safeReply(message, 'Consultando cobertura de internet...');
                        respuesta = await llamarPythonServer('internet', args);
                        break;
                    case 'dni':
                        await safeReply(message, 'Consultando DNI en RENIEC...');
                        respuesta = await llamarPythonServer('dni', args);
                        break;
                }

                if (respuesta) {
                    const enviado = await safeReply(message, respuesta);
                    if (enviado) {
                        console.log('[OK] Respuesta enviada');
                    } else {
                        console.log('[FAIL] No se pudo enviar la respuesta');
                    }
                }

            } catch (error) {
                console.error('[ERROR] Procesando comando:', error.message);
                try {
                    await safeReply(message, 'Error: ' + error.message);
                } catch (e) {
                    console.error('[ERROR] No se pudo enviar mensaje de error');
                }
            }
        }
    } finally {
        isProcessing = false;
    }
}

// Llamar al servidor Python
function llamarPythonServer(comando, args) {
    return new Promise((resolve, reject) => {
        const data = JSON.stringify({ comando, args });

        const options = {
            hostname: '127.0.0.1',
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
                    reject(new Error('Respuesta invalida del servidor'));
                }
            });
        });

        req.on('error', (e) => {
            reject(new Error('Servidor Python no disponible. Ejecuta: python python_server.py'));
        });

        req.setTimeout(90000, () => {
            req.destroy();
            reject(new Error('Timeout - consulta tardo demasiado'));
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

    console.log('[CMD] Recibido:', texto);

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
    console.log('[QUEUE] Pendientes:', commandQueue.length);

    // Procesar cola
    processQueue();
});

// Evento: Desconectado
client.on('disconnected', async (reason) => {
    console.log('[DISCONNECT] Razon:', reason);
});

// Iniciar cliente
console.log('Iniciando cliente de WhatsApp...');
console.log('IMPORTANTE: Asegurate de que el servidor Python este corriendo');
console.log('   En otra terminal: python python_server.py');
console.log();
client.initialize();
