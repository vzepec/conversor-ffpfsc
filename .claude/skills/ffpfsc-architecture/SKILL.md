---
name: ffpfsc-architecture
description: Reglas de arquitectura en capas del Conversor FFPFSC (domain, infrastructure, services, ui). Úsala antes de crear un módulo, mover código, añadir una funcionalidad, una opción de MkPFS, un formato de origen, un evento o cualquier cambio que cruce capas en src/ffpfsc_converter.
---

# Arquitectura del Conversor FFPFSC

## La regla

**Las dependencias solo apuntan hacia abajo.** Antes de escribir un `import`,
comprueba esta tabla. Si el import no está permitido, el código está en la capa
equivocada.

| Capa | Ruta | Responsabilidad | Puede importar | PROHIBIDO |
|------|------|-----------------|----------------|-----------|
| Dominio | `domain/` | Modelos (`dataclass`, `Enum`) y eventos | stdlib | cualquier módulo del proyecto, `tkinter`, `mkpfs`, `subprocess`, E/S |
| Infraestructura | `infrastructure/` | Hablar con el exterior: MkPFS, disco, SO | `domain`, `config`, terceros | `services`, `ui`, `tkinter` |
| Servicios | `services/` | Casos de uso, orquestación, hilos de trabajo | `domain`, `infrastructure`, `config`, `errors` | `ui`, `tkinter`, `subprocess`, `import mkpfs` |
| Presentación | `ui/` | Widgets, diálogos, textos | todo lo anterior | `subprocess`, `mkpfs`, lógica de negocio |
| Transversal | `config.py`, `errors.py` | Constantes y excepciones | `domain` | `services`, `ui` |

Comprobación rápida (no debe imprimir nada):

```bash
grep -rnE "^(from|import) (tkinter|ffpfsc_converter\.(ui|services|infrastructure))" src/ffpfsc_converter/domain
grep -rnE "^(from|import) (tkinter|ffpfsc_converter\.(ui|services))" src/ffpfsc_converter/infrastructure
grep -rnE "^(from|import) (tkinter|subprocess|mkpfs|ffpfsc_converter\.ui)" src/ffpfsc_converter/services
grep -rnE "^(import|from) (subprocess|mkpfs)" src/ffpfsc_converter/ui
```

## Dónde va cada cosa

| Necesito… | Archivo |
|-----------|---------|
| Un número/umbral/texto configurable | `config.py` (con comentario `#:` explicando el porqué) |
| Una nueva entidad o valor | `domain/models.py` (`@dataclass(frozen=True)` si es un valor) |
| Notificar algo a la UI desde un hilo | nueva clase en `domain/events.py` + añadirla a la unión `Event` |
| Un flag o parámetro de MkPFS | `ConversionOptions` + `infrastructure/mkpfs_adapter.build_pack_command` |
| Leer algo de MkPFS (metadatos, exFAT) | `infrastructure/mkpfs_adapter/metadata.py` (import diferido de `mkpfs`) |
| Operación de disco/SO | `infrastructure/filesystem.py` o `infrastructure/system.py` |
| Un caso de uso / regla de negocio | `services/<caso_de_uso>.py` |
| Un error que verá el usuario | subclase de `ConverterError` en `errors.py`, mensaje en español |
| Un texto que muestra la UI | función pura en `ui/presenters.py` |
| Color, fuente, medida | `ui/theme.py` |
| Un widget nuevo | módulo propio en `ui/` (como `options_panel.py`, `job_table.py`) compuesto en `ui/main_view.py` |
| Un diálogo o mensaje | `ui/dialogs.py` |
| Reaccionar a un evento en la vista | `ui/event_handlers.py` (`ViewUpdater`) |
| Una acción del usuario | callback en `ViewCallbacks` + método en `ui/app.py` (`MainWindow`) |

## Comunicación entre hilos

1. Los servicios que trabajan en segundo plano reciben un `EventSink`
   (`Callable[[Event], None]`) por constructor o parámetro. **Nunca** reciben
   widgets ni la ventana.
2. Publican eventos inmutables de `domain/events.py`.
3. `MainWindow._poll_events` los consume en el hilo de la interfaz y se los
   entrega a `ViewUpdater`, que los despacha con el diccionario `_handlers`
   (`tipo de evento → método _on_<evento>`).
4. Para un evento nuevo: crear la dataclass → añadirla a `Event` → publicarla
   en el servicio → registrar el manejador en `ViewUpdater._handlers` → test del servicio.

## Inyección de dependencias

Todo lo que lanza procesos o depende del entorno se inyecta para poder
testearlo (ver `ConversionRunner(emit, process_factory=...)`). Al crear un
servicio nuevo que use infraestructura costosa, acepta la dependencia como
parámetro con un valor por defecto real.

## Señales de alarma

- Un servicio importa `tkinter` o llama a `messagebox` → mover la decisión a la UI.
- La UI construye un comando o lee un archivo del juego → mover a un servicio.
- Aparece un literal numérico de negocio fuera de `config.py`.
- Un archivo supera **250 líneas** o mezcla dos responsabilidades → dividir (regla `limite-de-lineas.md`).
- Un evento se publica como tupla o dict → debe ser una dataclass de `domain/events.py`.

Al terminar, actualiza `docs/ARCHITECTURE.md` si cambiaste la estructura.
