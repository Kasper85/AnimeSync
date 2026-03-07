import logging

# Configuración básica del logger compartida por toda la aplicación
def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
