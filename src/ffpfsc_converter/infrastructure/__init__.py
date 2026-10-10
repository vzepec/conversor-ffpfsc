"""Capa de infraestructura: adaptadores al sistema operativo y a MkPFS.

Es la única capa que habla con procesos, el sistema de archivos a bajo nivel
o librerías de terceros. Las capas superiores dependen de estas funciones,
nunca de ``subprocess`` o ``mkpfs`` directamente.
"""
