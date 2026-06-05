import os
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

    def get_current_path_str(self) -> str:
        """
        Retorna la ruta absoluta actual en formato de texto (ej: /root/docs)
        """
        path_nodes = []
        curr = self.current_dir
        while curr is not None:
            path_nodes.append(curr.name)
            curr = curr.parent
        path_nodes.reverse()
        return "/" + "/".join(path_nodes[1:]) if len(path_nodes) > 1 else "/"

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
        if existing_node:
            if existing_node.is_directory:
                raise FileExistsConflictException(f"Ya existe un directorio con el nombre '{name}'.")
            if not overwrite:
                raise FileExistsConflictException(f"El archivo '{name}' ya existe en el directorio de destino.")
            
            # Liberar sectores anteriores del archivo a sobreescribir
            self.disk.free_file_sectors(existing_node.first_sector)
            file_node = existing_node
        else:
            file_node = FSNode(name, is_directory=False, parent=parent_dir)

        # Asignar nuevos sectores para el contenido (First Fit)
        allocated_sectors = self.disk.allocate_file_sectors(len(data))
        if not allocated_sectors:
            raise DiskFullException("Error: No hay suficientes sectores libres para guardar este archivo.")

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
        if path.startswith("/"):
            return True
        if "\\" in path or ":" in path:
            return False
        # Si resuelve directamente en el FS virtual, es virtual
        if self.resolve_virtual_path(path) is not None:
            return True
        # Si el padre de la ruta resuelve en el FS virtual, es virtual (caso de archivo nuevo)
        parent_path = os.path.dirname(path)
        if parent_path and self.resolve_virtual_path(parent_path) is not None:
            return True
        # Por defecto, si no resuelve en el FS y no tiene sintaxis de Windows, lo tratamos como real
        return False

    def cmd_copy(self, src_path: str, dest_path: str, overwrite: bool = False) -> str:
        """
        Implementa los 3 tipos de copia para archivos:
        1. Real -> Virtual
        2. Virtual -> Real
        3. Virtual -> Virtual
        """
        src_is_virtual = self.is_virtual_path(src_path)
        dest_is_virtual = self.is_virtual_path(dest_path)

        # Caso 1: Real -> Virtual
        if not src_is_virtual and dest_is_virtual:
            # Intentar resolver ruta origen real (soporte CWD y BASE_DIR fallback)
            resolved_src_path = src_path
            if not os.path.isabs(src_path) and not (len(src_path) > 1 and src_path[1] == ':'):
                if not os.path.exists(src_path):
                    from core.virtual_disk import BASE_DIR
                    alternative_path = os.path.join(BASE_DIR, src_path)
                    if os.path.exists(alternative_path):
                        resolved_src_path = alternative_path

            if not os.path.exists(resolved_src_path):
                raise FileSystemException(f"El archivo origen real '{src_path}' no existe.")
            if os.path.isdir(resolved_src_path):
                raise FileSystemException("Copia de directorios reales no soportada.")
            
            filename = os.path.basename(resolved_src_path)
            
            # Resolver destino virtual
            dest_node = self.resolve_virtual_path(dest_path)
            if dest_node is None:
                # Intentar ver si dest_path incluye el nombre del archivo final
                parent_path, new_filename = os.path.split(dest_path)
                dest_dir_node = self.resolve_virtual_path(parent_path)
                if dest_dir_node and dest_dir_node.is_directory:
                    filename = new_filename
                else:
                    raise FileSystemException(f"Directorio de destino virtual '{dest_path}' no encontrado.")
            else:
                if not dest_node.is_directory:
                    raise FileSystemException(f"La ruta de destino virtual '{dest_path}' no es un directorio.")
                dest_dir_node = dest_node

            # Leer archivo real
            with open(resolved_src_path, "rb") as f:
                file_data = f.read()

            self.write_virtual_file_content(dest_dir_node, filename, file_data, overwrite=overwrite)
            return f"Copia Real->Virtual exitosa: '{src_path}' copiado a '{self.get_current_path_str()}{'/' if self.get_current_path_str() != '/' else ''}{filename}'."

        # Caso 2: Virtual -> Real
        elif src_is_virtual and not dest_is_virtual:
            src_node = self.resolve_virtual_path(src_path)
            if src_node is None:
                raise FileSystemException(f"El archivo origen virtual '{src_path}' no existe.")
            if src_node.is_directory:
                raise FileSystemException("Copia de directorios virtuales al sistema real no soportada.")

            # Resolver ruta destino real
            real_dest_file = dest_path
            
            # Si la ruta destino no es absoluta, intentamos CWD, o fallback a BASE_DIR
            is_absolute = os.path.isabs(dest_path) or (len(dest_path) > 1 and dest_path[1] == ':')
            if not is_absolute:
                from core.virtual_disk import BASE_DIR
                # 1. Si dest_path es un directorio que existe en CWD
                if os.path.isdir(dest_path):
                    real_dest_file = os.path.join(dest_path, src_node.name)
                # 2. Si dest_path es un directorio que existe en BASE_DIR
                elif os.path.isdir(os.path.join(BASE_DIR, dest_path)):
                    real_dest_file = os.path.join(BASE_DIR, dest_path, src_node.name)
                else:
                    # Es un archivo destino final. Verificar el directorio padre.
                    dest_parent_dir = os.path.dirname(dest_path)
                    if dest_parent_dir:
                        if os.path.exists(dest_parent_dir):
                            real_dest_file = dest_path
                        else:
                            alt_parent = os.path.join(BASE_DIR, dest_parent_dir)
                            if os.path.exists(alt_parent):
                                real_dest_file = os.path.join(BASE_DIR, dest_path)
                            else:
                                raise FileSystemException(f"La ruta real de destino '{dest_parent_dir}' no existe.")
                    else:
                        # Si es solo un nombre de archivo en la raíz del CWD
                        real_dest_file = dest_path
            else:
                if os.path.isdir(dest_path):
                    real_dest_file = os.path.join(dest_path, src_node.name)
                else:
                    dest_parent_dir = os.path.dirname(dest_path)
                    if dest_parent_dir and not os.path.exists(dest_parent_dir):
                        raise FileSystemException(f"La ruta real de destino '{dest_parent_dir}' no existe.")

            if os.path.exists(real_dest_file) and not overwrite:
                raise FileExistsConflictException(f"El archivo real '{real_dest_file}' ya existe en el disco.")

            # Leer bytes de los sectores virtuales y escribirlos en el SO
            file_data = self.read_virtual_file_content(src_node)
            with open(real_dest_file, "wb") as f:
                f.write(file_data)
            return f"Copia Virtual->Real exitosa: '{src_path}' copiado a '{real_dest_file}'."

        # Caso 3: Virtual -> Virtual
        elif src_is_virtual and dest_is_virtual:
            src_node = self.resolve_virtual_path(src_path)
            if src_node is None:
                raise FileSystemException(f"El archivo origen virtual '{src_path}' no existe.")
            if src_node.is_directory:
                raise FileSystemException("Copia de directorios virtuales no soportada.")

            filename = src_node.name
            dest_node = self.resolve_virtual_path(dest_path)
            
            if dest_node is None:
                # Intentar ver si dest_path incluye el nombre del archivo final
                parent_path, new_filename = os.path.split(dest_path)
                dest_dir_node = self.resolve_virtual_path(parent_path)
                if dest_dir_node and dest_dir_node.is_directory:
                    filename = new_filename
                else:
                    raise FileSystemException(f"Ruta de destino virtual '{dest_path}' no válida.")
            else:
                if not dest_node.is_directory:
                    raise FileSystemException(f"El destino virtual '{dest_path}' debe ser un directorio.")
                dest_dir_node = dest_node

            # Leer del FS virtual y escribir en los nuevos sectores virtuales del destino
            file_data = self.read_virtual_file_content(src_node)
            self.write_virtual_file_content(dest_dir_node, filename, file_data, overwrite=overwrite)
            return f"Copia Virtual->Virtual exitosa: '{src_path}' copiado a '{dest_dir_node.name}/{filename}'."

        else:
            raise FileSystemException("Copia de Real a Real no es responsabilidad de este File System.")


    # =========================================================================
    # PLACEHOLDERS PARA SEBASTIAN Y JOSEPH
    # (Deben completar la lógica real de estas firmas)
    # =========================================================================

    def cmd_mkdir(self, name: str) -> str:
        # Sebastian implementará validación de repetidos, etc.
        # Por ahora se crea una versión básica para que la GUI funcione.
        if name in self.current_dir.children:
            raise FileExistsConflictException(f"El directorio '{name}' ya existe.")
        new_dir = FSNode(name, is_directory=True, parent=self.current_dir)
        self.current_dir.children[name] = new_dir
        return f"Directorio '{name}' creado."

    def cmd_cd(self, path: str) -> str:
        # Sebastian implementará (cambiarDIR)
        target = self.resolve_virtual_path(path)
        if target and target.is_directory:
            self.current_dir = target
            return f"Cambiado al directorio {self.get_current_path_str()}"
        return f"Error: Directorio '{path}' no encontrado."