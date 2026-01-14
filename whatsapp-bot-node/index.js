/**
 * Bot de WhatsApp - Cobertura Claro
 * Usando whatsapp-web.js con servidor Python para scrapers
 * Con auto-actualización cuando detecta incompatibilidades
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const http = require('http');
const path = require('path');
const { execSync, spawn } = require('child_process');

// Errores que indican incompatibilidad con WhatsApp Web
const ERRORES_INCOMPATIBILIDAD = [
    'markedUnread',
    'sendSeen',
    'Cannot read properties of undefined',
    'is not a function',
    'WWebJS'
];

let actualizando = false;
let erroresConsecutivos = 0;
const MAX_ERRORES_ANTES_REINICIO = 3;

// Función para detectar si es error de incompatibilidad
function esErrorIncompatibilidad(error) {
    const mensaje = error.message || error.toString();
    // Excluir errores de sesión cerrada (son temporales durante reinicio)
    if (mensaje.includes('Session closed') || mensaje.includes('page has been closed')) {
        return false;
    }
    return ERRORES_INCOMPATIBILIDAD.some(patron => mensaje.includes(patron));
}

// Función para auto-actualizar y reiniciar
async function autoActualizarYReiniciar() {
    if (actualizando) return;
    actualizando = true;

    console.log();
    console.log('='.repeat(50));
    console.log('⚠️  DETECTADA INCOMPATIBILIDAD CON WHATSAPP WEB');
    console.log('='.repeat(50));
    console.log();
    console.log('🔄 Actualizando whatsapp-web.js automáticamente...');

    try {
        // Cerrar el cliente de WhatsApp
        try {
            await client.destroy();
        } catch (e) {
            // Ignorar errores al cerrar
        }

        const fs = require('fs');

        // Limpiar caché de WhatsApp Web
        console.log('🧹 Limpiando caché de WhatsApp Web...');
        const cachePaths = [
            path.join(__dirname, '.wwebjs_cache'),
            path.join(__dirname, '.wwebjs_auth')
        ];

        for (const cachePath of cachePaths) {
            try {
                if (fs.existsSync(cachePath)) {
                    fs.rmSync(cachePath, { recursive: true, force: true });
                    console.log(`   ✓ Eliminado: ${path.basename(cachePath)}`);
                }
            } catch (e) {
                console.log(`   ⚠️ No se pudo eliminar: ${path.basename(cachePath)}`);
            }
        }

        // Limpiar caché de npm
        console.log('🧹 Limpiando caché de npm...');
        try {
            execSync('npm cache clean --force', { cwd: __dirname, stdio: 'pipe' });
        } catch (e) {
            // Ignorar errores de limpieza de npm cache
        }

        // Ejecutar npm update
        console.log('📦 Ejecutando: npm update whatsapp-web.js');
        execSync('npm update whatsapp-web.js', {
            cwd: __dirname,
            stdio: 'inherit'
        });

        console.log('✅ Actualización completada');
        console.log('🔄 Reiniciando bot en 3 segundos...');
        console.log('📱 Necesitarás escanear el QR nuevamente');
        console.log();

        // Esperar 3 segundos y reiniciar
        setTimeout(() => {
            // Reiniciar el proceso de Node.js
            const args = process.argv.slice(1);
            const child = spawn(process.argv[0], args, {
                cwd: __dirname,
                detached: true,
                stdio: 'inherit'
            });
            child.unref();
            process.exit(0);
        }, 3000);

    } catch (updateError) {
        console.error('❌ Error al actualizar:', updateError.message);
        console.log('💡 Intenta manualmente: npm update whatsapp-web.js');
        process.exit(1);
    }
}

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

// Función segura para responder mensajes (evita crash por sendSeen)
async function safeReply(message, text) {
    try {
        await message.reply(text);
        erroresConsecutivos = 0; // Reset en éxito
        return true;
    } catch (replyError) {
        console.log('⚠️ Error en reply, usando sendMessage como fallback...');

        try {
            // Usar chatId directamente del mensaje, sin llamar getChat()
            const chatId = message.from || message.id?.remote;
            if (!chatId) {
                throw new Error('No se pudo determinar el chat destino');
            }
            await client.sendMessage(chatId, text);
            console.log('✅ Fallback exitoso con sendMessage');
            erroresConsecutivos = 0; // Reset en éxito
            return true;
        } catch (fallbackError) {
            console.error('❌ Error en fallback sendMessage:', fallbackError.message);

            // Solo contar como error de incompatibilidad si realmente lo es
            if (esErrorIncompatibilidad(replyError) || esErrorIncompatibilidad(fallbackError)) {
                erroresConsecutivos++;
                console.log(`⚠️ Errores de incompatibilidad consecutivos: ${erroresConsecutivos}/${MAX_ERRORES_ANTES_REINICIO}`);

                if (erroresConsecutivos >= MAX_ERRORES_ANTES_REINICIO) {
                    console.log('🔄 Demasiados errores consecutivos, iniciando auto-actualización...');
                    await autoActualizarYReiniciar();
                }
            }
            return false;
        }
    }
}

// Procesar cola de comandos
async function processQueue() {
    if (actualizando) {
        console.log('⏸️ Cola pausada - bot actualizándose...');
        return;
    }
    if (isProcessing || commandQueue.length === 0) return;

    isProcessing = true;

    try {
        while (commandQueue.length > 0 && !actualizando) {
            const { message, comando, args } = commandQueue.shift();

            try {
                let respuesta = null;

                switch (comando) {
                    case 'help':
                        respuesta = getHelpMessage();
                        break;
                    case 'ruc':
                        await safeReply(message, '⏳ Consultando RUC...\nEspera un momento...');
                        respuesta = await llamarPythonServer('ruc', args);
                        break;
                    case 'delivery':
                        await safeReply(message, '⏳ Consultando cobertura de delivery...');
                        respuesta = await llamarPythonServer('delivery', args);
                        break;
                    case 'internet':
                        await safeReply(message, '⏳ Consultando cobertura de internet...');
                        respuesta = await llamarPythonServer('internet', args);
                        break;
                    case 'dni':
                        await safeReply(message, '⏳ Consultando DNI en RENIEC...');
                        respuesta = await llamarPythonServer('dni', args);
                        break;
                }

                if (respuesta) {
                    await safeReply(message, respuesta);
                    console.log('✅ Respuesta enviada');
                }

            } catch (error) {
                console.error(`❌ Error procesando comando: ${error.message}`);
                try {
                    await safeReply(message, `❌ Error: ${error.message}`);
                } catch (e) {
                    console.error('❌ No se pudo enviar mensaje de error');
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
