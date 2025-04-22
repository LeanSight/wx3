# lazy_loading.py
"""Módulo para carga perezosa (lazy loading) de dependencias con medición de tiempos."""

import importlib
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Tuple, Union

# Caché para mantener los módulos ya cargados
_module_cache: Dict[str, Any] = {}
# Caché para mantener los tiempos de carga
_loading_times: Dict[str, float] = {}

# Logger específico para lazy loading
logger = logging.getLogger("wx3.lazy_loading")


def measure_loading_time(func: Callable) -> Callable:
    """Decorador para medir el tiempo de carga de módulos o componentes.
    
    Args:
        func: Función a decorar
        
    Returns:
        Función decorada que mide y registra el tiempo de ejecución
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        component_name = args[0] if args and isinstance(args[0], str) else "unknown"
        
        # Mensaje al iniciar la carga
        logger.info(f"Cargando: {component_name}")
        
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        # Extraer el nombre del módulo o componente
        if args and isinstance(args[0], str):
            loading_time = end_time - start_time
            _loading_times[component_name] = loading_time
            logger.info(f"Cargado: {component_name} en {loading_time:.4f}s")
        
        return result
    return wrapper


@measure_loading_time
def _load_module(module_name: str) -> Any:
    """Carga un módulo Python mediante importlib.
    
    Args:
        module_name: Nombre del módulo a cargar
        
    Returns:
        Módulo cargado
        
    Raises:
        ImportError: Si el módulo no puede ser cargado
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        logger.error(f"Error al cargar el módulo '{module_name}': {e}")
        raise


@measure_loading_time
def _load_component(module: Any, component_name: str) -> Any:
    """Carga un componente específico desde un módulo.
    
    Args:
        module: Módulo del que cargar el componente
        component_name: Nombre del componente a cargar
        
    Returns:
        Componente cargado
        
    Raises:
        AttributeError: Si el componente no existe en el módulo
    """
    try:
        return getattr(module, component_name)
    except AttributeError as e:
        logger.error(f"Error al cargar el componente '{component_name}': {e}")
        raise


def lazy_load(module_name: str, components: Union[str, List[str]]) -> Union[Any, Tuple[Any, ...]]:
    """Carga perezosa de módulos y componentes con medición de tiempos.
    
    Args:
        module_name: Nombre del módulo a cargar
        components: Nombre del componente o lista de nombres de componentes a cargar.
                   Si es una cadena vacía, devuelve el módulo completo.
        
    Returns:
        Módulo completo, componente único o tupla de componentes cargados
        
    Example:
        # Cargar un módulo completo
        torch = lazy_load("torch", "")
        
        # Cargar un único componente
        Pipeline = lazy_load("pyannote.audio", "Pipeline")
        
        # Cargar múltiples componentes
        nn, optim = lazy_load("torch", ["nn", "optim"])
    """
    # Comprobar si el módulo ya está en caché
    if module_name not in _module_cache:
        _module_cache[module_name] = _load_module(module_name)
    
    module = _module_cache[module_name]
    
    # Caso especial: devolver el módulo completo si components es una cadena vacía
    if components == "":
        return module
    
    # Manejar caso de componente único
    if isinstance(components, str):
        return _load_component(module, components)
    
    # Manejar caso de múltiples componentes
    return tuple(_load_component(module, comp) for comp in components)


def get_loading_times() -> Dict[str, float]:
    """Devuelve un diccionario con los tiempos de carga registrados.
    
    Returns:
        Diccionario con nombres de módulos/componentes y sus tiempos de carga
    """
    return _loading_times.copy()