/**
 * Bot de WhatsApp - Cobertura Claro
 * Usando whatsapp-web.js con servidor Python para scrapers
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const http = require('http');
const path = require('path');
const fs = require('fs');

// ==================== SISTEMA DE RECONEXIÓN AUTOMÁTICA ====================
let client = null;
let isReconnecting = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_DELAY_MS = 30000; // 30 segundos entre intentos
const HEALTH_CHECK_INTERVAL_MS = 5 * 60 * 1000; // Verificar cada 5 minutos
let healthCheckInterval = null;

console.log('==================================================');
console.log('   BOT DE WHATSAPP - COBERTURA CLARO (Node.js)');
console.log('==================================================');
console.log();

// Detectar si estamos corriendo como ejecutable empaquetado (pkg)
// En pkg, process.pkg existe y el snapshot está en process.execPath
const isPackaged = typeof process.pkg !== 'undefined';

// Base path: junto al ejecutable si está empaquetado, o cwd si es desarrollo
const BASE_PATH = isPackaged ? path.dirname(process.execPath) : process.cwd();
console.log('[CONFIG] Modo:', isPackaged ? 'Empaquetado (pkg)' : 'Desarrollo');
console.log('[CONFIG] Base path:', BASE_PATH);

// Función para encontrar Chrome en ubicaciones comunes de Windows
function findChromePath() {
    // Primero revisar variable de entorno
    if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) {
        console.log('[CHROME] Usando CHROME_PATH del entorno:', process.env.CHROME_PATH);
        return process.env.CHROME_PATH;
    }

    // Rutas comunes de Chrome en Windows
    const possiblePaths = [
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        path.join(process.env.LOCALAPPDATA || '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
        path.join(process.env.PROGRAMFILES || '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
        path.join(process.env['PROGRAMFILES(X86)'] || '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
    ];

    for (const chromePath of possiblePaths) {
        if (chromePath && fs.existsSync(chromePath)) {
            console.log('[CHROME] Encontrado en:', chromePath);
            return chromePath;
        }
    }

    console.log('[CHROME] ADVERTENCIA: No se encontró Chrome. Puppeteer intentará usar su propio Chromium.');
    return undefined; // Puppeteer intentará descargar/usar Chromium
}

const CHROME_PATH = findChromePath();

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

// Ruta de datos de sesión
const AUTH_PATH = path.join(BASE_PATH, '.wwebjs_auth');
console.log('[CONFIG] Sesión en:', AUTH_PATH);

// ==================== FUNCIÓN PARA LIMPIAR BLOQUEOS ====================
/**
 * Elimina archivos de bloqueo de Puppeteer que pueden quedar huérfanos tras un cierre inesperado
 */
function cleanupLocks() {
    console.log('[CLEANUP] Verificando archivos de bloqueo de sesión...');
    try {
        const sessionPath = path.join(AUTH_PATH, 'session-bot-client');
        if (fs.existsSync(sessionPath)) {
            // Lista de archivos de bloqueo comunes en Chrome/Puppeteer
            const lockFiles = [
                path.join(sessionPath, 'SingletonLock'),
                path.join(sessionPath, 'DevToolsActivePort'),
                path.join(sessionPath, 'Default', 'LOCK')
            ];

            lockFiles.forEach(file => {
                if (fs.existsSync(file)) {
                    try {
                        console.log(`[CLEANUP] Eliminando bloqueo: ${path.basename(file)}`);
                        fs.unlinkSync(file);
                    } catch (e) {
                        console.log(`[CLEANUP] No se pudo eliminar ${path.basename(file)} (puede estar en uso): ${e.message}`);
                    }
                }
            });
        }
    } catch (e) {
        console.log(`[CLEANUP] Error durante la limpieza: ${e.message}`);
    }
}

// ==================== FUNCIÓN PARA CREAR CLIENTE ====================
function createClient() {
    console.log('[INIT] Creando nuevo cliente de WhatsApp...');

    const newClient = new Client({
        authStrategy: new LocalAuth({
            dataPath: AUTH_PATH,
            clientId: 'bot-client'
        }),
        puppeteer: {
            headless: true,
            executablePath: CHROME_PATH,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920,1080',
                '--disable-client-updates'
            ]
        }
    });

    // Evento: QR Code
    newClient.on('qr', (qr) => {
        console.log('Escanea el codigo QR con tu WhatsApp:');
        console.log();
        qrcode.generate(qr, { small: true });
    });

    // Evento: Autenticado
    newClient.on('authenticated', () => {
        console.log('[OK] Autenticado correctamente');
        reconnectAttempts = 0; // Reset intentos al autenticar
    });

    // Evento: Cargando pantalla
    newClient.on('loading_screen', (percent, message) => {
        console.log('[LOADING]', percent + '%', message);
    });

    // Evento: Fallo de autenticación
    newClient.on('auth_failure', (msg) => {
        console.log('[ERROR] Fallo de autenticación:', msg);
    });

    // Evento: Cambio de estado
    newClient.on('change_state', (state) => {
        console.log('[STATE]', state);
    });

    // Capturar logs del navegador
    newClient.on('authenticated', async () => {
        try {
            const page = newClient.pupPage;
            if (page) {
                page.on('console', msg => console.log('[BROWSER]', msg.text()));
                page.on('pageerror', err => console.log('[BROWSER ERROR]', err.toString()));
            }
        } catch (e) {
            console.log('[DEBUG] Error inyectando hooks:', e.message);
        }
    });

    // Debug: Sesión remota
    newClient.on('remote_session_saved', () => {
        console.log('[DEBUG] Sesión remota guardada');
    });

    // Debug: Mensaje RAW
    newClient.on('message_create', (msg) => {
        console.log('[RAW MSG]', msg.from, '->', msg.body.substring(0, 30));
    });

    // Evento: Listo - Iniciar healthcheck
    newClient.on('ready', () => {
        console.log();
        console.log('[OK] Bot listo y escuchando mensajes');
        console.log('[OK] Hora:', new Date().toLocaleString());
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

        // Iniciar healthcheck periódico
        startHealthCheck();
    });

    // Evento: Mensaje propio
    newClient.on('message_create', async (message) => {
        if (message.fromMe) {
            console.log('[DEBUG] Mensaje propio:', message.body.substring(0, 30));
        }
    });

    // ==================== EVENTOS DE DESCONEXIÓN Y ERROR ====================

    // Evento: Desconectado
    newClient.on('disconnected', async (reason) => {
        console.log('[DISCONNECT]', new Date().toLocaleString(), 'Razón:', reason);
        stopHealthCheck();
        await attemptReconnect('disconnected: ' + reason);
    });

    return newClient;
}

// ==================== SISTEMA DE HEALTHCHECK ====================
function startHealthCheck() {
    stopHealthCheck(); // Limpiar cualquier intervalo anterior

    console.log('[HEALTH] Iniciando verificación cada 5 minutos...');

    healthCheckInterval = setInterval(async () => {
        try {
            if (!client) {
                console.log('[HEALTH] Cliente no existe, reconectando...');
                await attemptReconnect('client null');
                return;
            }

            // Verificar si Puppeteer sigue vivo
            const state = await client.getState().catch(() => null);

            if (state === null) {
                console.log('[HEALTH] Estado nulo, posible desconexión...');
                await attemptReconnect('state null');
                return;
            }

            if (state !== 'CONNECTED') {
                console.log('[HEALTH] Estado:', state, '- Reconectando...');
                await attemptReconnect('state: ' + state);
                return;
            }

            console.log('[HEALTH]', new Date().toLocaleString(), '- OK (CONNECTED)');

        } catch (error) {
            console.log('[HEALTH] Error:', error.message);

            // Si el error es sobre contexto destruido, reconectar
            if (error.message.includes('context was destroyed') ||
                error.message.includes('Session closed') ||
                error.message.includes('Target closed') ||
                error.message.includes('Protocol error')) {
                await attemptReconnect('healthcheck error: ' + error.message);
            }
        }
    }, HEALTH_CHECK_INTERVAL_MS);
}

function stopHealthCheck() {
    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
        healthCheckInterval = null;
    }
}

// ==================== SISTEMA DE RECONEXIÓN ====================
async function attemptReconnect(reason) {
    if (isReconnecting) {
        console.log('[RECONNECT] Ya hay una reconexión en progreso...');
        return;
    }

    isReconnecting = true;
    reconnectAttempts++;

    console.log('[RECONNECT] Intento', reconnectAttempts, '/', MAX_RECONNECT_ATTEMPTS);
    console.log('[RECONNECT] Razón:', reason);

    if (reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
        console.log('[FATAL] Máximo de intentos alcanzado. Reinicia el bot manualmente.');
        console.log('[FATAL] Hora:', new Date().toLocaleString());
        process.exit(1);
    }

    try {
        // Detener healthcheck
        stopHealthCheck();

        // Intentar destruir cliente anterior
        if (client) {
            try {
                console.log('[RECONNECT] Destruyendo cliente anterior...');
                await client.destroy().catch(() => { });
            } catch (e) {
                console.log('[RECONNECT] Error destruyendo cliente:', e.message);
            }
        }

        // Esperar antes de reconectar
        console.log('[RECONNECT] Esperando', RECONNECT_DELAY_MS / 1000, 'segundos...');
        await new Promise(r => setTimeout(r, RECONNECT_DELAY_MS));

        // Crear nuevo cliente
        client = createClient();

        // Configurar manejador de mensajes
        setupMessageHandler();

        // Limpiar bloqueos antes de inicializar
        cleanupLocks();

        // Inicializar
        console.log('[RECONNECT] Inicializando nuevo cliente...');
        await client.initialize();

        console.log('[RECONNECT] Reconexión exitosa!');
        isReconnecting = false;

    } catch (error) {
        console.log('[RECONNECT] Error:', error.message);
        isReconnecting = false;

        // Reintentar después de un delay
        setTimeout(() => attemptReconnect('retry after error'), RECONNECT_DELAY_MS);
    }
}

// ==================== MANEJO GLOBAL DE ERRORES ====================
process.on('uncaughtException', async (error) => {
    console.log('[UNCAUGHT]', new Date().toLocaleString());
    console.log('[UNCAUGHT] Error:', error.message);

    // Si es error de contexto destruido, reconectar
    if (error.message.includes('context was destroyed') ||
        error.message.includes('Session closed') ||
        error.message.includes('Target closed') ||
        error.message.includes('navigation')) {
        console.log('[UNCAUGHT] Intentando reconexión automática...');
        await attemptReconnect('uncaughtException: ' + error.message);
    } else {
        console.log('[UNCAUGHT] Stack:', error.stack);
    }
});

process.on('unhandledRejection', async (reason, promise) => {
    console.log('[UNHANDLED]', new Date().toLocaleString());
    console.log('[UNHANDLED] Razón:', reason);

    const reasonStr = String(reason);
    if (reasonStr.includes('context was destroyed') ||
        reasonStr.includes('Session closed') ||
        reasonStr.includes('Target closed') ||
        reasonStr.includes('navigation')) {
        console.log('[UNHANDLED] Intentando reconexión automática...');
        await attemptReconnect('unhandledRejection');
    }
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

// ==================== MANEJADOR DE MENSAJES ====================
function setupMessageHandler() {
    if (!client) {
        console.log('[ERROR] No hay cliente para configurar manejador de mensajes');
        return;
    }

    client.on('message', async (message) => {
        try {
            console.log('[DEBUG] Mensaje entrante de:', message.from);
            console.log('[DEBUG] Contenido:', message.body);
            console.log('[DEBUG] Es de grupo?:', message.isGroupMsg);

            const texto = message.body.trim();

            // Solo procesar mensajes que empiecen con .
            if (!texto.startsWith('.')) {
                console.log('[DEBUG] Ignorado (no empieza con .)');
                return;
            }

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

        } catch (error) {
            console.log('[MSG ERROR]', error.message);

            // Si es error de contexto destruido, ignorar y dejar que el healthcheck reconecte
            if (error.message.includes('context was destroyed') ||
                error.message.includes('Session closed')) {
                console.log('[MSG ERROR] Contexto destruido, esperando reconexión...');
            }
        }
    });
}

// ==================== INICIO DEL BOT ====================
async function startBot() {
    console.log('Iniciando cliente de WhatsApp...');
    console.log('IMPORTANTE: Asegúrate de que el servidor Python esté corriendo');
    console.log('   En otra terminal: python python_server.py');
    console.log();
    console.log('[HORA INICIO]', new Date().toLocaleString());
    console.log();

    try {
        // Crear cliente
        client = createClient();

        // Configurar manejador de mensajes
        setupMessageHandler();

        // Limpiar bloqueos antes de inicializar
        cleanupLocks();

        // Inicializar
        await client.initialize();

    } catch (error) {
        console.log('[FATAL] Error iniciando bot:', error.message);
        
        if (error.message.includes('browser is already running') || error.message.includes('userDataDir')) {
            console.log();
            console.log('--------------------------------------------------');
            console.log('⚠️  ¡ATENCIÓN: EL NAVEGADOR PARECE ESTAR BLOQUEADO!');
            console.log('1. Abre el Administrador de Tareas (Ctrl+Shift+Esc)');
            console.log('2. Busca y cierra todos los procesos "Google Chrome" o "chrome.exe"');
            console.log('3. Asegúrate de que no haya otra terminal con el bot abierto');
            console.log('4. El bot reintentará en 30 segundos...');
            console.log('--------------------------------------------------');
            console.log();
        } else {
            console.log('[FATAL] Reintentando en 30 segundos...');
        }
        
        setTimeout(startBot, 30000);
    }
}

// Iniciar el bot
startBot();
