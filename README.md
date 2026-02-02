# 🩺 Sistema de Gestión de Órdenes Médicas - Policlínico Tabancura

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)
![Streamlit](https://img.shields.io/badge/Framework-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit)
![PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL-336791?style=for-the-badge&logo=postgresql)
![Pandas](https://img.shields.io/badge/Library-Pandas-150458?style=for-the-badge&logo=pandas)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

## 📝 Descripción
Este repositorio contiene la solución integral para la digitalización, validación y gestión de órdenes médicas del **Policlínico Tabancura**. El sistema permite centralizar la información proveniente de múltiples fuentes (Excel, CSV, entradas manuales), normalizarla mediante un maestro de aranceles y disponibilizarla a través de una interfaz web intuitiva.

El enfoque principal es la **integridad de los datos** y la **eficiencia operativa**, eliminando la dispersión de información en archivos locales y migrándola a una estructura de base de datos robusta.

---

## ✨ Características Principales

### 1. Panel de Control (Dashboard)
* Interfaz desarrollada en **Streamlit** para una navegación fluida.
* Visualización en tiempo real de las órdenes ingresadas.
* Filtros avanzados por paciente, médico, fecha o tipo de examen.

### 2. Motor de Importación e Ingesta
* Script especializado (`import.py`) para la migración de datos históricos.
* Limpieza automática de duplicados y normalización de formatos de fecha y RUT.
* Validación cruzada contra el archivo maestro `aranceles.xlsx`.

### 3. Gestión de Aranceles
* Módulo de consulta de códigos y precios médicos.
* Soporte para actualizaciones masivas de aranceles mediante carga de archivos Excel.

### 4. Persistencia de Datos
* Arquitectura preparada para conectar con **PostgreSQL**.
* Generación de respaldos automáticos en formatos `.csv` y `.xlsx` para auditoría interna.

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
| :--- | :--- |
| **Lenguaje** | Python 3.10+ |
| **Frontend** | Streamlit |
| **Análisis de Datos** | Pandas, Openpyxl |
| **Base de Datos** | PostgreSQL / SQL Alchemy |
| **Entorno Virtual** | Venv / Pip |

---

## 📂 Estructura del Proyecto

```text
ordenes-medicas/
├── main.py              # Aplicación principal de Streamlit
├── import.py            # Script de migración y carga de datos
├── aranceles.xlsx       # Base de datos maestra de prestaciones y códigos
├── ordenes-medicas.csv  # Dataset de salida y registros históricos
├── requirements.txt     # Dependencias del sistema
├── .gitignore           # Exclusión de entornos virtuales y archivos sensibles
└── logo.png             # Identidad visual de la clínica
