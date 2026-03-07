import importlib
from pathlib import Path
from .base import BaseAnimeProvider

PROVIDERS = {}

def get_provider_for_url(url: str) -> BaseAnimeProvider:
    for provider_class in PROVIDERS.values():
        if provider_class.is_supported(url):
            return provider_class()
    raise ValueError(f"No se encontró un provider compatible para la URL: {url}")

# Lógica de auto-descubrimiento
_current_dir = Path(__file__).parent
for file_path in _current_dir.glob("*.py"):
    if file_path.stem in ("__init__", "base"):
        continue

    # Importar el módulo dinámicamente
    module_name = f"providers.{file_path.stem}"
    module = importlib.import_module(module_name)

    # Buscar clases hijas de BaseAnimeProvider
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, BaseAnimeProvider) and attr is not BaseAnimeProvider:
            PROVIDERS[attr.name] = attr
