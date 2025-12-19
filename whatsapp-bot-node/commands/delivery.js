/**
 * Comando .delivery lat, lng
 * Consulta cobertura de delivery en portal Factibilidad Claro
 */

const puppeteer = require('puppeteer');
const config = require('../config');

// Helper para esperar
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Parsear coordenadas
function parsearCoordenadas(args) {
    const cleanArgs = args.replace(/[📍LatLng:]/g, '').replace(/[^\d\-.,\s]/g, '');
    const match = cleanArgs.match(/(-?\d+\.?\d*)\s*[,\s]\s*(-?\d+\.?\d*)/);

    if (match) {
        return {
            lat: parseFloat(match[1]),
            lng: parseFloat(match[2])
        };
    }
    return null;
}

module.exports = async function deliveryCommand(args) {
    const coords = parsearCoordenadas(args);

    if (!coords) {
        return `*Formato incorrecto*

Uso: .delivery lat, lng
Ejemplo: .delivery -12.046, -77.042`;
    }

    let browser = null;
    try {
        browser = await puppeteer.launch({
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--ignore-certificate-errors'
            ]
        });

        const page = await browser.newPage();

        // Login
        await page.goto(`${config.FACTIBILIDAD_URL}login`, {
            waitUntil: 'networkidle2',
            timeout: 30000
        });

        await page.type('input[type="text"]', config.FACTIBILIDAD_USERNAME);
        await page.type('#inputPass', config.FACTIBILIDAD_PASSWORD);
        await page.click('button[type="submit"]');

        await delay(3000);

        // Manejar modal de sesiones
        try {
            const btnContinuar = await page.$x("//button[contains(text(), 'Continuar')]");
            if (btnContinuar.length > 0) {
                await btnContinuar[0].click();
                await delay(2000);
            }
        } catch (e) { }

        // Ir a cobertura delivery
        await page.goto(`${config.FACTIBILIDAD_URL}cobertura-delivery`, {
            waitUntil: 'networkidle2',
            timeout: 30000
        });

        await delay(2000);

        // Click en lupa
        await page.click('#btn_search_dir');
        await delay(1500);

        // Click en tab Coordenadas
        await page.evaluate(() => {
            const tabs = document.querySelectorAll('.btn_searcher_tab button');
            tabs.forEach(tab => {
                if (tab.textContent.includes('Coordenadas')) tab.click();
            });
        });
        await delay(1000);

        // Ingresar coordenadas
        await page.type('#input_coordenadas', `${coords.lat}, ${coords.lng}`);
        await delay(500);

        // Buscar
        await page.click('#btn_search');
        await delay(3000);

        // Confirmar
        try {
            await page.click('#btn_confirmar');
            await delay(2000);
        } catch (e) {
            await browser.close();
            return `*Resultado de cobertura:*
Cobertura por Delivery: *NO*

Coordenadas:
Lat: ${coords.lat}
Lng: ${coords.lng}

_FACC_`;
        }

        // Extraer resultado
        const resultado = await page.evaluate(() => {
            const text = document.body.innerText.toUpperCase();
            const result = {
                distrito: '---',
                plano: '---',
                zona_toa: '---',
                color: '---',
                estado: 'SIN COBERTURA',
                condicion: '---'
            };

            // Distrito
            let m = text.match(/DISTRITO\s*:?\s*([A-ZÁÉÍÓÚÑ\s]+?)(?=PLANO|ZONA|COLOR|$)/);
            if (m) result.distrito = m[1].trim();

            // Plano
            m = text.match(/PLANO\s*:?\s*([A-Z0-9\-]+)/);
            if (m) result.plano = m[1].trim();

            // Zona TOA
            m = text.match(/ZONA[_\s]*TOA[\s\t:]*(\d+)/);
            if (m) result.zona_toa = m[1].trim();

            // Color
            ['AZUL', 'CELESTE', 'VERDE', 'AMARILLO', 'ROJO', 'NARANJA'].forEach(c => {
                if (text.includes(c)) result.color = c;
            });

            // Estado
            if (text.includes('CON COBERTURA')) {
                const em = text.match(/CON COBERTURA\s*\(([^)]+)\)/);
                result.estado = em ? `CON COBERTURA (${em[1].trim()})` : 'CON COBERTURA';
            }

            // Condición
            if (text.includes('LUNES A DOMINGO')) result.condicion = 'LUNES A DOMINGO';
            else if (text.includes('LUNES A VIERNES')) result.condicion = 'LUNES A VIERNES';

            return result;
        });

        await browser.close();

        const tieneCobertura = resultado.estado.includes('CON COBERTURA') ? 'SI' : 'NO';

        return `*Resultado de cobertura:*
Cobertura por Delivery: *${tieneCobertura}*

DISTRITO: ${resultado.distrito}
PLANO: ${resultado.plano}
ZONA_TOA: ${resultado.zona_toa}
COLOR: ${resultado.color}
ESTADO: ${resultado.estado}
CONDICION: ${resultado.condicion}

Coordenadas:
Lat: ${coords.lat}
Lng: ${coords.lng}

_FACC_`;

    } catch (error) {
        if (browser) await browser.close();
        console.error('Error delivery:', error.message);
        return `Error consultando delivery: ${error.message}`;
    }
};
