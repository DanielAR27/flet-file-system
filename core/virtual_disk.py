import os

# Obtener el directorio base de flet-file-system independiente desde dónde se ejecute python
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DISK_PATH = os.path.join(BASE_DIR, "file-system", "disk.bin")

class VirtualDisk:
    def __init__(self):
        self.disk_path = DEFAULT_DISK_PATH
        self.num_sectors = 0
        self.sector_size = 0
        self.fat = []  # File Allocation Table: -1 = libre, -2 = fin de archivo (EOF), >= 0 = puntero al siguiente sector
        self.is_initialized = False

    def create_disk(self, num_sectors: int, sector_size: int, disk_path: str = None):
        """
        Crea un archivo físico lleno de ceros para simular el disco virtual.
        Inicializa la FAT en memoria.
        """
        if disk_path is None:
            disk_path = DEFAULT_DISK_PATH
            
        self.disk_path = disk_path
        self.num_sectors = num_sectors
        self.sector_size = sector_size
        
        # Inicializar FAT: todos los sectores están libres (-1)
        self.fat = [-1] * num_sectors
        self.is_initialized = True

        # Crear la carpeta contenedora si no existe
        target_dir = os.path.dirname(self.disk_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        # Crear el archivo físico con el tamaño correspondiente
        total_size = num_sectors * sector_size
        with open(self.disk_path, "wb") as f:
            f.write(b"\x00" * total_size)

    def load_disk(self, num_sectors: int, sector_size: int, disk_path: str = None):
        """
        Carga un disco virtual existente si ya está en el sistema de archivos de la máquina real.
        """
        if disk_path is None:
            disk_path = DEFAULT_DISK_PATH
            
        if not os.path.exists(disk_path):
            raise FileNotFoundError(f"El disco virtual en '{disk_path}' no existe.")
        
        self.disk_path = disk_path
        self.num_sectors = num_sectors
        self.sector_size = sector_size
        self.fat = [-1] * num_sectors
        self.is_initialized = True

    def read_sector(self, sector_index: int) -> bytes:
        """
        Lee los bytes de un sector específico en el disco físico.
        """
        if not self.is_initialized:
            raise ValueError("El disco virtual no ha sido inicializado.")
        if sector_index < 0 or sector_index >= self.num_sectors:
            raise IndexError("Índice de sector fuera de rango.")

        offset = sector_index * self.sector_size
        with open(self.disk_path, "rb") as f:
            f.seek(offset)
            return f.read(self.sector_size)

    def write_sector(self, sector_index: int, data: bytes):
        """
        Escribe datos en un sector específico del disco físico.
        Los datos se truncan o rellenan con ceros para ajustarse al tamaño del sector.
        """
        if not self.is_initialized:
            raise ValueError("El disco virtual no ha sido inicializado.")
        if sector_index < 0 or sector_index >= self.num_sectors:
            raise IndexError("Índice de sector fuera de rango.")

        # Ajustar tamaño de datos al tamaño del sector
        data = data[:self.sector_size]
        if len(data) < self.sector_size:
            data = data.ljust(self.sector_size, b"\x00")

        offset = sector_index * self.sector_size
        with open(self.disk_path, "r+b") as f:
            f.seek(offset)
            f.write(data)

    def find_free_sectors(self, required_sectors: int) -> list:
        """
        Implementa el algoritmo FIRST FIT para encontrar sectores libres.
        Retorna una lista de índices de sectores libres.
        Si no hay suficientes sectores libres, retorna una lista vacía.
        """
        free_indices = []
        for i in range(self.num_sectors):
            if self.fat[i] == -1:  # Sector libre
                free_indices.append(i)
                if len(free_indices) == required_sectors:
                    return free_indices
        return []  # No hay suficientes sectores libres

    def allocate_file_sectors(self, data_size_bytes: int) -> list:
        """
        Calcula cuántos sectores se necesitan, los busca mediante First Fit,
        los enlaza en la FAT y retorna la lista de sectores asignados.
        """
        if data_size_bytes == 0:
            # Los archivos vacíos ocupan al menos 1 sector
            required_sectors = 1
        else:
            required_sectors = (data_size_bytes + self.sector_size - 1) // self.sector_size

        free_sectors = self.find_free_sectors(required_sectors)
        if not free_sectors:
            return []  # Disco lleno o sin suficiente espacio continuo/disperso

        # Enlazar los sectores en la FAT (Asignación Enlazada)
        for i in range(len(free_sectors) - 1):
            current_sec = free_sectors[i]
            next_sec = free_sectors[i + 1]
            self.fat[current_sec] = next_sec
        
        # El último sector apunta a -2 (EOF)
        self.fat[free_sectors[-1]] = -2

        return free_sectors

    def free_file_sectors(self, start_sector: int):
        """
        Libera la cadena de sectores enlazados a partir de un sector inicial.
        """
        current_sector = start_sector
        while current_sector >= 0:
            next_sector = self.fat[current_sector]
            self.fat[current_sector] = -1  # Marcar como libre
            current_sector = next_sector
        
        # Si era -2 (EOF), se detiene inmediatamente.

    def get_free_sectors_count(self) -> int:
        """
        Retorna la cantidad total de sectores libres en el disco.
        """
        return self.fat.count(-1)
