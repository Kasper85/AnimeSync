"""
Módulo de upload
================

Lógica para subir archivos a Telegram con manejo de errores robusto
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import Message, DocumentAttributeVideo, DocumentAttributeFilename
if __package__ is None or __package__ == '':
    from fast_uploader import fast_upload_file
    from files import FileInfo
else:
    from .fast_uploader import fast_upload_file
    from .files import FileInfo

try:
    import cv2
except ImportError:
    cv2 = None


# Logger para este módulo
logger = logging.getLogger(__name__)


# Límite de 4 GB para cuentas Premium
MAX_FILE_SIZE_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB


@dataclass
class UploadResult:
    """Resultado de intentar subir un archivo"""
    success: bool
    message: str
    link: Optional[str] = None


def get_video_metadata(file_path):
    """Extrae atributos de video y genera un thumbnail usando cv2."""
    file_path_str = str(file_path)
    if not file_path_str.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
        return None, None
        
    # Fallback to prevent videos from being uploaded as generic files
    default_attr = [
        DocumentAttributeVideo(duration=0, w=0, h=0, supports_streaming=True),
        DocumentAttributeFilename(file_name=os.path.basename(file_path_str))
    ]

    if not cv2:
        return default_attr, None
        
    try:
        cap = cv2.VideoCapture(file_path_str)
        if not cap.isOpened():
            return default_attr, None
            
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = int(frame_count / fps) if fps > 0 else 0
        
        # Tomar un frame a 10% del video o maximo al frame 120
        target_frame = max(0, min(120, int(frame_count * 0.1)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        
        thumb_path = None
        if ret and frame is not None:
            thumb_path = file_path_str + ".thumb.jpg"
            # Redimensionar (Telegram sugiere 320x320 max para thumbs)
            if width > 320 or height > 320:
                scale = 320.0 / max(width, height)
                new_w = int(width * scale)
                new_h = int(height * scale)
                frame = cv2.resize(frame, (new_w, new_h))
            cv2.imwrite(thumb_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
        cap.release()

        attributes = [
            DocumentAttributeVideo(duration=duration, w=width, h=height, supports_streaming=True),
            DocumentAttributeFilename(file_name=os.path.basename(file_path_str))
        ]
        return attributes, thumb_path
        
    except Exception as e:
        logger.warning(f"No se pudo extraer metadata del video {file_path}: {e}")
        return default_attr, None


async def upload_single_file(
    client: TelegramClient,
    channel_entity,
    file_info: FileInfo,
    max_retries: int = 3,
) -> UploadResult:
    file_path = file_info.path
    file_name = file_info.name
    file_size = file_info.size
    file_size_mb = file_info.size_mb

    if file_size > MAX_FILE_SIZE_BYTES:
        logger.warning(f"⏭️ Saltando {file_name}: excede 4 GB")
        return UploadResult(False, "Excede 4 GB")

    for attempt in range(max_retries):
        try:
            logger.info(f"Subiendo: {file_name} ({file_size_mb:.1f} MB)...")
            
            attributes, thumb_path = get_video_metadata(file_path)

            # === FAST UPLOAD REAL (paralelo) ===
            message = await fast_upload_file(
                client=client,
                file_path=file_path,
                entity=channel_entity,
                caption=file_name,         # <- Usar el nombre del archivo como descripción
                attributes=attributes,
                thumb=thumb_path,
                part_size_kb=512,          # <- Límite duro de Telegram
                max_workers=12,            # <- Empujando la concurrencia al tope seguro
            )
            
            # Limpiar thumbnail temporal
            if thumb_path and os.path.exists(thumb_path):
                try: os.unlink(thumb_path)
                except Exception: pass

            # Obtener link...
            link = None
            if hasattr(channel_entity, 'username') and channel_entity.username:
                link = f"https://t.me/{channel_entity.username}/{message.id}"

            return UploadResult(True, "Subido correctamente", link)

        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error en intento {attempt+1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)

    return UploadResult(False, "Máximo reintentos alcanzado")


async def get_channel_entity(client: TelegramClient, channel_str: str):
    """
    Obtiene la entidad del canal (puede ser username o ID numérico)
    
    Args:
        client: Instancia de TelegramClient
        channel_str: Username (sin @) o ID (ej: -1001234567890)
    
    Returns:
        Entity del canal
    
    Raises:
        ValueError: Si no se puede encontrar el canal
    """
    logger.info(f"Buscando canal: {channel_str}")
    
    try:
        # Determinar si es ID numérico o username
        if channel_str.startswith('-100') or channel_str.isdigit():
            # Es un ID numérico
            entity = await client.get_entity(int(channel_str))
        else:
            # Es un username
            entity = await client.get_entity(f"@{channel_str}")
        
        logger.info(f"✓ Canal encontrado: {entity.title}")
        return entity
        
    except Exception as e:
        raise ValueError(
            f"No se pudo encontrar el canal '{channel_str}'.\n"
            f"Asegúrate de que:\n"
            f"  - El canal existe y tu cuenta es administrador\n"
            f"  - El username es correcto (sin @)\n"
            f"  - El ID es correcto (-100...)\n"
            f"Error: {e}"
        )


@dataclass
class UploadStats:
    """Estadísticas de la sesión de upload"""
    uploaded: int
    skipped: int
    failed: int
    total_time: float
    links: list[str]


async def upload_files(
    client: TelegramClient,
    channel_entity,
    files: list[FileInfo],
) -> UploadStats:
    """
    Sube una lista de archivos secuencialmente
    
    Args:
        client: Instancia de TelegramClient
        channel_entity: Entidad del canal
        files: Lista de archivos a subir
    
    Returns:
        UploadStats: Estadísticas del proceso
    """
    import time
    
    start_time = time.time()
    
    # Resultados
    uploaded = 0
    skipped = 0
    failed = 0
    links = []
    
    # Subir secuencialmente (no paralelo para evitar bans)
    for i, file_info in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Procesando: {file_info.name}")
        
        result = await upload_single_file(
            client,
            channel_entity,
            file_info,
        )
        
        if result.success:
            uploaded += 1
            if result.link:
                links.append(result.link)
        elif result.message == "Excede 4 GB":
            skipped += 1
        else:
            failed += 1
        
        # Pequeña pausa entre archivos para evitar flood
        await asyncio.sleep(1)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    return UploadStats(
        uploaded=uploaded,
        skipped=skipped,
        failed=failed,
        total_time=total_time,
        links=links,
    )

