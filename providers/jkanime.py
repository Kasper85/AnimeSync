from typing import List, Optional
import re
import ssl
import logging
import urllib.request
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseAnimeProvider
from utils.network import resolver_ip_dominio

class JKAnimeProvider(BaseAnimeProvider):
    name = "JKAnime"
    domain = "jkanime.net"
    base_url = "https://jkanime.net"
    priority_servers = ["Mediafire", "UpnShare", "YourUpload", "Mega", "Streamwish", "VOE", "Mp4upload", "Vidhide"]
    supports_dub = True

    @classmethod
    def extract_episode_info(cls, url: str) -> Optional[dict]:
        """Detecta si la URL es un episodio de JKAnime: https://jkanime.net/naruto/1/"""
        match = re.search(r'jkanime\.net/([\w-]+)/(\d+)/?$', url)
        if match:
             return {"ep_num": int(match.group(2)), "serie": match.group(1)}
        return None

    def _fetch_html_con_bypass(self, url: str) -> str:
        """Hace una petición HTTP usando DNS bypass (Google DoH) y envía SNI manual para saltar Cloudflare."""
        import socket
        from urllib.parse import urlparse
        
        url_parsed = urlparse(url)
        path = url_parsed.path or '/'
        
        ip = resolver_ip_dominio(self.domain)
        if not ip:
            raise ConnectionError(f"No se pudo resolver IP para {self.domain}")
        
        # Crear socket y envolver con SSL forzando el SNI al dominio original
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        sock = socket.create_connection((ip, 443), timeout=10)
        ssock = ctx.wrap_socket(sock, server_hostname=self.domain)
        
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {self.domain}\r\n"
            f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
            f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        ssock.sendall(request.encode())
        
        data = b''
        while True:
            chunk = ssock.recv(4096)
            if not chunk:
                break
            data += chunk
        ssock.close()
        
        # Parse HTTP response
        parts = data.split(b'\r\n\r\n', 1)
        body = parts[1] if len(parts) > 1 else b''
        headers = parts[0]
        
        if b'Transfer-Encoding: chunked' in headers:
            decoded = b''
            remaining = body
            while remaining:
                line_end = remaining.find(b'\r\n')
                if line_end == -1: break
                size_str = remaining[:line_end].decode('ascii', errors='ignore').strip()
                if not size_str:
                    remaining = remaining[2:]
                    continue
                try:
                    chunk_size = int(size_str, 16)
                except ValueError:
                    break
                if chunk_size == 0: break
                decoded += remaining[line_end+2:line_end+2+chunk_size]
                remaining = remaining[line_end+2+chunk_size+2:]
            body = decoded
            
        return body.decode('utf-8', errors='ignore')

    async def get_episode_list(self, series_url: str, start_ep: int = 1, end_ep: int = 9999) -> List[str]:
        if not series_url.endswith('/'):
            series_url += '/'
        
        # Intentar scrapear la página de la serie para obtener el total real de episodios
        if end_ep == 9999:
            try:
                html = self._fetch_html_con_bypass(series_url)
                soup = BeautifulSoup(html, 'html.parser')
                
                cifra_max = 0
                for li in soup.find_all('li'):
                    text = li.get_text()
                    if 'Episodios:' in text:
                        match = re.search(r'\d+', text)
                        if match:
                            cifra_max = int(match.group())
                            break
                
                if cifra_max > 0:
                    end_ep = min(end_ep, cifra_max)
                    logging.info(f"[{self.name}] Detectados {cifra_max} episodios leyendo el texto de la página de la serie.")
                else:
                    logging.warning(f"[{self.name}] No se encontró el conteo de episodios. Usando modo dinámico.")
            except Exception as e:
                logging.warning(f"[{self.name}] Falló scraping de la serie, usando modo dinámico: {e}")
        
        urls = []
        for ep in range(start_ep, end_ep + 1):
            urls.append(urljoin(series_url, f"{ep}/"))
        return urls

    async def obtener_enlace_video(self, page, episode_url: str) -> Optional[dict]:
        await page.goto(episode_url, wait_until="domcontentloaded")
        
        try:
            # Esperar a que la página cargue
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            
            # ESTRATEGIA 1: Leer la tabla de descargas directamente del HTML
            # La tabla existe en div.download con enlaces directos a c1.jkplayers.com
            try:
                await page.wait_for_selector('div.download table', timeout=8000)
            except Exception:
                # ESTRATEGIA 2: Fallback - click en botón #dwld
                try:
                    boton_descarga = page.locator('#dwld')
                    await boton_descarga.wait_for(state="visible", timeout=8000)
                    await boton_descarga.click()
                    await page.wait_for_selector('table tbody tr', timeout=8000)
                except Exception as e:
                    logging.error(f"[{self.name}] No se encontró tabla de descargas ni botón #dwld: {e}")
                    return None
            
            # Extraer opciones de descarga de la tabla
            filas = await page.locator('table tbody tr:not(:first-child)').all()
            
            if not filas:
                filas = await page.locator('table tbody tr').all()
            
            opciones_descarga = {}
            
            for fila in filas:
                celdas = await fila.locator('td').all()
                if len(celdas) >= 4:
                    servidor = await celdas[0].inner_text()
                    try:
                        enlace = await celdas[3].locator('a').get_attribute('href')
                        if enlace:
                            opciones_descarga[servidor.strip()] = enlace
                    except Exception:
                        continue
                    
            if not opciones_descarga:
                logging.warning(f"[{self.name}] Tabla encontrada pero sin enlaces válidos.")
                return None

        except Exception as e:
            logging.error(f"[{self.name}] Falló al buscar opciones de descarga: {e}")
            return None

        # Prioridad de servidores
        for servidor_ideal in self.priority_servers:
            if servidor_ideal in opciones_descarga:
                return {"url": opciones_descarga[servidor_ideal], "server": servidor_ideal.lower()}

        servidor_fallback = list(opciones_descarga.keys())[0]
        return {"url": opciones_descarga[servidor_fallback], "server": servidor_fallback.lower()}
