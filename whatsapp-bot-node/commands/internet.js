/**
 * Comando .internet lat, lng
 * Consulta cobertura de internet en portal Factibilidad Claro
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

module.exports = async function internetCommand(args) {
    const coords = parsearCoordenadas(args);

    if (!coords) {
        return `*Formato incorrecto*

Uso: .internet lat, lng
Ejemplo: .internet -12.046, -77.042`;
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

        // Ir a consulta internet
        await page.goto(`${config.FACTIBILIDAD_URL}buscar-casa-coordenada/31`, {
            waitUntil: 'networkidle2',
            timeout: 30000
        });

        await delay(2000);

        // Ingresar coordenadas
        await page.type('#input_lat_lon', `${coords.lat}, ${coords.lng}`);

        // Buscar
        const btnBuscar = await page.$x("//button[contains(text(), 'Buscar')]");
        if (btnBuscar.length > 0) {
            await btnBuscar[0].click();
        }
        await delay(3000);

        // Confirmar
        try {
            const btnConfirmar = await page.$x("//button[contains(text(), 'Confirmar')]");
            if (btnConfirmar.length > 0) {
                await btnConfirmar[0].click();
                await delay(2000);
            } else {
                await browser.close();
                return `*Resultado de cobertura:*
Cobertura de Internet: *NO*

- FTTH HORIZONTAL: NO
- HFC HORIZONTAL: NO
- VERTICAL: NO

Coordenadas:
Lat: ${coords.lat}
Lng: ${coords.lng}

_FACC_`;
            }
        } catch (e) {
            await browser.close();
            return `*Resultado de cobertura:*
Cobertura de Internet: *NO*

Coordenadas:
Lat: ${coords.lat}
Lng: ${coords.lng}

_FACC_`;
        }

        // Extraer resultado
        const resultado = await page.evaluate(() => {
            const text = document.body.innerText.toUpperCase();
            const result = {
                tiene_cobertura: false,
                plano: '---',
                tecnologia: '---',
                velocidad: '---',
                vendor: '---',
                estado: 'SIN COBERTURA'
            };

            if (text.includes('CON COBERTURA')) {
                result.tiene_cobertura = true;
                result.estado = 'CON COBERTURA';
            }

            // Plano
            let m = text.match(/PLANO[:\s]*([A-Z0-9\-]+)/);
            if (m) result.plano = m[1].trim();

            // Tecnología
            ['FTTH', 'HFC', 'IFI 5G', 'IFI LIMITADO', 'COBRE'].forEach(tech => {
                if (text.includes(tech)) result.tecnologia = tech;
            });

            // Velocidad
            m = text.match(/VELOCIDAD[^\d]*(\d+\s*MB)/);
            if (m) result.velocidad = m[1].trim();

            // Vendor
            ['HUAWEI', 'ZTE', 'NOKIA', 'CALIX'].forEach(v => {
                if (text.includes(v)) result.vendor = v;
            });

            return result;
        });

        await browser.close();

        const tieneCobertura = resultado.tiene_cobertura ? 'SI' : 'NO';

        return `*Resultado de cobertura:*
Cobertura de Internet: *${tieneCobertura}*

PLANO: ${resultado.plano}
TECNOLOGIA: ${resultado.tecnologia}
VELOCIDAD: ${resultado.velocidad}
VENDOR: ${resultado.vendor}
ESTADO: ${resultado.estado}

Coordenadas:
Lat: ${coords.lat}
Lng: ${coords.lng}

_FACC_`;

    } catch (error) {
        if (browser) await browser.close();
        console.error('Error internet:', error.message);
        return `Error consultando internet: ${error.message}`;
    }
};
