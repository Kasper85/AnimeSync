"""
Módulo de configuración
=======================

Carga y valida la configuración desde el archivo .env
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

# Cargar configuración desde .env
from dotenv import load_dotenv


# Logger para este módulo
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuración de la aplicación"""
    api_id: int
    api_hash: str
    phone: str
    channel: str
    session_file: Path = Path('uploader.session')


def load_config() -> Config:
    """
    Carga la configuración desde el archivo .env
    
    Returns:
        Config: Objeto con la configuración validada
    
    Raises:
        ValueError: Si falta alguna variable requerida o tiene valores inválidos
    """
    # Cargar variables de entorno desde el .env en la raíz del proyecto
    env_path = Path(__file__).resolve().parent.parent / '.env'
    load_dotenv(env_path)
    
    # Obtener valores obligatorios
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')
    phone = os.getenv('PHONE')
    channel = os.getenv('CHANNEL')
    
    # Validar que existan
    missing = []
    if not api_id:
        missing.append('API_ID')
    if not api_hash:
        missing.append('API_HASH')
    if not phone:
        missing.append('PHONE')
    if not channel:
        missing.append('CHANNEL')
    
    if missing:
        raise ValueError(
            f"Faltan variables requeridas en .env: {', '.join(missing)}\n"
            f"Copia .env.example como .env y completa los valores."
        )
    
    # Convertir API_ID a entero
    try:
        api_id_int = int(api_id)
    except ValueError:
        raise ValueError(f"API_ID debe ser un número, recibido: {api_id}")
    
    logger.info("✓ Configuración cargada correctamente")
    
    return Config(
        api_id=api_id_int,
        api_hash=api_hash,
        phone=phone,
        channel=channel,
    )

