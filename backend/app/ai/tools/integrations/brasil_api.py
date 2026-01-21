"""
Brasil API - APIs públicas brasileiras.
Docs: https://brasilapi.com.br/docs
"""

import logging
import httpx
from datetime import datetime
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

BASE_URL = "https://brasilapi.com.br/api"


class BrasilAPITools:
    """Tools para consultas em APIs brasileiras."""

    def get_tools(self) -> list:
        return [
            self._consultar_cep,
            self._consultar_fipe,
            self._listar_bancos,
            self._consultar_banco,
            self._consultar_clima,
            self._listar_feriados,
            self._consultar_taxas,
        ]

    @tool
    def _consultar_cep(cep: str) -> str:
        """
        Consulta endereço completo por CEP.
        
        Args:
            cep: CEP (com ou sem hífen)
        """
        try:
            cep_limpo = cep.replace("-", "").replace(".", "").strip()
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{BASE_URL}/cep/v2/{cep_limpo}")
                r.raise_for_status()
                data = r.json()
            
            return (
                f"CEP: {data.get('cep')}\n"
                f"Rua: {data.get('street', 'N/A')}\n"
                f"Bairro: {data.get('neighborhood', 'N/A')}\n"
                f"Cidade: {data.get('city')} - {data.get('state')}\n"
                f"Coordenadas: {data.get('location', {}).get('coordinates', {}).get('latitude', 'N/A')}, "
                f"{data.get('location', {}).get('coordinates', {}).get('longitude', 'N/A')}"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"CEP {cep} não encontrado."
            return f"Erro ao consultar CEP: {e}"
        except Exception as e:
            logger.error(f"[BRASIL_API] Erro CEP: {e}")
            return f"Erro: {str(e)}"

    @tool
    def _consultar_fipe(tipo: str, marca: str, modelo: str = "", ano: str = "") -> str:
        """
        Consulta preço de veículo na Tabela FIPE.
        
        Args:
            tipo: Tipo do veículo (carros, motos, caminhoes)
            marca: Nome da marca (ex: Toyota, Honda, Scania)
            modelo: Nome do modelo (opcional, para busca específica)
            ano: Ano do veículo (opcional)
        """
        try:
            with httpx.Client(timeout=15) as client:
                # Buscar marcas
                r = client.get(f"{BASE_URL}/fipe/marcas/v1/{tipo}")
                r.raise_for_status()
                marcas = r.json()
                
                # Encontrar marca
                marca_lower = marca.lower()
                marca_encontrada = next((m for m in marcas if marca_lower in m['nome'].lower()), None)
                
                if not marca_encontrada:
                    marcas_disponiveis = ", ".join([m['nome'] for m in marcas[:10]])
                    return f"Marca '{marca}' não encontrada. Marcas disponíveis: {marcas_disponiveis}..."
                
                # Se não especificou modelo, listar modelos
                if not modelo:
                    return f"Marca {marca_encontrada['nome']} encontrada (código: {marca_encontrada['valor']}). Por favor, especifique o modelo."
                
                return f"Consulta FIPE: {marca_encontrada['nome']} - Para consulta completa, acesse brasilapi.com.br"
        except Exception as e:
            logger.error(f"[BRASIL_API] Erro FIPE: {e}")
            return f"Erro ao consultar FIPE: {str(e)}"

    @tool
    def _listar_bancos() -> str:
        """Lista os principais bancos brasileiros com seus códigos."""
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{BASE_URL}/banks/v1")
                r.raise_for_status()
                bancos = r.json()
            
            # Principais bancos
            principais = ["Banco do Brasil", "Itaú", "Bradesco", "Caixa", "Santander", "Nubank", "Inter", "C6"]
            resultado = ["Principais bancos brasileiros:"]
            
            for banco in bancos:
                nome = banco.get('name', '')
                if any(p.lower() in nome.lower() for p in principais):
                    resultado.append(f"- {banco.get('code', 'N/A')}: {nome}")
            
            return "\n".join(resultado[:15])
        except Exception as e:
            logger.error(f"[BRASIL_API] Erro bancos: {e}")
            return f"Erro: {str(e)}"

    @tool
    def _consultar_banco(codigo: str) -> str:
        """
        Consulta informações de um banco pelo código.
        
        Args:
            codigo: Código do banco (ex: 260 para Nubank, 077 para Inter)
        """
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{BASE_URL}/banks/v1/{codigo}")
                r.raise_for_status()
                banco = r.json()
            
            return (
                f"Código: {banco.get('code')}\n"
                f"Nome: {banco.get('fullName', banco.get('name'))}\n"
                f"ISPB: {banco.get('ispb', 'N/A')}"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"Banco com código {codigo} não encontrado."
            return f"Erro: {e}"
        except Exception as e:
            logger.error(f"[BRASIL_API] Erro banco: {e}")
            return f"Erro: {str(e)}"

    @tool
    def _consultar_clima(cidade: str) -> str:
        """
        Consulta previsão do tempo para uma cidade brasileira.
        
        Args:
            cidade: Nome da cidade (ex: Cuiaba, Sao Paulo)
        """
        try:
            with httpx.Client(timeout=10) as client:
                # Buscar cidade
                r = client.get(f"{BASE_URL}/cptec/v1/cidade/{cidade}")
                r.raise_for_status()
                cidades = r.json()
                
                if not cidades:
                    return f"Cidade '{cidade}' não encontrada."
                
                cidade_info = cidades[0]
                codigo = cidade_info['id']
                
                # Buscar previsão
                r2 = client.get(f"{BASE_URL}/cptec/v1/clima/previsao/{codigo}")
                r2.raise_for_status()
                clima = r2.json()
            
            previsao = clima.get('clima', [{}])[0] if clima.get('clima') else {}
            
            return (
                f"Clima em {clima.get('cidade', cidade)} - {clima.get('estado', '')}:\n"
                f"Condição: {previsao.get('condicao_desc', 'N/A')}\n"
                f"Temperatura: {previsao.get('min', 'N/A')}°C - {previsao.get('max', 'N/A')}°C\n"
                f"Índice UV: {previsao.get('indice_uv', 'N/A')}"
            )
        except Exception as e:
            logger.error(f"[BRASIL_API] Erro clima: {e}")
            return f"Erro ao consultar clima: {str(e)}"

    @tool
    def _listar_feriados(ano: int = None) -> str:
        """
        Lista feriados nacionais de um ano.
        
        Args:
            ano: Ano para consulta (padrão: ano atual)
        """
        try:
            ano = ano or datetime.now().year
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{BASE_URL}/feriados/v1/{ano}")
                r.raise_for_status()
                feriados = r.json()
            
            resultado = [f"Feriados nacionais de {ano}:"]
            for f in feriados:
                data = datetime.strptime(f['date'], "%Y-%m-%d").strftime("%d/%m")
                resultado.append(f"- {data}: {f['name']}")
            
            return "\n".join(resultado)
        except Exception as e:
            logger.error(f"[BRASIL_API] Erro feriados: {e}")
            return f"Erro: {str(e)}"

    @tool
    def _consultar_taxas() -> str:
        """Consulta taxas e indicadores econômicos (Selic, CDI, IPCA)."""
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{BASE_URL}/taxas/v1")
                r.raise_for_status()
                taxas = r.json()
            
            resultado = ["Taxas e indicadores econômicos atuais:"]
            for taxa in taxas:
                resultado.append(f"- {taxa['nome']}: {taxa['valor']}%")
            
            return "\n".join(resultado)
        except Exception as e:
            logger.error(f"[BRASIL_API] Erro taxas: {e}")
            return f"Erro: {str(e)}"


brasil_api_tools = BrasilAPITools()
