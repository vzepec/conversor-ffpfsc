# Payload para la PS5

La pestaña **PS5** de la app necesita que la consola ejecute el **helper de
[ps5upload](https://github.com/phantomptr/ps5upload)**. Esta carpeta incluye la
versión con la que se probó la app.

| Archivo | Versión | SHA-256 |
|---|---|---|
| `ps5upload-6.4.0.elf` | ps5upload 6.4.0 | `b0392932ae957821fbaccee44d761a9320655995ccfa80c9ffdcc5cec2497f70` |

Comprueba el archivo antes de enviarlo:

```bash
sha256sum payload/ps5upload-6.4.0.elf                         # Linux
Get-FileHash payload\ps5upload-6.4.0.elf -Algorithm SHA256    # Windows (PowerShell)
```

## Qué hace en la consola

- Abre el helper en el puerto **9120** (protocolo AVA1). La app lo usa para
  emparejarse, consultar el espacio libre, borrar y encender su servidor FTP.
- El FTP (puerto **2122**) no arranca solo: la app lo inicia cuando lo necesita,
  en solo lectura salvo durante una subida o un reemplazo.
- Sigue activo hasta que la PS5 se reinicia o entra en reposo.

## Cómo cargarlo

Requiere una PS5 con jailbreak y un **cargador de ELF** activo (normalmente en el
puerto **9021**). Cualquiera de estas formas sirve:

- **Al arrancar:** configúralo en tu jailbreak (etaHEN, autoload, etc.) para que
  se ejecute solo cada vez que inicias la consola.
- **Desde Linux:** `nc -q0 <IP de la PS5> 9021 < payload/ps5upload-6.4.0.elf`
- **Desde Windows:** usa un enviador de payloads (por ejemplo, el de la app de
  ps5upload o cualquier "payload sender") apuntando al puerto 9021.

Después, en la app: pestaña **PS5** → IP de la consola → **Conectar**. La primera
vez la PS5 muestra un código de 6 dígitos para emparejar. Consulta
[docs/PS5.md](../docs/PS5.md).

> [!IMPORTANT]
> La PS5 acepta emparejamientos nuevos solo durante los **5 minutos siguientes a
> cargar el payload** (si no tiene otro dispositivo emparejado).

## Compatibilidad

La app habla la versión 1 del protocolo AVA1, la que usan los helpers de
ps5upload **6.x**. Las versiones 5.x no son compatibles, y **la 7.0 tampoco**:
eliminó el servidor FTP (`ftp.start`) que usa la app para transferir. Para
actualizar dentro de 6.x, reemplaza el `.elf`, actualiza la tabla de arriba y
prueba emparejar, navegar, descargar y subir.

El FTP de 6.x guarda la posición de `REST` en un entero de 32 bits: solo puede
retomar un archivo en sus primeros 2 GiB. La app lo tiene en cuenta (ver
`docs/PS5.md`, «Cortes de conexión y reintentos»).

## Licencia

ps5upload se distribuye bajo **GPLv3**. Este binario se incluye sin cambios; su
código fuente está en <https://github.com/phantomptr/ps5upload/tree/v6.4.0>. Si
este repositorio se publica, acompaña el binario con ese enlace y con el texto de
la licencia, como exige la GPLv3.
