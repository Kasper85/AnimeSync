from abc import ABC, abstractmethod
from typing import List, Optional

class BaseAnimeProvider(ABC):
    # Atributos obligatorios para la clase hija
    name: str = ""
    domain: str = ""
    base_url: str = ""
    priority_servers: List[str] = ["Mediafire", "Mega", "Streamwish"]
    supports_dub: bool = False

    @abstractmethod
    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999) -> List[str]:
        """
        Dada la URL de la serie y rangos, devuelve una lista secuencial de URLs de los episodios.
        """
        pass

    @abstractmethod
    async def obtener_enlace_video(self, page, episode_url: str) -> Optional[dict]:
        """
        Navega al episodio usando Playwright y extrae el enlace web de Mediafire o Mega (fallback).
        Retorna un diccionario: {"url": "enlace", "server": "mediafire|mega"}
        """
        pass

    @classmethod
    def is_supported(cls, url: str) -> bool:
        """Verifica si este provider puede manejar la URL origen dada."""
        return cls.domain in url

    @classmethod
    def extract_episode_info(cls, url: str) -> Optional[dict]:
        """
        Analiza la URL y determina si corresponde a un episodio individual en vez de la serie completa.
        Debe devolver un diccionario con {'ep_num': int, ...} si es un episodio, o None si es una serie completa.
        """
        return None
