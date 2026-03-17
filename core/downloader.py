import os
import asyncio
import logging
import aiofiles

async def descargar_video(url_directa, nombre_carpeta, nombre_archivo, session, id_hilo=0, headers_extra=None):
    ruta_actual = os.getcwd()
    ruta_destino = os.path.join(ruta_actual, nombre_carpeta)
    os.makedirs(ruta_destino, exist_ok=True)
    ruta_completa = os.path.join(ruta_destino, nombre_archivo)
    
    headers = headers_extra.copy() if headers_extra else {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "video/mp4,video/x-m4v,video/*;q=0.9,application/mp4;q=0.8,*/*;q=0.7",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://latanime.org/"
    }
    modo_apertura = 'wb'
    tamanio_existente = 0

    if os.path.exists(ruta_completa):
        tamanio_existente = os.path.getsize(ruta_completa)
        headers['Range'] = f'bytes={tamanio_existente}-'
        modo_apertura = 'ab'

    try:
        async with session.get(url_directa, headers=headers, ssl=False) as respuesta:
            respuesta.raise_for_status()

            # 206 Partial Content significa que el servidor aceptó el Range
            es_reanudable = respuesta.status == 206
            if not es_reanudable and tamanio_existente > 0:
                modo_apertura = 'wb'
                tamanio_existente = 0

            # NUEVO: Implementación de I/O Asíncrono no-bloqueante para no atascar a los workers
            async with aiofiles.open(ruta_completa, modo_apertura) as archivo:
                bytes_descargados_sesion = 0
                # Leemos chunks grandes de 1MB para no ahogar el Event Loop
                async for bloque in respuesta.content.iter_chunked(1048576):
                    await archivo.write(bloque)
                    bytes_descargados_sesion += len(bloque)
                    # Yield para permitir a otras tareas (workers) avanzar en el loop
                    await asyncio.sleep(0)
                        
            return True, bytes_descargados_sesion

    except Exception as e:
        logging.error(f"[{nombre_archivo}] Error en descarga: {type(e).__name__} - {str(e)}")
        return False, 0