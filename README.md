# Voximplant Tools

Conjunto de scripts en Python diseñados para procesar, consolidar y auditar los reportes de llamadas generados por campañas de Voximplant.  
Este proyecto automatiza tareas repetitivas que anteriormente realizaban procesos manuales en Excel, reduciendo tiempos operativos y asegurando la calidad y consistencia de los datos históricos.



## 🚀 Objetivo del Proyecto

Optimizar el flujo de trabajo de análisis de campañas de llamadas, permitiendo:

- Procesar reportes diarios automáticamente.
- Generar consolidados para cada día.
- Unificar históricos manuales y automáticos.
- Detectar errores y aplicar correcciones especiales.
- Generar bases depuradas listas para BI y auditoría.



## 🧱 Estructura del Proyecto

La estructura del proyecto en este repositorio es:

voxinplant_tools/
│
├── auditar_hist.py

├── corregir_swap_dia.py

├── fusionar_historicos.py

├── voxinplant_consolidador.py

├── requirements_voxinplant.txt
│
├── archive_raw/ # Archivos crudos descargados desde Voximplant (ejemplo vacío)

├── inbox/ # Reportes nuevos pendientes por procesar

├── logs/ # Logs generados por los scripts

└── output/

├── daily/ # Consolidados diarios

└── history/ # Histórico unificado, backups y resúmenes


> 🔒 Por políticas de datos, en este repositorio **no se incluyen archivos reales**.  
> Solo se subirán ejemplos sintéticos si se requieren en el futuro.



## 🧩 Scripts Principales

### `voxinplant_consolidador.py`
Procesa los reportes del día ubicados en la carpeta `inbox/`:

- Limpia y normaliza columnas.
- Clasifica tipos de respuesta.
- Genera archivo consolidado del día.
- Mueve el archivo original a `archive_raw/`.

Genera archivos como:
output/daily/Report_2025-11-11_consolidado.xlsx


### `fusionar_historicos.py`
Combina:

- Consolidados automáticos
- Histórico manual
- Backups existentes

Actualiza archivos como:

output/history/HISTORICO_UNIQUE.xlsx
output/history/BASE_HISTORICA_UNIFICADA.xlsx



Permite contar con un repositorio único y confiable para análisis o BI.


### `corregir_swap_dia.py`
Aplica reglas de corrección específicas cuando se detectan errores en los reportes.  
Ejemplo: el caso del *swap* masivo del 11/11/2025.


### `auditar_hist.py`
Realiza validaciones automáticas:

- Conteos por tipo de llamada
- Revisión de duplicados
- Detención de inconsistencias
- Reglas internas de calidad de datos



## 📦 Requisitos

- Python 3.10+
- Dependencias listadas en:

requirements_voxinplant.txt




## 🔧 Instalación

```bash
git clone https://github.com/cristiannwtf1/voxinplant-tools.git
cd voxinplant-tools

# Crear entorno virtual (opcional)
python -m venv .venv
.\.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements_voxinplant.txt
🚀 Uso
1. Procesar el reporte diario
Coloca el archivo del día en:


inbox/
Ejecuta:


python voxinplant_consolidador.py
Esto genera:


output/daily/Report_YYYY-MM-DD_consolidado.xlsx
2. Actualizar histórico unificado

python fusionar_historicos.py
Genera:


output/history/BASE_HISTORICA_UNIFICADA.xlsx
3. Aplicar correcciones especiales

python corregir_swap_dia.py
4. Auditar el histórico
bash


python auditar_hist.py
📊 Impacto Operativo
Este sistema permitió:

Reducir procesos manuales de 3–4 horas a minutos.

Detectar errores en reportes crudos antes de cargarlos.

Mantener un histórico unificado, depurado y confiable.

Facilitar reporting diario y tableros BI.

Mejorar la trazabilidad y asegurar la calidad de la información.

🔮 Mejoras Futuras
Integración a una API con FastAPI.

Interfaz web para cargar reportes y ejecutar procesos.

Dashboard con métricas en tiempo real.

Pruebas unitarias y pipeline CI/CD.

📄 Licencia
MIT License.
Libre para uso, modificación y distribución con atribución.

✨ Autor
Cristian Cubillos
Desarrollador Python | Analista IT | Automatización de procesos
LinkedIn
