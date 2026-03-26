"""
Módulo de manejo de archivos
============================

Utilidades para obtener, filtrar y mostrar archivos locales
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Logger para este módulo
logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Información de un archivo para subir"""
    path: Path
    name: str
    size: int  # bytes
    size_mb: float
    modified: float  # timestamp


def get_files_in_directory(
    directory: Path,
    extensions: Optional[list] = None,
    sort_by: str = 'name',
    max_files: Optional[int] = None,
) -> list[FileInfo]:
    """
    Obtiene lista de archivos en un directorio (no recursivo, sin ocultos)
    
    Args:
        directory: Ruta al directorio
        extensions: Lista de extensiones a filtrar (ej: ['.mp4', '.mkv'])
        sort_by: 'name', 'size_asc', 'size_desc', 'date'
        max_files: Límite máximo de archivos
    
    Returns:
        Lista de FileInfo con información de cada archivo
    """
    files = []
    
    # Obtener archivos del directorio (solo nivel superior)
    for item in directory.iterdir():
        # Ignorar archivos ocultos (empieza con .)
        if item.name.startswith('.'):
            continue
        
        # Ignorar carpetas, solo archivos
        if not item.is_file():
            continue
        
        # Filtrar por extensión si se especificó
        if extensions:
            ext = item.suffix.lower()
            if ext not in extensions:
                continue
        
        # Obtener información del archivo
        try:
            stat = item.stat()
            files.append(FileInfo(
                path=item,
                name=item.name,
                size=stat.st_size,
                size_mb=stat.st_size / (1024 * 1024),
                modified=stat.st_mtime,
            ))
        except Exception as e:
            logger.warning(f"No se pudo obtener info de {item.name}: {e}")
            continue
    
    # Ordenar archivos
    if sort_by == 'name':
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower()
                    for text in re.split(r'(\d+)', s)]
        files.sort(key=lambda x: natural_sort_key(x.name))
    elif sort_by == 'size_asc':
        files.sort(key=lambda x: x.size)
    elif sort_by == 'size_desc':
        files.sort(key=lambda x: x.size, reverse=True)
    elif sort_by == 'date':
        files.sort(key=lambda x: x.modified, reverse=True)
    
    # Aplicar límite
    if max_files:
        files = files[:max_files]
    
    return files


def print_files_summary(files: list[FileInfo]) -> None:
    """
    Muestra resumen de archivos a subir
    
    Args:
        files: Lista de archivos
    """
    total_size_mb = sum(f.size_mb for f in files)
    
    print(f"\n{'='*60}")
    print(f"📁 ARCHIVOS A SUBIR: {len(files)}")
    print(f"{'='*60}")
    print(f"{'Nombre':<45} {'Tamaño':>10}")
    print(f"{'-'*60}")
    
    for f in files:
        name = f.name[:42] + '...' if len(f.name) > 45 else f.name
        print(f"{name:<45} {f.size_mb:>8.1f} MB")
    
    print(f"{'-'*60}")
    print(f"{'TOTAL:':<45} {total_size_mb:>8.1f} MB")
    print(f"{'='*60}\n")


def parse_extensions(input_str: str) -> Optional[list[str]]:
    """
    Parsea string de extensiones separadas por coma o espacio
    
    Args:
        input_str: String con extensiones (ej: ".mp4 .mkv .zip" o ".mp4,.mkv")
    
    Returns:
        Lista de extensiones en minúsculas, o None si está vacío
    """
    if not input_str or not input_str.strip():
        return None
    
    # Parsear extensiones
    ext_list = input_str.replace(',', ' ').split()
    
    # Normalizar: asegurar que empiezan con punto
    extensions = []
    for ext in ext_list:
        ext = ext.strip().lower()
        if ext:
            if not ext.startswith('.'):
                ext = f'.{ext}'
            extensions.append(ext)
    
    return extensions if extensions else None


def select_sort_option() -> str:
    """
    Solicita al usuario el criterio de ordenamiento
    
    Returns:
        str: sorting 'name', 'size_asc', 'size_desc', o 'date'
    """
    print("\nOrdenar por:")
    print("  1. Alfabético (default)")
    print("  2. Tamaño ascendente")
    print("  3. Tamaño descendente")
    print("  4. Fecha de modificación")
    
    sort_option = input("Selecciona [1-4]: ").strip()
    
    sort_by_map = {
        '1': 'name',
        '2': 'size_asc',
        '3': 'size_desc',
        '4': 'date',
    }
    
    return sort_by_map.get(sort_option, 'name')


def get_max_files_input() -> Optional[int]:
    """
    Solicita al usuario el límite máximo de archivos
    
    Returns:
        int: Límite, o None si no se especifica
    """
    max_files_input = input(
        "\nLímite máximo de archivos por ejecución? [ENTER = ilimitado, ej: 10]: "
    ).strip()
    
    if not max_files_input:
        return None
    
    try:
        max_files = int(max_files_input)
        if max_files > 0:
            return max_files
    except ValueError:
        pass
    
    print("✗ Valor inválido, se usará ilimitado")
    return None


def validate_directory(path_str: str) -> Optional[Path]:
    """
    Valida que la ruta sea un directorio válido
    
    Args:
        path_str: Ruta ingresada por el usuario
    
    Returns:
        Path: Si es válido, None si no lo es
    """
    # Limpiar comillas
    path_str = path_str.strip('"').strip("'")
    
    path = Path(path_str)
    
    if not path.exists():
        print("✗ La ruta no existe. Intenta de nuevo.")
        return None
    
    if not path.is_dir():
        print("✗ La ruta no es una carpeta. Intenta de nuevo.")
        return None
    
    return path