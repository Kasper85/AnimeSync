import logging

async def obtener_link_mp4_pixeldrain(url: str, session: object = None) -> str:
    """
    Convierte un enlace de PixelDrain en un enlace directo de descarga.
    Ejemplo entrada: https://pixeldrain.com/u/Tag7cP4N
    Ejemplo salida: https://pixeldrain.com/api/file/Tag7cP4N
    """
    try:
        # Extraer el ID del archivo
        file_id = url.rstrip('/').split('/')[-1]
        
        # El enlace directo es simplemente agregando el ID a la ruta de la API
        direct_url = f"https://pixeldrain.com/api/file/{file_id}"
        
        logging.info(f"[PixelDrain] Enlace directo resuelto: {direct_url}")
        return direct_url
    except Exception as e:
        logging.error(f"[PixelDrain] Error resolviendo URL {url}: {e}")
        return None
