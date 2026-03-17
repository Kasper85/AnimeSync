import logging

# ==========================================
# CONSTANTES GLOBALES DE CONFIGURACIÓN
# ==========================================

# Tamaño mínimo para considerar un archivo de video como válido (evita re-descargar archivos corruptos)
TAMANIO_MINIMO_VIDEO_MB = 50.0




def setup_logging():
    """Configura el logger global con handlers para consola y archivo."""
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)  # Solo mostrar advertencias y errores por defecto

    # Evitar duplicar handlers si se llama más de una vez
    if logger.hasHandlers():
        logger.handlers.clear()

    # Formato más limpio
    fmt = logging.Formatter("%(levelname)s: %(message)s")

    # Handler de consola
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)


