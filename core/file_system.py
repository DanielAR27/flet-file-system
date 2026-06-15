import os
import fnmatch
from datetime import datetime
from core.virtual_disk import VirtualDisk

class FileSystemException(Exception):
    pass

class DiskFullException(FileSystemException):
    pass

class FileExistsConflictException(FileSystemException):
    pass

class FSNode:
    def __init__(self, name: str, is_directory: bool, parent=None):
        self.name = name
        self.is_directory = is_directory
        self.parent = parent
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
        
        # Atributos de directorio
        self.children = {} if is_directory else None
        
        # Atributos de archivo
        self.first_sector = -1 if not is_directory else None
        self.size = 0 if not is_directory else None

    def get_extension(self) -> str:
        if self.is_directory:
            return ""
        parts = self.name.rsplit(".", 1)
        return parts[1] if len(parts) > 1 else ""

    def get_name_without_extension(self) -> str:
        if self.is_directory:
            return self.name
        parts = self.name.rsplit(".", 1)
        return parts[0]

class FileSystem:
    def __init__(self):
        self.root = FSNode("root", is_directory=True)
        self.current_dir = self.root
        self.disk = VirtualDisk()

    def get_path_for_node(self, node: "FSNode") -> str:
        """Retorna la ruta absoluta de cualquier FSNode."""
        path_nodes = []
        curr = node
        while curr is not None:
            path_nodes.append(curr.name)
            curr = curr.parent
        path_nodes.reverse()
        return "/" + "/".join(path_nodes[1:]) if len(path_nodes) > 1 else "/"

    def get_current_path_str(self) -> str:
        """Retorna la ruta absoluta del directorio de trabajo actual."""
        return self.get_path_for_node(self.current_dir)

    def resolve_virtual_path(self, path: str) -> FSNode:
        """
        Resuelve una ruta virtual (absoluta o relativa) y retorna el nodo FSNode correspondiente.
        Si la ruta no es válida, retorna None.
        Soporta /root/... como alias de /... (para facilidad del usuario).
        """
        if not path:
            return self.current_dir

        # Determinar punto de inicio
        if path.startswith("/"):
            curr = self.root
            parts = [p for p in path.split("/") if p]
            # Aceptar /root/... como alias de /... 
            if parts and parts[0] == self.root.name:
                parts = parts[1:]
        else:
            curr = self.current_dir
            parts = [p for p in path.split("/") if p]

        for part in parts:
            if part == ".":
                continue
            elif part == "..":
                if curr.parent is not None:
                    curr = curr.parent
            else:
                if curr.children and part in curr.children:
                    curr = curr.children[part]
                else:
                    return None
        return curr

    def get_tree_structure(self, node: FSNode = None, prefix_lines: list = None) -> list:
        """
        Retorna una lista de tuplas (prefix_lines, name, is_directory, node) para construir el árbol visual.
        Es recursiva y sigue el formato necesario para la GUI en Flet.
        """
        if node is None:
            node = self.root
        if prefix_lines is None:
            prefix_lines = []

        result = []
        
        # Agregar el nodo actual (incluyendo referencia al nodo para resaltado)
        result.append((prefix_lines.copy(), node.name, node.is_directory, node))

        if node.is_directory and node.children:
            child_list = list(node.children.values())
            # Ordenar directorios primero, luego archivos alfabéticamente
            child_list.sort(key=lambda x: (not x.is_directory, x.name.lower()))
            
            for i, child in enumerate(child_list):
                is_last = (i == len(child_list) - 1)
                new_prefix = prefix_lines.copy()
                
                # Definir conector de línea
                if is_last:
                    new_prefix.append("└── ")
                else:
                    new_prefix.append("├── ")
                
                # Para la recursión de los hijos del hijo, el prefijo cambia a espacios o línea continua
                child_recursion_prefix = prefix_lines.copy()
                if is_last:
                    child_recursion_prefix.append("    ")
                else:
                    child_recursion_prefix.append("│   ")
                
                # Llamada recursiva
                child_results = self.get_tree_structure(child, child_recursion_prefix)
                # Reemplazar el prefijo del primer elemento (el hijo en sí) para que tenga el conector correcto
                child_results[0] = (new_prefix, child.name, child.is_directory, child)
                result.extend(child_results)
                
        return result

    # =========================================================================
    # AUTOCOMPLETE
    # =========================================================================

    def get_completions(self, partial_path: str) -> list:
        """
        Dado un token parcial, retorna una lista de posibles completaciones (rutas virtuales).
        """
        if not self.root:
            return []

        # Separar parte de directorio y parte de nombre
        if "/" in partial_path:
            last_slash = partial_path.rfind("/")
            dir_part = partial_path[:last_slash] or "/"
            name_part = partial_path[last_slash + 1:]
        else:
            dir_part = ""
            name_part = partial_path

        # Resolver el directorio contenedor
        if dir_part:
            dir_node = self.resolve_virtual_path(dir_part)
        else:
            dir_node = self.current_dir

        if dir_node is None or not dir_node.is_directory:
            return []

        # Encontrar hijos que comiencen con el nombre parcial
        matches = []
        for child_name, child_node in dir_node.children.items():
            if child_name.startswith(name_part):
                if dir_part:
                    full_path = dir_part.rstrip("/") + "/" + child_name
                else:
                    full_path = child_name
                if child_node.is_directory:
                    full_path += "/"
                matches.append(full_path)

        return sorted(matches)

    # =========================================================================

    def cmd_create(self, num_sectors: int, sector_size: int, disk_path: str = None) -> str:
        """
        Inicializa un disco virtual limpio.
        """
        try:
            self.disk.create_disk(num_sectors, sector_size, disk_path)
            self.root = FSNode("root", is_directory=True)
            self.current_dir = self.root
            return f"Éxito: Disco virtual creado en '{self.disk.disk_path}' ({num_sectors} sectores, {sector_size} bytes c/u)."
        except Exception as e:
            raise FileSystemException(f"Error al crear el disco virtual: {str(e)}")

    def read_virtual_file_content(self, file_node: FSNode) -> bytes:
        """
        Lee el contenido de un archivo virtual siguiendo la cadena en la FAT.
        """
        if file_node.is_directory:
            raise FileSystemException("No se puede leer el contenido de un directorio.")

        if file_node.first_sector == -1 or file_node.size == 0:
            return b""

        content = bytearray()
        current_sector = file_node.first_sector
        bytes_to_read = file_node.size

        while current_sector >= 0 and bytes_to_read > 0:
            sector_data = self.disk.read_sector(current_sector)
            # Solo tomar los bytes que corresponden al archivo (evitar leer relleno de ceros del último sector)
            chunk_size = min(bytes_to_read, self.disk.sector_size)
            content.extend(sector_data[:chunk_size])
            bytes_to_read -= chunk_size
            current_sector = self.disk.fat[current_sector]

        return bytes(content)

    def write_virtual_file_content(self, parent_dir: FSNode, name: str, data: bytes, overwrite: bool = False) -> FSNode:
        """
        Escribe datos binarios en sectores enlazados y crea/actualiza el nodo de archivo virtual.
        """
        if not self.disk.is_initialized:
            raise FileSystemException("Debe crear un disco virtual primero usando CREATE.")

        if not parent_dir.is_directory:
            raise FileSystemException("El nodo padre debe ser un directorio.")

        # Verificar si el archivo ya existe
        existing_node = parent_dir.children.get(name)
        old_sectors = []
        if existing_node:
            if existing_node.is_directory:
                raise FileExistsConflictException(f"Ya existe un directorio con el nombre '{name}'.")
            if not overwrite:
                raise FileExistsConflictException(f"El archivo '{name}' ya existe en el directorio de destino.")
            
            # Recordar la cadena de sectores para posible rollback
            if existing_node.first_sector >= 0:
                curr = existing_node.first_sector
                while curr >= 0:
                    old_sectors.append(curr)
                    curr = self.disk.fat[curr]
            # Liberar sectores anteriores del archivo a sobreescribir
            self.disk.free_file_sectors(existing_node.first_sector)
            file_node = existing_node
        else:
            file_node = FSNode(name, is_directory=False, parent=parent_dir)

        # Asignar nuevos sectores para el contenido (First Fit)
        allocated_sectors = self.disk.allocate_file_sectors(len(data))
        if not allocated_sectors:
            # Rollback si era archivo existente
            if existing_node and old_sectors:
                for i in range(len(old_sectors) - 1):
                    self.disk.fat[old_sectors[i]] = old_sectors[i+1]
                self.disk.fat[old_sectors[-1]] = -2
            raise DiskFullException("Error: No hay suficiente espacio.")

        # Escribir los datos por fragmentos en los sectores asignados
        for i, sector_idx in enumerate(allocated_sectors):
            start = i * self.disk.sector_size
            end = start + self.disk.sector_size
            chunk = data[start:end]
            self.disk.write_sector(sector_idx, chunk)

        # Configurar metadatos del nodo
        file_node.first_sector = allocated_sectors[0]
        file_node.size = len(data)
        file_node.modified_at = datetime.now()

        # Agregar al padre si es nuevo
        if not existing_node:
            parent_dir.children[name] = file_node

        return file_node

    def is_virtual_path(self, path: str) -> bool:
        """
        Determina de manera robusta si una ruta es virtual (dentro de nuestro FS) o real (del SO).
        """
        if ":" in path:
            return False
        if "\\" in path:
            return False
        if path.startswith("/"):
            return True
        
        # Si existe físicamente y no está resuelto virtualmente, asumimos real
        if os.path.exists(path) and self.resolve_virtual_path(path) is None:
            return False
            
        return True

    def cmd_copy(self, src_path: str, dest_path: str, overwrite: bool = False) -> str:
        """
        Implementa los 3 tipos de copia para archivos Y directorios:
        1. Real  → Virtual
        2. Virtual → Real
        3. Virtual → Virtual
        """
        src_is_virtual  = self.is_virtual_path(src_path)
        dest_is_virtual = self.is_virtual_path(dest_path)

        # ── Caso 1: Real → Virtual ────────────────────────────────────────────
        if not src_is_virtual and dest_is_virtual:
            resolved_src = src_path
            if not os.path.isabs(src_path) and not (len(src_path) > 1 and src_path[1] == ':'):
                if not os.path.exists(src_path):
                    from core.virtual_disk import BASE_DIR
                    alt = os.path.join(BASE_DIR, src_path)
                    if os.path.exists(alt):
                        resolved_src = alt

            if not os.path.exists(resolved_src):
                raise FileSystemException(f"El origen real '{src_path}' no existe.")

            # Resolver directorio virtual de destino
            dest_node = self.resolve_virtual_path(dest_path)
            if dest_node is not None and dest_node.is_directory:
                dest_dir_node = dest_node
                entry_name    = os.path.basename(resolved_src.rstrip("/\\"))
            elif dest_node is None:
                parent_path, entry_name = os.path.split(dest_path)
                dest_dir_node = self.resolve_virtual_path(parent_path)
                if not dest_dir_node or not dest_dir_node.is_directory:
                    raise FileSystemException(
                        f"Directorio virtual de destino '{dest_path}' no encontrado."
                    )
            else:
                raise FileSystemException(
                    f"'{dest_path}' ya existe como archivo en el FS virtual."
                )

            if os.path.isdir(resolved_src):
                count     = self._copy_real_dir_to_virtual(resolved_src, dest_dir_node, entry_name, overwrite)
                full_dest = self.get_path_for_node(dest_dir_node).rstrip("/") + "/" + entry_name
                return f"Copia Real→Virtual exitosa: directorio '{src_path}' → '{full_dest}' ({count} archivo(s))."

            with open(resolved_src, "rb") as f:
                file_data = f.read()
            self.write_virtual_file_content(dest_dir_node, entry_name, file_data, overwrite=overwrite)
            full_dest = self.get_path_for_node(dest_dir_node).rstrip("/") + "/" + entry_name
            return f"Copia Real→Virtual exitosa: '{src_path}' → '{full_dest}'."

        # ── Caso 2: Virtual → Real ────────────────────────────────────────────
        elif src_is_virtual and not dest_is_virtual:
            src_node = self.resolve_virtual_path(src_path)
            if src_node is None:
                raise FileSystemException(f"El elemento virtual '{src_path}' no existe.")

            if src_node.is_directory:
                from core.virtual_disk import BASE_DIR
                is_abs = os.path.isabs(dest_path) or (len(dest_path) > 1 and dest_path[1] == ':')
                if os.path.isdir(dest_path):
                    real_parent = dest_path
                elif not is_abs and os.path.isdir(os.path.join(BASE_DIR, dest_path)):
                    real_parent = os.path.join(BASE_DIR, dest_path)
                else:
                    raise FileSystemException(
                        f"Para copiar un directorio virtual al SO, '{dest_path}' debe ser "
                        "un directorio real existente."
                    )
                count     = self._copy_virtual_dir_to_real(src_node, real_parent, src_node.name, overwrite)
                real_dest = os.path.join(real_parent, src_node.name)
                return f"Copia Virtual→Real exitosa: directorio '{src_path}' → '{real_dest}' ({count} archivo(s))."

            # Resolver ruta destino real para archivo
            real_dest_file = dest_path
            is_absolute    = os.path.isabs(dest_path) or (len(dest_path) > 1 and dest_path[1] == ':')
            if not is_absolute:
                from core.virtual_disk import BASE_DIR
                if os.path.isdir(dest_path):
                    real_dest_file = os.path.join(dest_path, src_node.name)
                elif os.path.isdir(os.path.join(BASE_DIR, dest_path)):
                    real_dest_file = os.path.join(BASE_DIR, dest_path, src_node.name)
                else:
                    dest_parent_dir = os.path.dirname(dest_path)
                    if dest_parent_dir:
                        if os.path.exists(dest_parent_dir):
                            real_dest_file = dest_path
                        else:
                            alt_parent = os.path.join(BASE_DIR, dest_parent_dir)
                            if os.path.exists(alt_parent):
                                real_dest_file = os.path.join(BASE_DIR, dest_path)
                            else:
                                raise FileSystemException(
                                    f"La ruta real de destino '{dest_parent_dir}' no existe."
                                )
                    else:
                        real_dest_file = dest_path
            else:
                if os.path.isdir(dest_path):
                    real_dest_file = os.path.join(dest_path, src_node.name)
                else:
                    dest_parent_dir = os.path.dirname(dest_path)
                    if dest_parent_dir and not os.path.exists(dest_parent_dir):
                        raise FileSystemException(
                            f"La ruta real de destino '{dest_parent_dir}' no existe."
                        )

            if os.path.exists(real_dest_file) and not overwrite:
                raise FileExistsConflictException(
                    f"El archivo real '{real_dest_file}' ya existe en el disco."
                )

            file_data = self.read_virtual_file_content(src_node)
            with open(real_dest_file, "wb") as f:
                f.write(file_data)
            return f"Copia Virtual→Real exitosa: '{src_path}' → '{real_dest_file}'."

        # ── Caso 3: Virtual → Virtual ──────────────────────────────────────────
        elif src_is_virtual and dest_is_virtual:
            src_node = self.resolve_virtual_path(src_path)
            if src_node is None:
                raise FileSystemException(f"El elemento virtual origen '{src_path}' no existe.")

            filename  = src_node.name
            dest_node = self.resolve_virtual_path(dest_path)

            if dest_node is None:
                parent_path, new_filename = os.path.split(dest_path)
                dest_dir_node = self.resolve_virtual_path(parent_path)
                if dest_dir_node and dest_dir_node.is_directory:
                    filename = new_filename
                else:
                    raise FileSystemException(f"Ruta de destino virtual '{dest_path}' no válida.")
            else:
                if not dest_node.is_directory:
                    raise FileSystemException(
                        f"El destino virtual '{dest_path}' debe ser un directorio."
                    )
                dest_dir_node = dest_node

            if src_node.is_directory:
                if src_node is dest_dir_node or self._is_ancestor(src_node, dest_dir_node):
                    raise FileSystemException(
                        "No se puede copiar un directorio dentro de sí mismo o su subárbol."
                    )
                count     = self._copy_virtual_dir_to_virtual(src_node, dest_dir_node, filename, overwrite)
                full_dest = self.get_path_for_node(dest_dir_node).rstrip("/") + "/" + filename
                return f"Copia Virtual→Virtual exitosa: directorio '{src_path}' → '{full_dest}' ({count} archivo(s))."

            file_data = self.read_virtual_file_content(src_node)
            self.write_virtual_file_content(dest_dir_node, filename, file_data, overwrite=overwrite)
            full_dest = self.get_path_for_node(dest_dir_node).rstrip("/") + "/" + filename
            return f"Copia Virtual→Virtual exitosa: '{src_path}' → '{full_dest}'."

        else:
            raise FileSystemException("Copia de Real a Real no es responsabilidad de este File System.")

    def _copy_real_dir_to_virtual(self, real_path: str, virtual_parent: "FSNode",
                                  dir_name: str, overwrite: bool) -> int:
        """
        Copia recursivamente un directorio real al FS virtual.
        Crea el directorio en virtual_parent si no existe; si ya existe (y es dir), lo reutiliza.
        Retorna la cantidad de archivos copiados.
        """
        existing = virtual_parent.children.get(dir_name)
        if existing:
            if not existing.is_directory:
                raise FileSystemException(
                    f"Ya existe un archivo llamado '{dir_name}' en el destino virtual."
                )
            dest_dir = existing
        else:
            dest_dir = FSNode(dir_name, is_directory=True, parent=virtual_parent)
            virtual_parent.children[dir_name] = dest_dir

        count = 0
        for item in sorted(os.listdir(real_path)):
            item_path = os.path.join(real_path, item)
            if os.path.isfile(item_path):
                with open(item_path, "rb") as f:
                    data = f.read()
                self.write_virtual_file_content(dest_dir, item, data, overwrite=overwrite)
                count += 1
            elif os.path.isdir(item_path):
                count += self._copy_real_dir_to_virtual(item_path, dest_dir, item, overwrite)
        return count

    def _copy_virtual_dir_to_real(self, virtual_node: "FSNode", real_parent: str,
                                   dir_name: str, overwrite: bool) -> int:
        """
        Copia recursivamente un directorio virtual al sistema de archivos real.
        Crea la carpeta en real_parent/dir_name. Retorna la cantidad de archivos copiados.
        """
        real_dir = os.path.join(real_parent, dir_name)
        os.makedirs(real_dir, exist_ok=True)

        count = 0
        if virtual_node.children:
            for child_name, child_node in virtual_node.children.items():
                if child_node.is_directory:
                    count += self._copy_virtual_dir_to_real(child_node, real_dir, child_name, overwrite)
                else:
                    real_file = os.path.join(real_dir, child_name)
                    if os.path.exists(real_file) and not overwrite:
                        raise FileExistsConflictException(
                            f"El archivo real '{real_file}' ya existe."
                        )
                    data = self.read_virtual_file_content(child_node)
                    with open(real_file, "wb") as f:
                        f.write(data)
                    count += 1
        return count

    def _copy_virtual_dir_to_virtual(self, src_node: "FSNode", dest_parent: "FSNode",
                                      dir_name: str, overwrite: bool) -> int:
        """
        Clona recursivamente un directorio dentro del FS virtual.
        Crea o reutiliza el directorio dest_parent/dir_name. Retorna archivos copiados.
        """
        existing = dest_parent.children.get(dir_name)
        if existing:
            if not existing.is_directory:
                raise FileSystemException(
                    f"Ya existe un archivo llamado '{dir_name}' en el destino."
                )
            dest_dir = existing
        else:
            dest_dir = FSNode(dir_name, is_directory=True, parent=dest_parent)
            dest_parent.children[dir_name] = dest_dir

        count = 0
        if src_node.children:
            for child_name, child_node in src_node.children.items():
                if child_node.is_directory:
                    count += self._copy_virtual_dir_to_virtual(child_node, dest_dir, child_name, overwrite)
                else:
                    data = self.read_virtual_file_content(child_node)
                    self.write_virtual_file_content(dest_dir, child_name, data, overwrite=overwrite)
                    count += 1
        return count


    # =========================================================================
    # COMANDOS DE DIRECTORIOS (Sebastian)
    # =========================================================================

    def cmd_mkdir(self, path: str) -> str:
        """
        Crea un directorio en la ruta indicada. Soporta rutas anidadas (ej: docs/imagenes).
        No crea directorios intermedios; el padre debe existir.
        """
        if not path or path.strip() in (".", ".."):
            raise FileSystemException("Nombre de directorio inválido.")

        if path.startswith("/"):
            curr = self.root
            parts = [p for p in path.split("/") if p]
            if parts and parts[0] == self.root.name:
                parts = parts[1:]
        else:
            curr = self.current_dir
            parts = [p for p in path.split("/") if p]

        if not parts:
            raise FileSystemException("Nombre de directorio inválido.")

        # Navegar al directorio padre (todos los segmentos menos el último)
        for part in parts[:-1]:
            if part == ".":
                continue
            elif part == "..":
                if curr.parent is not None:
                    curr = curr.parent
            else:
                if not curr.children or part not in curr.children:
                    raise FileSystemException(
                        f"El directorio padre '{part}' no existe. Navegue con CD primero."
                    )
                node = curr.children[part]
                if not node.is_directory:
                    raise FileSystemException(f"'{part}' no es un directorio.")
                curr = node

        new_name = parts[-1]
        if new_name in (".", ".."):
            raise FileSystemException(f"Nombre de directorio inválido: '{new_name}'.")
        if "/" in new_name or "\\" in new_name:
            raise FileSystemException(f"El nombre '{new_name}' contiene caracteres no válidos.")
        if new_name in curr.children:
            raise FileSystemException(
                f"Ya existe un elemento llamado '{new_name}' en '{self.get_path_for_node(curr)}'."
            )

        new_dir = FSNode(new_name, is_directory=True, parent=curr)
        curr.children[new_name] = new_dir
        created_path = self.get_path_for_node(curr).rstrip("/") + "/" + new_name
        return f"Directorio '{created_path}' creado exitosamente."

    def cmd_cd(self, path: str) -> str:
        """
        Cambia el directorio de trabajo actual.
        Soporta rutas absolutas, relativas, '.' y '..'.
        """
        target = self.resolve_virtual_path(path)
        if target is None:
            raise FileSystemException(f"El directorio '{path}' no existe.")
        if not target.is_directory:
            raise FileSystemException(f"'{path}' no es un directorio.")
        self.current_dir = target
        return f"Directorio actual: {self.get_current_path_str()}"

    def cmd_lsdir(self, path: str = None) -> str:
        """
        Lista el contenido del directorio especificado o del directorio de trabajo actual.
        Muestra tipo, nombre, tamaño (archivos) y fecha de modificación.
        """
        if path:
            target = self.resolve_virtual_path(path)
            if target is None:
                raise FileSystemException(f"El directorio '{path}' no existe.")
            if not target.is_directory:
                raise FileSystemException(f"'{path}' no es un directorio.")
        else:
            target = self.current_dir

        dir_path = self.get_path_for_node(target)

        if not target.children:
            return f"El directorio '{dir_path}' está vacío."

        children = sorted(
            target.children.values(),
            key=lambda x: (not x.is_directory, x.name.lower())
        )
        num_dirs  = sum(1 for c in children if c.is_directory)
        num_files = sum(1 for c in children if not c.is_directory)

        sep   = "─" * 50
        lines = [f"Contenido de '{dir_path}':", sep]

        for child in children:
            date_str = child.modified_at.strftime("%Y-%m-%d %H:%M")
            if child.is_directory:
                lines.append(f"  📁 [DIR]   {child.name:<24} {date_str}")
            else:
                if child.size < 1024:
                    size_str = f"{child.size} B"
                elif child.size < 1024 * 1024:
                    size_str = f"{child.size / 1024:.1f} KB"
                else:
                    size_str = f"{child.size / (1024*1024):.1f} MB"
                lines.append(f"  📄 [FILE]  {child.name:<24} {size_str:>8}  {date_str}")

        lines.append(sep)
        lines.append(f"  {num_dirs} directorio(s), {num_files} archivo(s)")
        return "\n".join(lines)

    def cmd_tree(self) -> str:
        """
        Retorna la representación en forma de árbol del File System virtual.
        """
        structure = self.get_tree_structure()
        lines = []
        for prefix, name, is_dir, _ in structure:
            prefix_str = "".join(prefix)
            icon = "📁 " if is_dir else "📄 "
            lines.append(f"{prefix_str}{icon}{name}")
        
        return "\n".join(lines)

    def cmd_find(self, pattern: str, start_path: str = None) -> str:
        """
        Busca archivos y directorios por nombre usando el patrón dado.
        Soporta comodines * y ? (ej: *.txt, reporte_?).
        Recorre todo el árbol desde la raíz o desde start_path si se indica.
        """
        if not pattern:
            raise FileSystemException("Debe especificar un patrón. Ej: FIND *.txt")

        if start_path:
            start_node = self.resolve_virtual_path(start_path)
            if start_node is None:
                raise FileSystemException(f"La ruta de inicio '{start_path}' no existe.")
            if not start_node.is_directory:
                raise FileSystemException(f"'{start_path}' no es un directorio.")
        else:
            start_node = self.root

        matches: list[tuple[str, FSNode]] = []
        self._find_recursive(start_node, pattern, self.get_path_for_node(start_node), matches)

        if not matches:
            return f"No se encontraron elementos que coincidan con '{pattern}'."

        sep   = "─" * 50
        lines = [f"Resultados para '{pattern}':", sep]
        for path, node in matches:
            type_label = "[DIR] " if node.is_directory else "[FILE]"
            lines.append(f"  {type_label}  {path}")
        lines.append(sep)
        lines.append(f"  {len(matches)} resultado(s) encontrado(s).")
        return "\n".join(lines)

    def _find_recursive(self, node: "FSNode", pattern: str, current_path: str, matches: list):
        """Recorre el árbol recursivamente buscando coincidencias con el patrón."""
        if not node.is_directory or not node.children:
            return
        for child_name, child_node in node.children.items():
            child_path = (
                ("/" + child_name) if current_path == "/"
                else (current_path.rstrip("/") + "/" + child_name)
            )
            if fnmatch.fnmatch(child_name.lower(), pattern.lower()):
                matches.append((child_path, child_node))
            if child_node.is_directory:
                self._find_recursive(child_node, pattern, child_path, matches)

    def cmd_remove(self, path: str) -> str:
        """
        Elimina un archivo o directorio de forma recursiva.
        Libera los sectores FAT de todos los archivos involucrados.
        """
        target = self.resolve_virtual_path(path)
        if target is None:
            raise FileSystemException(f"El elemento '{path}' no existe.")
        if target is self.root:
            raise FileSystemException("No se puede eliminar el directorio raíz.")
        if target is self.current_dir:
            raise FileSystemException(
                "No se puede eliminar el directorio de trabajo actual. Use CD para salir primero."
            )
        if self._is_ancestor(target, self.current_dir):
            raise FileSystemException(
                f"No se puede eliminar '{path}': es un ancestro del directorio actual. "
                "Use CD para salir de él primero."
            )

        target_path = self.get_path_for_node(target)
        count       = self._count_nodes(target)
        type_str    = "Directorio" if target.is_directory else "Archivo"

        self._remove_recursive(target)
        del target.parent.children[target.name]

        return f"{type_str} '{target_path}' eliminado exitosamente ({count} elemento(s) removido(s))."

    def _is_ancestor(self, potential_ancestor: "FSNode", node: "FSNode") -> bool:
        """Retorna True si potential_ancestor es ancestro estricto de node."""
        curr = node.parent
        while curr is not None:
            if curr is potential_ancestor:
                return True
            curr = curr.parent
        return False

    def _count_nodes(self, node: "FSNode") -> int:
        """Cuenta el total de nodos en el subárbol (incluye la raíz del subárbol)."""
        if not node.is_directory or not node.children:
            return 1
        return 1 + sum(self._count_nodes(c) for c in node.children.values())

    def _remove_recursive(self, node: "FSNode"):
        """Elimina recursivamente todos los nodos y libera sectores FAT de archivos."""
        if node.is_directory and node.children:
            for child in list(node.children.values()):
                self._remove_recursive(child)
        elif not node.is_directory:
            if node.first_sector >= 0 and self.disk.is_initialized:
                self.disk.free_file_sectors(node.first_sector)

    # =========================================================================
    # COMANDOS DE ARCHIVOS (Joseph)
    # =========================================================================

    def cmd_file(self, path: str, content: str, overwrite: bool = False) -> str:
        """
        Crea un archivo virtual con el contenido dado.
        Soporta rutas relativas ('notas.txt') y anidadas ('docs/notas.txt').
        """
        if not self.disk.is_initialized:
            raise FileSystemException("Debe crear un disco virtual primero usando CREATE.")

        # Separar directorio padre y nombre de archivo
        if "/" in path:
            last_slash = path.rfind("/")
            parent_path = path[:last_slash] or "/"
            filename    = path[last_slash + 1:]
            parent_dir  = self.resolve_virtual_path(parent_path)
            if parent_dir is None:
                raise FileSystemException(f"El directorio '{parent_path}' no existe.")
            if not parent_dir.is_directory:
                raise FileSystemException(f"'{parent_path}' no es un directorio.")
        else:
            filename   = path
            parent_dir = self.current_dir

        if not filename:
            raise FileSystemException("Nombre de archivo inválido.")

        existing = parent_dir.children.get(filename)
        if existing:
            if existing.is_directory:
                raise FileSystemException(
                    f"Ya existe un directorio con el nombre '{filename}'."
                )
            if not overwrite:
                raise FileExistsConflictException(
                    f"El archivo '{filename}' ya existe en '{self.get_path_for_node(parent_dir)}'."
                )

        data = content.encode("utf-8")
        self.write_virtual_file_content(parent_dir, filename, data, overwrite=overwrite)

        full_path = self.get_path_for_node(parent_dir).rstrip("/") + "/" + filename
        return f"Archivo '{full_path}' creado exitosamente ({len(data)} bytes)."

    def cmd_modfile(self, path: str, new_content: str) -> str:
        """
        Reemplaza el contenido de un archivo virtual existente reasignando sectores en la FAT.
        """
        if not self.disk.is_initialized:
            raise FileSystemException("El disco virtual no está inicializado.")

        target = self.resolve_virtual_path(path)
        if target is None:
            raise FileSystemException(f"El archivo '{path}' no existe.")
        if target.is_directory:
            raise FileSystemException(f"'{path}' es un directorio, no un archivo.")

        data = new_content.encode("utf-8")
        self.write_virtual_file_content(target.parent, target.name, data, overwrite=True)
        return f"Archivo '{self.get_path_for_node(target)}' modificado exitosamente ({len(data)} bytes)."

    def cmd_mapa(self) -> str:
        """
        Imprime el estado de la FAT sector por sector.
        Muestra la asignación para verificar que First Fit funciona correctamente.
        Valores: Libre = sector disponible, EOF = fin de archivo, número = siguiente sector.
        """
        if not self.disk.is_initialized:
            raise FileSystemException("El disco virtual no está inicializado. Use CREATE primero.")

        fat = self.disk.fat
        header = "─" * 60
        lines = ["Estado de la FAT (File Allocation Table):", header]
        
        raw_parts = []
        for i, val in enumerate(fat):
            if val == -1:
                state = "Libre"
            elif val == -2:
                state = "EOF"
            else:
                state = f"→ {val}"
            raw_parts.append(f"[ {i} ] {state}")

        max_part_len = max(len(p) for p in raw_parts)
        parts = []
        for p in raw_parts:
            parts.append(f"{p:<{max_part_len}}")
            if len(parts) == 4:
                lines.append("  " + "   ".join(parts))
                parts = []

        if parts:
            lines.append("  " + "   ".join(parts))

        free = self.disk.get_free_sectors_count()
        used = self.disk.num_sectors - free
        lines.append(header)
        lines.append(f"  Total: {self.disk.num_sectors} sectores  |  Usados: {used}  |  Libres: {free}")
        return "\n".join(lines)

    def cmd_verfile(self, path: str) -> str:
        """
        Lee el contenido de un archivo virtual y lo retorna como texto para mostrar en terminal.
        """
        target = self.resolve_virtual_path(path)
        if target is None:
            raise FileSystemException(f"El archivo '{path}' no existe.")
        if target.is_directory:
            raise FileSystemException(f"'{path}' es un directorio, no un archivo.")
        if not self.disk.is_initialized:
            raise FileSystemException("El disco virtual no está inicializado.")

        raw = self.read_virtual_file_content(target)
        if not raw:
            return f"El archivo '{self.get_path_for_node(target)}' está vacío."

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")

        sep   = "─" * 50
        lines = [f"Contenido de '{self.get_path_for_node(target)}':", sep]
        text_lines = text.splitlines()
        lines.extend(text_lines if text_lines else ["(vacío)"])
        lines.append(sep)
        return "\n".join(lines)

    def cmd_verpropiedades(self, path: str) -> str:
        """
        Muestra los metadatos del nodo: nombre, extensión, tipo, ruta, fechas, tamaño y sectores.
        """
        target = self.resolve_virtual_path(path)
        if target is None:
            raise FileSystemException(f"El elemento '{path}' no existe.")

        sep   = "─" * 44
        lines = [f"Propiedades de '{target.name}':", sep]
        lines.append(f"  Nombre         : {target.name}")
        lines.append(f"  Extensión      : {target.get_extension() or '(sin extensión)'}")
        lines.append(f"  Tipo           : {'Directorio' if target.is_directory else 'Archivo'}")
        lines.append(f"  Ruta completa  : {self.get_path_for_node(target)}")
        lines.append(f"  Fecha creación : {target.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  Última modif.  : {target.modified_at.strftime('%Y-%m-%d %H:%M:%S')}")

        if not target.is_directory:
            sz = target.size
            if sz < 1024:
                size_str = f"{sz} B"
            elif sz < 1048576:
                size_str = f"{sz / 1024:.2f} KB"
            else:
                size_str = f"{sz / 1048576:.2f} MB"
            lines.append(f"  Tamaño         : {size_str} ({sz} bytes)")
            lines.append(f"  Sector inicial : {target.first_sector}")

            if target.first_sector >= 0 and self.disk.is_initialized:
                count, cur = 0, target.first_sector
                while cur >= 0:
                    count += 1
                    cur = self.disk.fat[cur]
                lines.append(f"  Sectores usados: {count}")
        else:
            num_children = len(target.children) if target.children else 0
            lines.append(f"  Elementos      : {num_children} elemento(s)")

        lines.append(sep)
        return "\n".join(lines)

    def cmd_mover(self, src_path: str, dest_path: str) -> str:
        """
        Mueve o renombra un archivo o directorio.
        - Si dest_path es un directorio existente → mueve el elemento dentro de él.
        - Si dest_path no existe → lo usa como nueva ruta/nombre (renombrar o reubicar).
        No modifica la FAT: solo actualiza los punteros del árbol en memoria.
        """
        src_node = self.resolve_virtual_path(src_path)
        if src_node is None:
            raise FileSystemException(f"El elemento origen '{src_path}' no existe.")
        if src_node is self.root:
            raise FileSystemException("No se puede mover el directorio raíz.")
        if src_node is self.current_dir:
            raise FileSystemException(
                "No se puede mover el directorio de trabajo actual. Use CD para salir primero."
            )
        if self._is_ancestor(src_node, self.current_dir):
            raise FileSystemException(
                f"No se puede mover '{src_path}': es un ancestro del directorio actual."
            )

        dest_node = self.resolve_virtual_path(dest_path)

        if dest_node is not None:
            # El destino existe: debe ser un directorio destino contenedor
            if not dest_node.is_directory:
                raise FileSystemException(
                    f"'{dest_path}' ya existe como archivo. Use otro nombre de destino."
                )
            if src_node is dest_node:
                raise FileSystemException("El origen y el destino son el mismo elemento.")
            if src_node.is_directory and self._is_ancestor(src_node, dest_node):
                raise FileSystemException(
                    "No se puede mover un directorio dentro de su propio subárbol."
                )
            if src_node.name in dest_node.children:
                raise FileSystemException(
                    f"Ya existe '{src_node.name}' en '{self.get_path_for_node(dest_node)}'. "
                    "Use REMOVE primero si desea reemplazarlo."
                )
            dest_dir = dest_node
            new_name  = src_node.name
        else:
            # El destino no existe: interpretar como nueva ubicación o nuevo nombre
            if "/" in dest_path:
                last_slash    = dest_path.rfind("/")
                parent_path   = dest_path[:last_slash] or "/"
                new_name      = dest_path[last_slash + 1:]
                dest_dir_node = self.resolve_virtual_path(parent_path)
                if dest_dir_node is None or not dest_dir_node.is_directory:
                    raise FileSystemException(
                        f"El directorio destino '{parent_path}' no existe."
                    )
                dest_dir = dest_dir_node
            else:
                new_name = dest_path
                dest_dir = self.current_dir

            if not new_name or new_name in (".", ".."):
                raise FileSystemException("Nombre de destino inválido.")
            if src_node.is_directory and self._is_ancestor(src_node, dest_dir):
                raise FileSystemException(
                    "No se puede mover un directorio dentro de su propio subárbol."
                )
            if new_name in dest_dir.children:
                raise FileSystemException(
                    f"Ya existe '{new_name}' en '{self.get_path_for_node(dest_dir)}'. "
                    "Use REMOVE primero si desea reemplazarlo."
                )

        old_path   = self.get_path_for_node(src_node)
        old_parent = src_node.parent

        # Desvincular del padre anterior
        del old_parent.children[src_node.name]

        # Actualizar nodo y vincularlo al nuevo padre
        src_node.name        = new_name
        src_node.parent      = dest_dir
        src_node.modified_at = datetime.now()
        dest_dir.children[new_name] = src_node

        new_path = self.get_path_for_node(src_node)
        action   = "renombrado" if old_parent is dest_dir else "movido"
        type_str = "Directorio" if src_node.is_directory else "Archivo"
        return f"{type_str} {action}: '{old_path}'  →  '{new_path}'."