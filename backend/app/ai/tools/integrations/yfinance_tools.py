"""
yFinance Tools - Dados financeiros e investimentos.
Docs: https://github.com/ranaroussi/yfinance
"""

import logging
from datetime import datetime, timedelta
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


class YFinanceTools:
    """Tools para consulta de dados financeiros e investimentos."""

    def get_tools(self) -> list:
        return [
            self._get_stock_price,
            self._get_stock_info,
            self._get_crypto_price,
            self._get_currency_rate,
            self._get_stock_history,
        ]

    @tool
    def _get_stock_price(ticker: str) -> str:
        """
        Consulta preço atual de uma ação.
        Para ações brasileiras, adicione .SA (ex: PETR4.SA, VALE3.SA).
        
        Args:
            ticker: Código da ação (ex: AAPL, PETR4.SA, ITUB4.SA)
        """
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker.upper())
            info = stock.fast_info
            
            price = info.last_price
            change = info.regular_market_change_percent if hasattr(info, 'regular_market_change_percent') else 0
            
            return f"{ticker.upper()}: R$ {price:.2f} ({change:+.2f}%)"
        except Exception as e:
            logger.error(f"[YFINANCE] Erro ao buscar {ticker}: {e}")
            return f"Erro ao buscar {ticker}: {str(e)}"

    @tool
    def _get_stock_info(ticker: str) -> str:
        """
        Informações detalhadas de uma ação (setor, P/L, dividendos, etc).
        
        Args:
            ticker: Código da ação (ex: PETR4.SA, VALE3.SA)
        """
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker.upper())
            info = stock.info
            
            details = [
                f"Empresa: {info.get('longName', ticker)}",
                f"Setor: {info.get('sector', 'N/A')}",
                f"Preço: R$ {info.get('currentPrice', 'N/A')}",
                f"P/L: {info.get('trailingPE', 'N/A')}",
                f"Dividend Yield: {info.get('dividendYield', 0) * 100:.2f}%" if info.get('dividendYield') else "Dividend Yield: N/A",
                f"52 semanas: R$ {info.get('fiftyTwoWeekLow', 'N/A')} - R$ {info.get('fiftyTwoWeekHigh', 'N/A')}",
            ]
            return "\n".join(details)
        except Exception as e:
            logger.error(f"[YFINANCE] Erro ao buscar info de {ticker}: {e}")
            return f"Erro: {str(e)}"

    @tool
    def _get_crypto_price(crypto: str) -> str:
        """
        Consulta preço de criptomoeda em USD.
        
        Args:
            crypto: Símbolo da cripto (ex: BTC, ETH, SOL)
        """
        try:
            import yfinance as yf
            ticker = f"{crypto.upper()}-USD"
            coin = yf.Ticker(ticker)
            info = coin.fast_info
            
            price = info.last_price
            return f"{crypto.upper()}: US$ {price:,.2f}"
        except Exception as e:
            logger.error(f"[YFINANCE] Erro ao buscar {crypto}: {e}")
            return f"Erro: {str(e)}"

    @tool
    def _get_currency_rate(from_currency: str, to_currency: str = "BRL") -> str:
        """
        Consulta taxa de câmbio entre moedas.
        
        Args:
            from_currency: Moeda de origem (ex: USD, EUR)
            to_currency: Moeda de destino (ex: BRL)
        """
        try:
            import yfinance as yf
            ticker = f"{from_currency.upper()}{to_currency.upper()}=X"
            rate = yf.Ticker(ticker)
            info = rate.fast_info
            
            price = info.last_price
            return f"1 {from_currency.upper()} = {price:.4f} {to_currency.upper()}"
        except Exception as e:
            logger.error(f"[YFINANCE] Erro câmbio: {e}")
            return f"Erro: {str(e)}"

    @tool
    def _get_stock_history(ticker: str, period: str = "1mo") -> str:
        """
        Histórico de preços de uma ação.
        
        Args:
            ticker: Código da ação
            period: Período (1d, 5d, 1mo, 3mo, 6mo, 1y, 5y)
        """
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker.upper())
            hist = stock.history(period=period)
            
            if hist.empty:
                return f"Sem dados para {ticker}"
            
            first = hist['Close'].iloc[0]
            last = hist['Close'].iloc[-1]
            change = ((last - first) / first) * 100
            high = hist['High'].max()
            low = hist['Low'].min()
            
            return f"{ticker.upper()} ({period}): Início R$ {first:.2f} → Atual R$ {last:.2f} ({change:+.2f}%), Máx R$ {high:.2f}, Mín R$ {low:.2f}"
        except Exception as e:
            logger.error(f"[YFINANCE] Erro histórico: {e}")
            return f"Erro: {str(e)}"


yfinance_tools = YFinanceTools()
