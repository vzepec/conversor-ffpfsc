# Vectores de prueba de AVA1

Copiados sin cambios de
[phantomptr/ps5upload](https://github.com/phantomptr/ps5upload/tree/main/protocol/ava1/vectors)
(licencia GPLv3). Fijan byte a byte la cabecera de trama, las derivaciones de
claves, el handshake Noise XX y el PAKE de emparejamiento, para que el cliente
de `infrastructure/ava1/` hable exactamente el mismo protocolo que el helper.
