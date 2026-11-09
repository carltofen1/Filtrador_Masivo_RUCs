"""Test rápido del scraper SUNAT - un solo RUC para verificar que funciona."""
from modules.sunat_scraper import SunatScraper, SunatBloqueadoError
import json

scraper = SunatScraper()  # ventana fuera de pantalla; headless lo bloquea Cloudflare

try:
    # RUC de prueba (SUNAT misma)
    resultado = scraper.consultar_ruc("20131312955")
    
    if resultado:
        print("\n✅ FUNCIONA! Datos extraídos:")
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    else:
        print("\n❌ No se pudo extraer datos. SUNAT puede estar caída o con CAPTCHA.")
except SunatBloqueadoError as e:
    print(f"\n🛑 {e}")
finally:
    scraper.close()
