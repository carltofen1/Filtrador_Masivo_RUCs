/**
 * Comando .ruc NUMERO
 * Consulta datos de SUNAT y teléfono de ENTEL
 */

const puppeteer = require('puppeteer');
const config = require('../config');

// Helper para esperar
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Consultar SUNAT
async function consultarSunat(ruc) {
    let browser = null;
    try {
        browser = await puppeteer.launch({
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        });

        const page = await browser.newPage();
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

        await page.goto(config.SUNAT_URL, { waitUntil: 'networkidle2', timeout: 30000 });

        // Click en tab RUC
        try {
            await page.click('#btnPorRuc');
            await delay(500);
        } catch (e) { }

        // Ingresar RUC
        await page.type('#txtRuc', ruc);

        // Buscar
        await page.click('#btnAceptar');
        await page.waitForSelector('h4.list-group-item-heading', { timeout: 10000 });

        // Extraer datos
        const datos = await page.evaluate(() => {
            const resultado = {
                razon_social: '',
                estado: '',
                direccion: '',
                departamento: '',
                provincia: '',
                distrito: '',
                representante: '',
                documento: ''
            };

            // Razón Social
            const h4 = document.querySelector('h4.list-group-item-heading');
            if (h4) {
                const texto = h4.textContent.trim();
                if (texto.includes(' - ')) {
                    resultado.razon_social = texto.split(' - ').slice(1).join(' - ');
                }
            }

            // Estado y dirección
            const items = document.querySelectorAll('.list-group-item');
            items.forEach(item => {
                const text = item.textContent;
                if (text.includes('Estado del Contribuyente:')) {
                    const p = item.querySelector('p.list-group-item-text');
                    if (p) resultado.estado = p.textContent.trim().toUpperCase();
                }
                if (text.includes('Domicilio Fiscal:')) {
                    const p = item.querySelector('p.list-group-item-text');
                    if (p) {
                        const partes = p.textContent.trim().split(' - ');
                        if (partes.length >= 3) {
                            resultado.distrito = partes[partes.length - 1];
                            resultado.provincia = partes[partes.length - 2];
                            resultado.departamento = partes[partes.length - 3] || '';
                            resultado.direccion = partes.slice(0, -3).join(' - ');
                        }
                    }
                }
            });

            return resultado;
        });

        // Buscar representante legal
        try {
            await page.click('button.btnInfRepLeg');
            await delay(1000);

            const repLegal = await page.evaluate(() => {
                const tbody = document.querySelector('tbody');
                if (tbody) {
                    const fila = tbody.querySelector('tr');
                    if (fila) {
                        const celdas = fila.querySelectorAll('td');
                        if (celdas.length >= 3) {
                            return {
                                documento: `${celdas[0].textContent.trim()} ${celdas[1].textContent.trim()}`,
                                nombre: celdas[2].textContent.trim()
                            };
                        }
                    }
                }
                return null;
            });

            if (repLegal) {
                datos.representante = repLegal.nombre;
                datos.documento = repLegal.documento;
            }
        } catch (e) { }

        await browser.close();
        return datos;

    } catch (error) {
        if (browser) await browser.close();
        console.error('Error SUNAT:', error.message);
        return null;
    }
}

// Consultar ENTEL
async function consultarEntel(ruc) {
    let browser = null;
    try {
        browser = await puppeteer.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });

        const page = await browser.newPage();
        await page.goto(config.ENTEL_URL, { waitUntil: 'networkidle2', timeout: 30000 });

        // Login
        await page.type('#Email', config.ENTEL_USERNAME);
        await page.type('#Password', config.ENTEL_PASSWORD);
        await page.click('#btnLgn');

        await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 });

        // Ir a operaciones
        await page.goto('https://entel.insolutions.pe/entelid-portal/Operation', { waitUntil: 'networkidle2' });

        // Buscar RUC
        await page.type('#ruc', ruc);
        await page.click('#filter');

        // Esperar resultados
        await delay(3000);

        // Extraer teléfonos
        const telefonos = await page.evaluate(() => {
            const info = document.querySelector('#data-table_info');
            if (info && info.textContent.includes('0 to 0')) {
                return null;
            }

            const tbody = document.querySelector('#data-table tbody');
            if (!tbody) return null;

            const filas = tbody.querySelectorAll('tr');
            const tels = [];

            filas.forEach(fila => {
                const celdas = fila.querySelectorAll('td');
                if (celdas.length >= 5) {
                    const tel = celdas[4].textContent.trim().replace(/[\s-]/g, '');
                    if (tel && /^\d{8,}$/.test(tel) && !tels.includes(tel)) {
                        tels.push(tel);
                    }
                }
            });

            return tels.slice(-2).join(' / ');
        });

        await browser.close();
        return telefonos;

    } catch (error) {
        if (browser) await browser.close();
        console.error('Error ENTEL:', error.message);
        return null;
    }
}

module.exports = async function rucCommand(args) {
    // Extraer RUC
    const ruc = args.replace(/\D/g, '');

    if (!ruc || ruc.length !== 11) {
        return `*Formato incorrecto*

Uso: .ruc NUMERO_RUC
Ejemplo: .ruc 20123456789

_El RUC debe tener 11 dígitos_`;
    }

    console.log(`   → Consultando SUNAT para RUC ${ruc}...`);
    const datosSunat = await consultarSunat(ruc);

    console.log(`   → Consultando ENTEL para RUC ${ruc}...`);
    const telefono = await consultarEntel(ruc);

    // Formatear respuesta
    let respuesta = `*Consulta RUC: ${ruc}*\n\n`;

    if (datosSunat) {
        respuesta += `*DATOS SUNAT:*
Razón Social: ${datosSunat.razon_social || '---'}
Estado: ${datosSunat.estado || '---'}
Representante: ${datosSunat.representante || '---'}
DNI: ${datosSunat.documento || '---'}
Dirección: ${datosSunat.direccion || '---'}
Distrito: ${datosSunat.distrito || '---'}
Provincia: ${datosSunat.provincia || '---'}
Departamento: ${datosSunat.departamento || '---'}

`;
    } else {
        respuesta += `*DATOS SUNAT:* No disponible\n\n`;
    }

    respuesta += `*TELÉFONO ENTEL:* ${telefono || 'Sin registro'}`;

    return respuesta;
};
