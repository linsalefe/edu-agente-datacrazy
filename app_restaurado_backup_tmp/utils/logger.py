"""
Sistema de Logs com Loguru
Configuração para desenvolvimento e produção
"""

import sys
from pathlib import Path
from loguru import logger
from app.config import settings


def setup_logger():
    """Configura o sistema de logs"""
    
    # Remove handler padrão
    logger.remove()
    
    # Formato de log
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Console (sempre ativo)
    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if settings.DEBUG else "INFO",
        colorize=True
    )
    
    # Criar diretório de logs
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Arquivo de logs INFO+
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        format=log_format,
        level="INFO",
        rotation="00:00",  # Rotação à meia-noite
        retention="30 days",  # Manter 30 dias
        compression="zip",  # Comprimir logs antigos
        encoding="utf-8"
    )
    
    # Arquivo de logs ERROR+
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        format=log_format,
        level="ERROR",
        rotation="00:00",
        retention="60 days",  # Erros mantém mais tempo
        compression="zip",
        encoding="utf-8"
    )
    
    # Arquivo JSON para parsing automático (produção)
    if not settings.DEBUG:
        logger.add(
            log_dir / "app_{time:YYYY-MM-DD}.json",
            format="{message}",
            level="INFO",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            serialize=True  # Formato JSON
        )
    
    logger.info("✅ Sistema de logs configurado")
    logger.info(f"📁 Logs salvos em: {log_dir.absolute()}")


# Inicializar ao importar
setup_logger()