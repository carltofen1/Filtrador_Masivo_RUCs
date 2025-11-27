# 🚀 Filtrador Masivo de RUCs - Claro

Sistema automatizado para extraer y consolidar información de empresas peruanas usando RUC, combinando datos de SUNAT y la plataforma interna de Claro.

## 📋 Características

- ✅ **Consulta automática a SUNAT** (Razón Social, Dirección, Representante Legal, DNI)
- ✅ **Scraping de plataforma Claro** (Teléfonos, Operador, Cantidad de Líneas)
- ✅ **Integración con Google Sheets** en tiempo real
- ✅ **Batch updates optimizado** (mínimo uso de API calls)
- ✅ **Procesamiento masivo** con manejo de errores robusto
- ✅ **Progreso en vivo** visible en Google Sheets

## 📊 Datos Extraídos

| Campo | Fuente |
|-------|--------|
| ID REGISTRO | Auto-generado |
| RUC | Input |
| Razón Social | SUNAT |
| Representante Legal | SUNAT |
| Teléfonos | Claro |
| Documento Identidad | SUNAT |
| DEPARTAMENTO | SUNAT |
| PROVINCIA | SUNAT |
| DISTRITO | SUNAT |
| DIRECCION | SUNAT |

## 🛠️ Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/Filtrador_Masivo_RUCs.git
cd Filtrador_Masivo_RUCs
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar credenciales

#### Google Sheets API
- El archivo `credentials.json` ya está incluido
- Asegúrate de que la cuenta de servicio tenga acceso a tu Google Sheet

#### Variables de entorno
Crea un archivo `.env` basado en `.env.example`:

```env
# Google Sheets Configuration
SPREADSHEET_ID=tu_spreadsheet_id_aqui
SHEET_NAME=Datos_Filtrados

# Claro Platform Credentials
CLARO_USERNAME=tu_usuario_claro
CLARO_PASSWORD=tu_password_claro
CLARO_URL=url_de_la_plataforma_claro

# Processing Configuration
BATCH_SIZE=100
DELAY_BETWEEN_BATCHES=1
```

## 📝 Configuración de Google Sheets

1. Crea una pestaña llamada **"Datos_Filtrados"** en tu Google Sheet
2. Comparte el sheet con el email de la cuenta de servicio:
   ```
   ventascenter@ventascenter.iam.gserviceaccount.com
   ```
3. Dale permisos de **Editor**
4. Copia el ID del spreadsheet de la URL:
   ```
   https://docs.google.com/spreadsheets/d/[ESTE_ES_EL_ID]/edit
   ```
5. Pégalo en el archivo `.env`

## 🎯 Uso

### Preparar datos
1. En la pestaña **"Datos_Filtrados"**, coloca los RUCs en la columna B (empezando en B2)
2. La columna K (ESTADO) debe estar **vacía** o con el valor **"Pendiente"** para que se procesen
3. Los RUCs con ESTADO = "Activo", "Baja", "Desconocido", "Completado" serán **omitidos**
4. Los headers se crearán automáticamente si no existen

### Probar el sistema
```bash
python test_completo.py
```

Este script verificará:
- ✅ Conexión a Google Sheets
- ✅ Lectura de RUCs pendientes
- ✅ Funcionamiento del scraper de SUNAT

### Ejecutar el procesamiento completo
```bash
python main.py
```

### Monitorear progreso
- El script mostrará el progreso en la consola
- Los datos se actualizarán en Google Sheets en tiempo real
- Cada batch de 100 registros se guarda automáticamente
- La columna ESTADO mostrará:
  - **"Procesando"** → Mientras se consulta
  - **"Completado"** → Datos extraídos exitosamente
  - **"Error - SUNAT"** → No se pudo obtener datos de SUNAT
  - **"Error: ..."** → Otro tipo de error

## ⚙️ Configuración de Claro Scraper

**IMPORTANTE**: El módulo `claro_scraper.py` necesita ser configurado según la estructura de tu plataforma interna.

### Pasos para configurar:

1. Abre `modules/claro_scraper.py`
2. En el método `login()`, configura los selectores de la página de login:
   ```python
   username_field = wait.until(
       EC.presence_of_element_located((By.ID, "tu-selector-aqui"))
   )
   ```
3. En el método `buscar_por_ruc()`, configura los selectores de búsqueda y extracción

### Ayuda para encontrar selectores:
1. Abre la plataforma Claro en Chrome
2. Presiona F12 (DevTools)
3. Usa el selector de elementos (Ctrl+Shift+C)
4. Haz clic en los campos que necesitas
5. Copia el ID, clase o selector CSS

## 📁 Estructura del Proyecto

```
Filtrador_Masivo_RUCs/
├── credentials.json          # Credenciales Google Sheets API
├── .env                      # Variables de entorno (crear)
├── .env.example              # Plantilla de configuración
├── config.py                 # Configuración centralizada
├── main.py                   # Script principal
├── requirements.txt          # Dependencias Python
├── modules/
│   ├── __init__.py
│   ├── sheets_manager.py     # Gestor de Google Sheets
│   ├── sunat_scraper.py      # Consulta a SUNAT
│   └── claro_scraper.py      # Scraping de Claro
└── README.md
```

## 🔧 Solución de Problemas

### Error: "Spreadsheet not found"
- Verifica que el `SPREADSHEET_ID` en `.env` sea correcto
- Asegúrate de haber compartido el sheet con la cuenta de servicio

### Error: "Worksheet not found"
- Verifica que la pestaña se llame exactamente **"Datos_Filtrados"**
- O cambia `SHEET_NAME` en `.env`

### Error en login de Claro
- Verifica las credenciales en `.env`
- Configura los selectores correctos en `claro_scraper.py`

### API de SUNAT no responde
- El script usa múltiples APIs de respaldo
- Si todas fallan, verifica tu conexión a internet

## 📊 Optimización de API Calls

El sistema usa **batch updates** para minimizar llamadas a la API de Google Sheets:

- **Sin optimizar**: ~2000 requests para 2000 RUCs
- **Con batch updates**: ~41 requests para 2000 RUCs
- **Ahorro**: 98% menos requests

## 🤝 Contribuir

Este es un proyecto interno de Claro. Para contribuir:
1. Crea un branch para tu feature
2. Haz commit de tus cambios
3. Crea un Pull Request

## 📄 Licencia

Uso interno - Claro Perú

## 👨‍💻 Autor

Desarrollado para el equipo de Claro Perú

---

**Nota**: Recuerda configurar el módulo `claro_scraper.py` según la estructura específica de tu plataforma interna antes de ejecutar el script.
