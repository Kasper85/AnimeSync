# fast_uploader.py
"""
FastTelethon - Subida PARALELA REAL
Implementación manual de concurrencia inyectando chunks al socket.
"""

import asyncio
import math
import os
import logging
from pathlib import Path
from typing import Optional, Callable

from telethon import TelegramClient
from telethon.tl.types import Message, InputFileBig, InputFile
from telethon.tl.functions.upload import SaveBigFilePartRequest, SaveFilePartRequest

logger = logging.getLogger(__name__)

async def upload_file_parallel(
    client: TelegramClient,
    file_path: str,
    part_size_kb: int = 512,
    max_workers: int = 12,
    progress_callback: Optional[Callable] = None
):
    """Subida verdaderamente paralela encolando múltiples peticiones al socket."""
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    part_size = int(part_size_kb * 1024)
    total_parts = math.ceil(file_size / part_size)
    
    is_big = file_size > 10 * 1024 * 1024
    file_id = int.from_bytes(os.urandom(8), "big", signed=True)
    
    queue = asyncio.Queue()
    
    # Productor: lee los bytes del archivo y llena la cola
    async def file_reader():
        with open(file_path, "rb") as f:
            for i in range(total_parts):
                chunk = f.read(part_size)
                await queue.put((i, chunk))
        # Enviar marcadores de fin para cada hilo
        for _ in range(max_workers):
            await queue.put(None)
            
    uploaded_bytes = [0]
    
    # Consumidor: saca pedazos y dispara la petición asíncrona a Telethon
    async def worker():
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            
            part_idx, chunk = item
            
            if is_big:
                req = SaveBigFilePartRequest(
                    file_id=file_id,
                    file_part=part_idx,
                    file_total_parts=total_parts,
                    bytes=chunk
                )
            else:
                req = SaveFilePartRequest(
                    file_id=file_id,
                    file_part=part_idx,
                    bytes=chunk
                )
            
            # Subir con hasta 5 reintentos en caso de timeout
            for attempt in range(5):
                try:
                    await client(req)
                    break
                except Exception as e:
                    if attempt == 4:
                        logger.error(f"Fallo extremo al subir parte {part_idx}: {e}")
                        raise
                    await asyncio.sleep(1)
            
            uploaded_bytes[0] += len(chunk)
            if progress_callback:
                progress_callback(uploaded_bytes[0], file_size)
                
            queue.task_done()
            
    # Arrancamos simultáneamente la lectura y los envíos
    reader_task = asyncio.create_task(file_reader())
    workers = [asyncio.create_task(worker()) for _ in range(max_workers)]
    
    # Esperamos a que todos terminen
    await asyncio.gather(reader_task, *workers)
    
    # Devolvemos el objeto virtual final ensamblado
    if is_big:
        return InputFileBig(id=file_id, parts=total_parts, name=file_name)
    else:
        return InputFile(id=file_id, parts=total_parts, name=file_name, md5_checksum="")


async def fast_upload_file(
    client: TelegramClient,
    file_path: Path,
    entity,
    caption: str = "",
    progress_callback: Optional[Callable] = None,
    part_size_kb: int = 512,
    max_workers: int = 12,
    attributes=None,
    thumb=None,
) -> Message:
    
    file_size = file_path.stat().st_size
    file_name = file_path.name
    
    logger.info(f"🚀 Multi-Worker Upload iniciado: {file_name} ({file_size/(1024*1024):.1f} MB)")
    
    # Paso 1: Subida bruta y paralela de archivos binarios al servidor (MAX SPEED)
    uploaded_file = await upload_file_parallel(
        client=client,
        file_path=str(file_path),
        part_size_kb=part_size_kb,
        max_workers=max_workers,
        progress_callback=progress_callback
    )
    
    logger.info("✅ Upload binario finalizado. Enviando al chat...")
    
    # Paso 2: Vincular el archivo subido como mensaje (instantáneo)
    uploaded_message = await client.send_file(
        entity=entity,
        file=uploaded_file,
        caption=caption,
        attributes=attributes,
        thumb=thumb,
        force_document=False,
        allow_cache=False,
    )
    
    return uploaded_message