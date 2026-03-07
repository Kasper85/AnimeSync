import os
import aiohttp
import asyncio
import logging
import aiofiles

async def descargar_video(url_directa, nombre_carpeta, nombre_archivo, session, id_hilo=0):
    ruta_actual = os.getcwd()
    ruta_destino = os.path.join(ruta_actual, nombre_carpeta)
    os.makedirs(ruta_destino, exist_ok=True)
    ruta_completa = os.path.join(ruta_destino, nombre_archivo)
    
    headers = {}
    modo_apertura = 'wb'
    tamanio_existente = 0

    if os.path.exists(ruta_completa):
        tamanio_existente = os.path.getsize(ruta_completa)
        headers['Range'] = f'bytes={tamanio_existente}-'
        modo_apertura = 'ab'

    try:
        async with session.get(url_directa, headers=headers) as respuesta:
            respuesta.raise_for_status()

            # 206 Partial Content significa que el servidor aceptó el Range
            es_reanudable = respuesta.status == 206
            if not es_reanudable and tamanio_existente > 0:
                modo_apertura = 'wb'
                tamanio_existente = 0

            # contentLength a veces puede no estar, asumimos 0 si falta para evitar errores
            peso_descargado = int(respuesta.headers.get('content-length', 0))
            peso_total = peso_descargado + tamanio_existente
            
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