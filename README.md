# Emulador de File System

Este proyecto consiste en el diseño e implementación de un emulador de sistema de archivos (File System) virtual estructurado en sectores y enlazado, desarrollado con fines didácticos para la cátedra de Sistemas Operativos del Instituto Tecnológico de Costa Rica (Semestre I - 2026).

El software proporciona una interfaz gráfica interactiva que representa la estructura jerárquica de archivos y directorios en memoria (representada como un árbol visual), respaldada por un almacenamiento persistente en un archivo binario (`disk.bin`) que actúa como el disco físico simulado.

---

## 📋 Requisitos del Proyecto e Implementación

De acuerdo con las especificaciones solicitadas, se han incorporado los siguientes lineamientos de diseño en el núcleo de la aplicación:

| Requisito | Estado | Mecanismo de Implementación |
| :--- | :---: | :--- |
| **Asignación Enlazada** | **Completado** | La estructura de archivos se enlaza en memoria mediante una tabla de asignación de archivos (FAT) simulada. Cada sector apunta al siguiente índice lógico o a un marcador de fin de archivo (EOF). |
| **Algoritmo First Fit** | **Completado** | Para la asignación de sectores, el sistema escanea de manera lineal la tabla de asignación desde el sector inicial `0` y toma el primer conjunto de sectores libres que satisfagan la solicitud de espacio. |
| **Control de Sectores Vacíos** | **Completado** | Se realiza el seguimiento dinámico de sectores disponibles (inicializados en `-1` en la FAT). El espacio se reclama y se libera en tiempo real mediante algoritmos de asignación y desasignación. |
| **Soporte No Contiguo** | **Completado** | Al ser una asignación enlazada, los archivos virtuales se pueden fragmentar y almacenar en sectores dispersos del disco virtual cuando no hay espacio contiguo disponible. |
| **Persistencia Física** | **Completado** | Se escribe físicamente en un archivo binario de tamaño predefinido (`disk.bin`). Al cerrar la aplicación, la jerarquía lógica en memoria se reinicia, pero los datos binarios persisten en el disco simulado. |

---

## 🏗️ Arquitectura y Componentes Completados (Núcleo)

Se ha desarrollado la arquitectura base del sistema, que comprende los siguientes módulos funcionales:

### 1. Interfaz Gráfica de Usuario (GUI)
Desarrollada utilizando **Flet** bajo un diseño moderno de alta fidelidad:
* **Estructura Dinámica (TREE):** Ubicada en el panel lateral izquierdo, muestra de forma gráfica y en tiempo real el árbol completo de directorios y archivos. Resalta visualmente el directorio de trabajo actual y los tipos de elementos (carpetas vs. archivos).
* **Terminal Integrada:** Soporta comandos interactivos con atajos de teclado estándar de entornos Unix:
  * Historial de comandos mediante las flechas de navegación ($\uparrow$ / $\downarrow$).
  * Combinaciones de teclas para edición rápida (`Ctrl+U` para limpiar línea, `Ctrl+W` para borrar palabra anterior, `Ctrl+K` para truncar texto).
  * Autocompletado inteligente de rutas virtuales con la tecla `Tab`.
* **Ruta de Trabajo Dinámica:** Siempre visible en la parte superior de la ventana principal.

### 2. Gestión de Almacenamiento Virtual (`core/virtual_disk.py`)
Módulo encargado de la abstracción a bajo nivel del disco:
* Creación física del disco simulado escribiendo bloques binarios vacíos de tamaño $N \times S$ bytes.
* Implementación de operaciones atómicas de lectura (`read_sector`) y escritura (`write_sector`) de bloques.
* Algoritmos First Fit para asignación y marcas de liberación en la tabla FAT del disco.


### 3. Comando Principal de Copia (`core/file_system.py`)
Implementación completa y robusta del comando `COPY` para los tres flujos requeridos:
* **Real a Virtual:** Lee un archivo del sistema operativo de la máquina y lo escribe fragmentado en sectores virtuales del disco.
* **Virtual a Real:** Reconstruye un archivo leyendo secuencialmente los sectores virtuales del disco simulado y genera un archivo binario nativo en la máquina host.
* **Virtual a Virtual:** Clona y enlaza información entre nodos del árbol virtual asignando nuevos bloques físicos en disco.
* *Nota:* Incluye control de colisiones. Si el destino ya existe, el sistema pausa la ejecución y despliega un diálogo gráfico preguntando al usuario si desea sobreescribir el elemento.

### 4. Documentación Asociada (Daniel)
* **Estrategia de Solución:** Redacción formal de la arquitectura lógica y física empleada.
* **Bitácora de Trabajo:** Registro cronológico de actividades y reuniones de las tres semanas.

---

## 🛠️ Guía de Integración (Desarrollo Pendiente)

El proyecto cuenta con placeholders y firmas predefinidas para facilitar la integración de los componentes restantes a cargo del equipo de trabajo.

### Flujo de Registro de Nuevos Comandos
Para añadir un comando nuevo, se deben seguir los siguientes pasos:
1. Implementar la lógica de negocio en el archivo **file_system.py**
2. Capturar la instrucción dentro de la función `execute_command_logic` en **main.py** y llamar al método correspondiente del backend.
3. Retornar una cadena de texto confirmando el éxito o los detalles del proceso para que la GUI los imprima en la consola.

### Módulos y Documentación a Integrar

#### 📌 Sección de Rutas y Directorios (Sebastian)
##### Desarrollo Técnico:
1. **MKDIR:** Completar la validación de directorios para evitar nombres duplicados dentro de una misma ruta y permitir la creación de rutas anidadas.
2. **CD (CambiarDIR):** Implementar la lógica para cambiar el directorio actual de trabajo, soportando navegación absoluta, relativa (`.`, `..`) y rutas largas.
3. **ListarDIR:** Retornar y formatear la lista de elementos hijos de la ruta de trabajo para imprimirlos en consola con sus correspondientes marcadores de tipo.
4. **FIND:** Buscar un archivo o directorio por coincidencia exacta o comodines (ej. `*.txt`) recorriendo el árbol virtual y listar todas las rutas donde se localice.
5. **ReMove:** Eliminar archivos y carpetas de forma recursiva en la jerarquía, asegurando que se liberen los sectores correspondientes en la FAT mediante `self.disk.free_file_sectors()`.

##### Documentación Asociada:
* **Casos de Prueba:** Definir y detallar cada prueba (entradas, resultados esperados y obtenidos) para evaluar la funcionalidad completa del programa.
* **Manual de Usuario:** Redactar el manual técnico y de uso con las instrucciones para compilar y correr la tarea.

#### 📌 Sección de Operaciones de Archivos (Joseph)
##### Desarrollo Técnico:
1. **FILE:** Crear un archivo virtual solicitando el contenido inicial en la consola de comandos. Debe instanciar el nodo e invocar al método `write_virtual_file_content`.
2. **ModFILE:** Buscar un archivo virtual determinado y sobreescribir su contenido reasignando sectores libres en la FAT.
3. **VerFile:** Cargar un archivo virtual a partir de sus sectores enlazados y mostrar su representación en formato texto en la terminal gráfica.
4. **VerPropiedades:** Extraer los metadatos almacenados en el nodo `FSNode` de un archivo (Nombre, Extensión, Tamaño en bytes, Fecha de Creación y Modificación) y presentarlos formalmente.
5. **MoVer:** Desplazar un archivo o carpeta hacia otra ruta o renombrarlo en caliente alterando su relación de jerarquía en el árbol de directorios.

##### Documentación Asociada:
* **Análisis de Resultados:** Elaborar el listado de las tareas y actividades del proyecto a nivel funcional, detallando y justificando sus porcentajes de realización.

---

## ▶️ Instrucciones de Ejecución

### Prerrequisitos
Es necesario disponer de Python 3 y la biblioteca `flet` instalada:
```bash
pip install flet
```

### Inicialización de la Aplicación
Navegar al directorio del proyecto y ejecutar el archivo principal:
```bash
cd flet-file-system
python main.py
```

Al abrir la interfaz, configure e inicialice el tamaño del disco usando el comando `CREATE`:
```bash
CREATE <cantidad_de_sectores> <tamaño_de_sector>
# Ejemplo: CREATE 5000 512
```

Una vez creado, podrá utilizar los comandos soportados del sistema (consulte el comando `HELP` en la consola para obtener más información).
