# Rich Live Display - Fix para Windows CMD/PowerShell

## Problema

Rich `Live` imprime multiples frames visibles en vez de sobreescribir el anterior.
El mismo bloque aparece N veces (una por cada auto-refresh a 4fps).

## Causa raiz

### Como funciona Live en Rich

Rich tiene dos modos de renderizado en Windows:

| Modo | Condicion | Como mueve el cursor |
|------|-----------|----------------------|
| **VT100** | `detect_legacy_windows()` → False (VT disponible) | ANSI escape codes (`\033[NA`) |
| **Legacy Win32** | `detect_legacy_windows()` → True (VT no disponible) | `SetConsoleCursorPosition()` Win32 API |

`detect_legacy_windows()` implementa: `WINDOWS and not get_windows_console_features().vt`

### Por que fallaba

El codigo usaba `Console(markup=True, force_terminal=True)`.

`force_terminal=True` fuerza `is_terminal=True` sin importar el contexto real.
Esto causa que Rich emita ANSI escape codes incluso cuando:
- stdout es una pipe (Git Bash, redireccion, captura)
- El terminal no tiene VT processing activo

Cuando los codigos `\033[NA` (cursor-up) no se procesan, cada frame del
`Live` se imprime como texto nuevo en lugar de sobreescribir el anterior.

Importante: `force_terminal=True` NO bypasea `legacy_windows`. Pero si el
entorno es una pipe o MSYS2/mintty, `detect_legacy_windows()` puede retornar
False (asume VT disponible) mientras el cursor-up de todas formas no funciona.

## Solucion

### Fix aplicado: remover `force_terminal=True`

```python
# ANTES (roto)
console = Console(markup=True, force_terminal=True)

# DESPUES (correcto)
console = Console(markup=True)
```

Con auto-deteccion:
- **cmd.exe / PowerShell modernos** (Windows 10+): detecta VT100, usa ANSI → Live funciona
- **cmd.exe legacy sin VT**: detecta legacy_windows, usa Win32 API → Live funciona
- **pipe / redireccion / CI**: detecta no-terminal → Rich deshabilita colores y Live graciosamente

### Fix adicional: transient=True en Live

```python
# ANTES
Live(..., transient=False)  # frames intermedios quedan visibles al parar

# DESPUES
Live(..., transient=True)   # limpia al parar; estado final se imprime manualmente
```

Y en `on_pipeline_end` imprimir el arbol final una sola vez:
```python
self._live.stop()
self._console.print(self._render_tree())
```

### Alternativa: habilitar VT processing manualmente (no aplicada)

Si en algun caso se necesita `force_terminal=True` y se quiere forzar VT100:

```python
import sys
if sys.platform == "win32":
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32")
    handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
    mode = ctypes.c_ulong()
    kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    mode.value |= 4  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    kernel32.SetConsoleMode(handle, mode)
```

Tambien funciona el truco `os.system("")` que inicializa el subsistema de
color de Windows y habilita VT processing como efecto secundario.

## Referencias

- [Rich Console API](https://rich.readthedocs.io/en/stable/reference/console.html)
- [Python bug #29059 - Windows ANSI](https://bugs.python.org/issue29059)
- [Rich _win32_console.py](https://github.com/Textualize/rich/blob/master/rich/_win32_console.py)
- [Microsoft - Console Virtual Terminal Sequences](https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences)
- [Rich issue #1320 - spinner moves down on Windows](https://github.com/Textualize/rich/issues/1320)
