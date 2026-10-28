"""
Módulo de configuração de logging para projetos Melnick.
Uso:
    from Módulos.logs_melnick import setup_logger
    logger = setup_logger("NomeDoLogger", logs_path="caminho/para/logs")
"""

import logging
import sys
import os

# Formatter customizado para console
class ConsoleFormatter(logging.Formatter):
    """Formatter que mostra nível apenas se > INFO e nome apenas se não for o logger principal."""
    
    def __init__(self, main_logger_name: str | None = None):
        super().__init__()
        self.main_logger_name = main_logger_name
    
    def format(self, record):
        parts = []
        
        # Mostra o nível se for maior que INFO (WARNING, ERROR, CRITICAL)
        if record.levelno > logging.INFO:
            parts.append(f"{record.levelname}")
        
        # Mostra o nome do logger se não for o logger principal
        if self.main_logger_name and record.name != self.main_logger_name:
            parts.append(f"[{record.name}]")
        
        # Monta a mensagem final
        if parts:
            return f"{' '.join(parts)} {record.getMessage()}"
        else:
            return record.getMessage()


def setup_logger(
    name: str,
    logs_path: str | None = None,
    log_file: str | None = None,
    level: int = logging.DEBUG,
    console_output: bool = True
) -> logging.Logger:
    """
    Configura e retorna um logger com formatação padronizada.
    
    Args:
        name: Nome do logger principal
        logs_path: Caminho da pasta de logs
        log_file: Nome do arquivo de log (padrão: {name.lower()}.log)
        level: Nível mínimo de logging (padrão: DEBUG)
        console_output: Se True, mostra logs no console
    
    Returns:
        Logger configurado
    """
    
    # Cria pasta de logs se necessário
    if logs_path and not os.path.exists(logs_path):
        os.makedirs(logs_path)
    
    # Define nome do arquivo de log
    if not log_file:
        log_file = f"{name.lower().replace(' ', '_')}.log"
    
    # Obtém ou cria o logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove handlers existentes para evitar duplicação
    root_logger.handlers.clear()
    
    # Handler para arquivo
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    if logs_path:
        file_handler = logging.FileHandler(
            os.path.join(logs_path, log_file) if logs_path else log_file,
            encoding='utf-8'
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)
    
    # Handler para console
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ConsoleFormatter(main_logger_name=name))
        root_logger.addHandler(console_handler)
    
    # Configura captura de exceções não tratadas
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            logging.getLogger(name).info("Execução cancelada pelo usuário.")
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger(name).critical(
            "Exceção não tratada %s: %s",
            exc_type.__name__, exc_value,
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    sys.excepthook = handle_exception
    
    # Retorna o logger com o nome especificado
    logger = logging.getLogger(name)
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Obtém um logger existente pelo nome.
    Use após setup_logger() ter sido chamado.
    
    Args:
        name: Nome do logger
    
    Returns:
        Logger existente
    """
    return logging.getLogger(name)