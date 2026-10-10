# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Añadido
- La versión de la aplicación se muestra en el título de la ventana y a la
  derecha de la línea de estado.

## [1.1.0] - 2026-10-09

### Añadido
- Rules de Claude Code en `.claude/rules/`: documentación en español neutro,
  límite de 250 líneas por archivo, código limpio y buenas prácticas.
- `tools/check_standards.py`: verifica el límite de líneas y que toda función
  tenga docstring con `Args`, `Returns`, `Yields` y `Raises`; se ejecuta en `pytest`.
- Tests del verificador y de la comprobación de espacio libre.

### Cambiado
- Todas las funciones y métodos documentados con descripción breve, parámetros,
  retorno y excepciones.
- `ui/app.py` dividido en `main_view.py`, `options_panel.py`, `job_table.py`,
  `dialogs.py` y `event_handlers.py`; `app.py` queda como controlador.
- `infrastructure/mkpfs_adapter.py` convertido en subpaquete (`command`,
  `output`, `process`, `metadata`) con la misma API pública.

## [1.0.0] - 2026-10-09

### Añadido
- Paquete `ffpfsc_converter` con arquitectura en capas (`domain`, `infrastructure`,
  `services`, `ui`).
- Suite de tests con pytest (descubrimiento, metadatos, estimación, adaptador
  MkPFS, cola de conversión y textos de la UI).
- Configuración de `ruff`, `pyproject.toml` y comando `ffpfsc-converter`.
- Documentación: README, arquitectura, guía de uso y guía de desarrollo.
- Skills de Claude Code para arquitectura, código limpio y buenas prácticas.
- `instalar.sh --dev` instala también las herramientas de desarrollo.

### Cambiado
- `conversor.py` (archivo único) se reemplaza por el paquete; `abrir.sh` ahora
  ejecuta `python -m ffpfsc_converter` y es portable (no tiene rutas fijas).
- Los eventos entre hilos son dataclasses tipadas en lugar de tuplas.
- El estado del trabajo (`JobState`) se separa del texto mostrado.

### Corregido
- La estimación y el resultado mostraban `−-35%` cuando el archivo crecía;
  ahora se muestra `+35%`.

## [0.1.0] - 2026-10-09

- Primera versión funcional: interfaz Tkinter con arrastrar y soltar,
  estimación de tamaño y conversión con MkPFS.
