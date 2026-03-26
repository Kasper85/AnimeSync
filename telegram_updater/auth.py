"""
Módulo de autenticación
======================

Manejo de login interactivo y gestión de sesiones con Telethon
"""

import asyncio
import logging
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
)

from config import Config


# Logger para este módulo
logger = logging.getLogger(__name__)


async def login_interactive(client: TelegramClient, phone: str) -> bool:
    """
    Maneja el login interactivo del usuario
    
    Args:
        client: Instancia de TelegramClient
        phone: Número de teléfono del usuario
    
    Returns:
        bool: True si el login fue exitoso
    """
    logger.info("Iniciando sesión interactiva...")
    
    try:
        # En Telethon 1.42+, usamos el flujo completo con start()
        # Primero desconectamos el cliente si está conectado
        if client.is_connected():
            await client.disconnect()
        
        # Usar client.start que maneja el flujo completo
        # El parámetro force_sms=True asegura que se envíe nuevo código
        await client.start(phone=phone, force_sms=True)
        
        # Verificar que está conectado y autorizado
        if await client.is_user_authorized():
            logger.info("✓ Sesión iniciada correctamente")
            return True
        else:
            logger.error("✗ No se pudo autorizar la sesión")
            return False
            
    except SessionPasswordNeededError:
        # Usuario tiene 2FA, necesitamos el phone_code_hash
        logger.info("Tu cuenta tiene verificación en dos pasos (2FA)")
        
        # Desconectar y reintentar con 2FA
        if client.is_connected():
            await client.disconnect()
        
        # Usar start() con password
        await client.start(phone=phone, password=input("Ingresa tu contraseña de Telegram: "))
        
        if await client.is_user_authorized():
            logger.info("✓ Sesión iniciada con 2FA")
            return True
        else:
            logger.error("✗ Contraseña incorrecta")
            return False
            
    except Exception as e:
        logger.error(f"Error durante el login: {e}")
        return False
    
    return False


async def is_valid_session_file(session_file: Path) -> bool:
    """
    Verifica si el archivo de sesión es un SQLite válido con la tabla sessions.
    
    Args:
        session_file: Ruta al archivo de sesión
    
    Returns:
        bool: True si el archivo es válido, False si está corrupto o vacío
    """
    if not session_file.exists():
        return False
    
    # Verificar que el archivo no esté vacío
    if session_file.stat().st_size == 0:
        logger.warning("Archivo de sesión vacío, eliminando...")
        try:
            session_file.unlink()
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo vacío: {e}")
        return False
    
    # Verificar que sea un SQLite válido
    try:
        import sqlite3
        conn = sqlite3.connect(str(session_file))
        cursor = conn.cursor()
        # Verificar que existan las tablas necesarias
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if 'sessions' not in tables:
            logger.warning("Archivo de sesión corrupto: falta tabla 'sessions'")
            try:
                session_file.unlink()
            except Exception as e:
                logger.warning(f"No se pudo eliminar archivo corrupto: {e}")
            return False
        
        return True
    except Exception as e:
        logger.warning(f"Error al validar sesión: {e}")
        try:
            session_file.unlink()
        except:
            pass
        return False


async def ensure_session(client: TelegramClient, config: Config) -> bool:
    """
    Asegura que exista una sesión válida. Si ya existe una sesión,
    intenta usarla. Si no es válida, solicita nuevo código.
    
    Args:
        client: Instancia de TelegramClient
        config: Objeto de configuración
    
    Returns:
        bool: True si la sesión es válida
    """
    # Si hay un archivo de sesión, verificar si ya estamos autorizados
    if config.session_file.exists():
        logger.info("Sesión existente detectada, intentando conectar...")
        try:
            await client.connect()
            if await client.is_user_authorized():
                logger.info("✓ Sesión existente válida")
                return True
            else:
                logger.info("Sesión existente no autorizada. Se solicitará nuevo inicio de sesión.")
                # No eliminamos el archivo porque SQLiteSession lo tiene abierto.
                # await client.start() en login_interactive sobrescribirá la autorización.
        except Exception as e:
            logger.warning(f"Error al conectar con sesión existente: {e}")
            # Si hay error grave, cerramos la conexión para que login_interactive intente de nuevo
            if client.is_connected():
                await client.disconnect()

    # Solicitar nuevo código
    return await login_interactive(client, config.phone)


async def create_client(config: Config) -> TelegramClient:
    """
    Crea una instancia de TelegramClient con la configuración dada
    
    Args:
        config: Objeto de configuración
    
    Returns:
        TelegramClient: Cliente configurado
    """
    client = TelegramClient(
        str(config.session_file),
        config.api_id,
        config.api_hash,
    )
    
    logger.info("Cliente Telegram creado")
    return client


async def disconnect_client(client: TelegramClient) -> None:
    """
    Desconecta el cliente de manera segura
    
    Args:
        client: Cliente a desconectar
    """
    if client is None:
        return
    try:
        if client.is_connected():
            await client.disconnect()
            logger.info("Cliente desconectado")
    except asyncio.CancelledError:
        # Ignorar cancelaciones durante desconexión
        logger.debug("Desconexión cancelada")
    except Exception as e:
        logger.warning(f"Error al desconectar: {e}")