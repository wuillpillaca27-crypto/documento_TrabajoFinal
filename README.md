# Monitor de Rendimiento en Tiempo Real para xv6-riscv

Universidad Nacional de San Cristóbal de Huamanga — Ingeniería de Sistemas — IS-380 — 2026-II.

**Integrantes:** Jesús David Quispe Roca, Wuill Grover Pillaca Mesares y Romel Baruch Medina Rondinel.

**Docente:** Ing. Lizbeth Jaico Quispe.

## Descripción
Monitor de procesos, memoria libre y ticks del kernel mediante la syscall getmetrics, sysmon, QEMU y una interfaz Python con Tkinter y Matplotlib. Incluye stresstest, gráficas, tabla de procesos y exportación CSV.

## Instalación y ejecución
Usar la copia original de xv6 del curso. Este paquete contiene archivos nuevos y documentación, no el sistema operativo base. Integrar las modificaciones descritas en [Integración kernel](documento_TrabajoFinal/04_Documentacion_Complementaria/Integracion_kernel.md).

```bash
sudo apt update
sudo apt install -y python3-tk python3-matplotlib
make clean && make && make fs.img
make qemu
```
En xv6 ejecutar `sysmon`. Salir con Ctrl+A, luego X. Desde Ubuntu, en la raíz:

```bash
python3 monitor_xv6.py
```
Ejecutar la prueba de carga desde el botón correspondiente y exportar el CSV. No iniciar una segunda instancia de QEMU simultáneamente.

## Documentación
[Índice del trabajo final](documento_TrabajoFinal/README.md).

## Validación
La compilación debe repetirse en la variante del curso. Kill y cierre automático requieren validación final según la monografía. Las capturas y CSV de una ejecución actual y el PPTX original deben incorporarse. No se incluyen resultados simulados.
