# Emulador de File System Virtual con Asignación Enlazada

**Curso:** Sistemas Operativos (Escuela de Computación)  
**Institución:** Instituto Tecnológico de Costa Rica (ITCR)  
**Profesora:** Ing. Erika Marín Schumann  
**Semestre:** I Semestre 2026  

## Integrantes

| Nombre                      | Carnet     |
|-----------------------------|------------|
| Daniel Alemán Ruiz          | 2023051957 |
| Joseph Arrieta Mora         | 2023020875 |
| Sebastián Rodríguez Sánchez | 2023074446 |

---

## Descripción General

Este proyecto implementa un **emulador de sistema de archivos (File System)** virtual con estructura jerárquica de directorios y almacenamiento respaldado en un archivo binario (`disk.bin`) que actúa como el disco físico simulado.

El sistema emplea una **Tabla de Asignación de Archivos (FAT)** gestionada en memoria, con asignación de sectores mediante el algoritmo **First Fit** y encadenamiento de bloques de forma **enlazada**, lo que permite fragmentación no contigua. La interfaz gráfica, construida con **Flet**, ofrece una terminal interactiva con árbol de directorios dinámico y visualización de la ruta actual en todo momento.

---

## Requisitos de Diseño Implementados

| Requisito | Estado | Mecanismo |
| :--- | :---: | :--- |
| **Asignación Enlazada** | ✅ Completado | La FAT en memoria encadena sectores: cada sector apunta al siguiente o a EOF (`-2`). |
| **Algoritmo First Fit** | ✅ Completado | `find_free_sectors` escanea linealmente la FAT desde el sector `0` hasta encontrar la cantidad requerida de bloques libres. |
| **Control de Sectores Vacíos** | ✅ Completado | La FAT se inicializa con `-1` (libre). Al liberar un archivo, se restauran los sectores a `-1`. |
| **Almacenamiento No Contiguo** | ✅ Completado | Los sectores asignados no necesitan ser contiguos; los punteros de la FAT los encadenan. |
| **Persistencia Física** | ✅ Completado | Los datos se escriben en `file-system/disk.bin`. Al cerrar la aplicación, el archivo binario persiste pero la jerarquía lógica en memoria se reinicia. |
| **Seguridad de Nombres Duplicados** | ✅ Completado | Si el nombre ya existe, se lanza `FileExistsConflictException` y se solicita confirmación de sobrescritura. |
| **Aviso de Disco Lleno** | ✅ Completado | Se lanza `DiskFullException` si no hay sectores libres suficientes para el archivo nuevo. |

---

## Estructura del Proyecto

```
/flet-file-system
├── main.py                # Interfaz gráfica (Flet) y dispatcher de comandos
├── README.md              # Este archivo
├── /core
│   ├── file_system.py     # Lógica del FS: FSNode, FileSystem, comandos
│   └── virtual_disk.py    # Disco virtual: FAT, First Fit, lectura/escritura
├── /file-system
│   └── disk.bin           # Archivo binario del disco simulado (generado en runtime)
└── /assets
    └── fs_icon.png        # Ícono de la aplicación
```

---

## Arquitectura y Componentes

### 1. Interfaz Gráfica (`main.py`)

Desarrollada con **Flet** bajo un diseño moderno de alta fidelidad:

- **Árbol de Directorios (TREE):** Panel lateral izquierdo con visualización en tiempo real de la jerarquía completa. Resalta visualmente el directorio actual (`◄`), diferencia carpetas (`📁`) de archivos (`📄`) y usa colores distintos por tipo.
- **Terminal Integrada:** Soporta comandos interactivos con atajos de teclado estilo Unix:
  - Historial de comandos con `↑` / `↓`.
  - `Ctrl+U` para limpiar la línea, `Ctrl+W` para borrar la última palabra, `Ctrl+K` para truncar.
  - Autocompletado de rutas virtuales con `Tab`.
- **Ruta Actual Dinámica:** Visible en el encabezado en todo momento.
- **Diálogos Gráficos:** Confirmación de sobrescritura, editor de archivos (FILE/MODFILE) con validación inline.

### 2. Disco Virtual (`core/virtual_disk.py`)

Módulo de abstracción a bajo nivel:

- **`create_disk(num_sectors, sector_size)`:** Crea físicamente el archivo `disk.bin` con `num_sectors × sector_size` bytes en ceros e inicializa la FAT.
- **`read_sector(i)` / `write_sector(i, data)`:** Operaciones atómicas de I/O por bloque.
- **`find_free_sectors(n)`:** Implementación de **First Fit** — escanea secuencialmente y retorna los primeros `n` sectores libres (`fat[i] == -1`).
- **`allocate_file_sectors(size_bytes)`:** Calcula sectores necesarios, los busca con First Fit y los enlaza en la FAT.
- **`free_file_sectors(start)`:** Libera la cadena entera de sectores de un archivo.
- **`get_free_sectors_count()`:** Retorna el total de sectores disponibles.

### 3. File System Lógico (`core/file_system.py`)

Capa de alto nivel:

- **`FSNode`:** Nodo del árbol (archivo o directorio). Almacena nombre, padre, hijos, `first_sector`, `size`, fechas de creación y modificación.
- **`FileSystem`:** Raíz del árbol y directorio actual. Implementa todos los comandos del sistema.
- **Resolución de rutas:** Soporte para rutas absolutas (`/dir/subdir`), relativas (`.`, `..`) y el alias `/root/...`.
- **Excepciones:** `FileSystemException`, `DiskFullException`, `FileExistsConflictException`.

---

## Comandos Disponibles

| Comando | Sintaxis | Descripción |
| :--- | :--- | :--- |
| **CREATE** | `CREATE <sectores> <tamaño>` | Inicializa el disco virtual. |
| **FILE** | `FILE [nombre.ext]` | Crea un archivo (abre el editor gráfico). |
| **MKDIR** | `MKDIR <ruta>` | Crea un directorio (soporta rutas anidadas). |
| **CAMBIARDIR** | `CAMBIARDIR <ruta>` | Cambia el directorio actual (`.`, `..`, absoluto, relativo). |
| **LISTARDIR** | `LISTARDIR [ruta]` | Lista el contenido del directorio actual o de la ruta indicada. |
| **MODFILE** | `MODFILE <ruta>` | Modifica el contenido de un archivo (abre el editor gráfico). |
| **VERFILE** | `VERFILE <ruta>` | Muestra el contenido de un archivo en la terminal. |
| **VERPROPIEDADES** | `VERPROPIEDADES <ruta>` | Muestra nombre, extensión, tamaño, fecha de creación y modificación. |
| **COPY** | `COPY <origen> <destino>` | Copia archivos/directorios: Real→Virtual, Virtual→Real, Virtual→Virtual. |
| **MOVER** | `MOVER <origen> <destino>` | Mueve o renombra archivos/directorios (funciona como `rename`). |
| **REMOVE** | `REMOVE <ruta> [ruta2 ...]` | Elimina archivos o directorios (recursivo para directorios). |
| **FIND** | `FIND <patrón> [ruta_inicio]` | Busca por nombre (soporta comodines `*` y `?`). |
| **TREE** | `TREE` | Imprime el árbol completo del File System en la terminal. |
| **MAPA** | `MAPA` | Muestra el estado actual de la FAT (sectores libres/usados). |
| **HELP** | `HELP` | Lista todos los comandos con su descripción. |

---

## Instrucciones de Ejecución

### Prerrequisitos

Python 3 y la biblioteca `flet`:

```bash
pip install flet
```

### Iniciar la Aplicación

Desde la raíz del proyecto:

```bash
python main.py
```

### Flujo Básico

```bash
# 1. Inicializar el disco virtual (5000 sectores de 512 bytes = ~2.4 MB)
CREATE 5000 512

# 2. Crear directorios
MKDIR documentos
MKDIR documentos/fotos

# 3. Crear archivos (abre el editor gráfico)
FILE documentos/notas.txt

# 4. Navegar
CAMBIARDIR documentos
LISTARDIR

# 5. Ver propiedades y contenido
VERPROPIEDADES notas.txt
VERFILE notas.txt

# 6. Copiar un archivo real al FS virtual
COPY C:\Users\usuario\archivo.txt /documentos/archivo.txt

# 7. Buscar archivos
FIND *.txt

# 8. Ver árbol completo
TREE
```

---

## Notas de Diseño

- **Fragmentación interna:** Al ser asignación enlazada, el último sector de un archivo puede estar parcialmente vacío (relleno con `\x00`).
- **Persistencia:** Al cerrar la app, el árbol lógico en memoria se pierde, pero `disk.bin` permanece en disco.
- **Ruta virtual siempre visible:** El encabezado de la interfaz muestra la ruta actual en todo momento.
- **Comodines en FIND:** Se soportan patrones como `*.txt`, `nota?`, `doc*`.
- **MOVER como rename:** `MOVER archivo.txt nuevo_nombre.txt` renombra el archivo en el mismo directorio.
