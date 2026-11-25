import os
import signal
import csv
import queue
import subprocess
import threading
import tkinter as tk
from collections import deque
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

MAX_POINTS = 60
TOTAL_MEM_KB = 128 * 1024  # 128 MB por defecto en xv6-riscv


class XV6MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Monitor de Rendimiento en Tiempo Real - xv6-riscv")
        self.root.geometry("1150x600")

        self.frame_queue = queue.Queue()
        self.running = True
        self.update_job = None
        self.qemu_proc = None

        self.ticks_data = deque(maxlen=MAX_POINTS)
        self.mem_used_data = deque(maxlen=MAX_POINTS)
        self.procs_data = deque(maxlen=MAX_POINTS)
        self.full_history = []

        self._build_ui()
        self._start_xv6()
        self._update_loop()

    def _build_ui(self):
        # 1. Barra Superior (KPIs y acciones)
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        self.lbl_ticks = ttk.Label(top_frame, text="Ticks: 0", font=("Consolas", 11, "bold"))
        self.lbl_ticks.pack(side=tk.LEFT, padx=10)

        self.lbl_mem = ttk.Label(top_frame, text="RAM Libre: 0 KB", font=("Consolas", 11, "bold"))
        self.lbl_mem.pack(side=tk.LEFT, padx=10)

        self.lbl_procs = ttk.Label(
            top_frame,
            text="Procesos: 0 (Run: 0 | Ready: 0 | Sleep: 0)",
            font=("Consolas", 11, "bold"),
        )
        self.lbl_procs.pack(side=tk.LEFT, padx=10)

        ttk.Button(top_frame, text="Exportar CSV", command=self._export_csv).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="Prueba de Carga (stresstest)", command=self._send_stress).pack(side=tk.RIGHT, padx=5)

        # 2. Panel Principal Dividido
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Izquierda: Gráficas
        chart_frame = ttk.Frame(main_pane)
        main_pane.add(chart_frame, weight=3)

        self.fig, (self.ax_mem, self.ax_proc) = plt.subplots(2, 1, figsize=(6.5, 5.5), dpi=100)
        self.fig.tight_layout(pad=3.0)
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Derecha: Tabla de procesos estilo htop
        proc_frame = ttk.LabelFrame(main_pane, text="Tabla de Procesos Activos (xv6)", padding=8)
        main_pane.add(proc_frame, weight=2)

        table_container = ttk.Frame(proc_frame)
        table_container.pack(fill=tk.BOTH, expand=True)

        cols = ("pid", "name", "state", "mem")
        self.tree = ttk.Treeview(table_container, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("pid", text="PID")
        self.tree.heading("name", text="Nombre")
        self.tree.heading("state", text="Estado")
        self.tree.heading("mem", text="Mem (KB)")
        self.tree.column("pid", width=55, anchor=tk.CENTER)
        self.tree.column("name", width=110, anchor=tk.W)
        self.tree.column("state", width=95, anchor=tk.CENTER)
        self.tree.column("mem", width=85, anchor=tk.E)

        self.tree.tag_configure("RUNNING", background="#dcfce7")
        self.tree.tag_configure("RUNNABLE", background="#fef9c3")
        self.tree.tag_configure("SLEEPING", background="#f1f5f9")
        self.tree.tag_configure("ZOMBIE", background="#fee2e2")

        scrollbar = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        proc_ctrl = ttk.Frame(proc_frame, padding=(0, 8, 0, 0))
        proc_ctrl.pack(fill=tk.X)
        ttk.Button(proc_ctrl, text="Matar Proceso Seleccionado (kill)", command=self._kill_selected).pack(fill=tk.X)

        # 3. Barra Inferior: Consola rápida hacia xv6
        cmd_frame = ttk.Frame(self.root, padding=(10, 5, 10, 10))
        cmd_frame.pack(fill=tk.X)
        ttk.Label(cmd_frame, text="Comando xv6:").pack(side=tk.LEFT, padx=(0, 8))
        self.cmd_entry = ttk.Entry(cmd_frame)
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.cmd_entry.bind("<Return>", lambda _e: self._send_custom_command())
        ttk.Button(cmd_frame, text="Enviar", command=self._send_custom_command).pack(side=tk.RIGHT)

    def _start_xv6(self):
        try:
            self.qemu_proc = subprocess.Popen(
                ["make", "qemu"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            threading.Thread(target=self._read_qemu_output, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error al iniciar QEMU", f"No se pudo ejecutar 'make qemu':\n{e}")

    def _read_qemu_output(self):
        sysmon_started = False
        current_metric = None
        current_procs = []

        for line in self.qemu_proc.stdout:
            if not self.running:
                break
            line = line.strip()

            if not sysmon_started and "init: starting sh" in line:
                self._write_to_xv6("sysmon &")
                sysmon_started = True

            if line.startswith("METRIC|"):
                parts = line.split("|")
                if len(parts) == 7:
                    try:
                        current_metric = {
                            "ticks": int(parts[1]),
                            "free_kb": int(parts[2]),
                            "total": int(parts[3]),
                            "running": int(parts[4]),
                            "runnable": int(parts[5]),
                            "sleeping": int(parts[6]),
                        }
                        current_procs = []
                    except ValueError:
                        current_metric = None

            elif line.startswith("PROC|") and current_metric is not None:
                parts = line.split("|")
                if len(parts) == 5:
                    try:
                        current_procs.append({
                            "pid": int(parts[1]),
                            "state": parts[2],
                            "mem_kb": int(parts[3]),
                            "name": parts[4],
                        })
                    except ValueError:
                        pass

            elif line == "END_FRAME" and current_metric is not None:
                self.frame_queue.put((current_metric, current_procs))
                current_metric = None
                current_procs = []

    def _write_to_xv6(self, command):
        if self.qemu_proc and self.qemu_proc.stdin and self.qemu_proc.poll() is None:
            try:
                self.qemu_proc.stdin.write(command + "\n")
                self.qemu_proc.stdin.flush()
            except OSError:
                pass

    def _send_stress(self):
        self._write_to_xv6("stresstest &")

    def _send_custom_command(self):
        cmd = self.cmd_entry.get().strip()
        if cmd:
            self._write_to_xv6(cmd)
            self.cmd_entry.delete(0, tk.END)

    def _kill_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Sin selección", "Selecciona un proceso de la tabla primero.")
            return

        values = self.tree.item(selected[0], "values")
        pid = int(values[0])
        name = values[1]

        if pid in (1, 2) or name == "sysmon":
            confirm = messagebox.askyesno(
                "Proceso crítico",
                f"El proceso '{name}' (PID {pid}) es esencial en xv6. ¿Seguro que deseas matarlo?",
            )
            if not confirm:
                return

        self._write_to_xv6(f"kill {pid}")

    def _export_csv(self):
        if not self.full_history:
            messagebox.showinfo("Sin datos", "Aún no hay métricas registradas para exportar.")
            return

        default_name = f"xv6_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("Archivo CSV", "*.csv")],
            title="Guardar historial de métricas",
        )
        if not filepath:
            return

        try:
            with open(filepath, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "timestamp",
                        "ticks",
                        "ram_used_mb",
                        "ram_free_kb",
                        "total_procs",
                        "running",
                        "runnable",
                        "sleeping",
                    ],
                )
                writer.writeheader()
                writer.writerows(self.full_history)
            messagebox.showinfo(
                "Exportación exitosa",
                f"Se guardaron {len(self.full_history)} registros en:\n{filepath}",
            )
        except Exception as e:
            messagebox.showerror("Error al exportar", f"No se pudo guardar el archivo:\n{e}")

    def _update_loop(self):
        latest_frame = None

        while not self.frame_queue.empty():
            m, procs = self.frame_queue.get()
            used_kb = max(0, TOTAL_MEM_KB - m["free_kb"])
            used_mb = round(used_kb / 1024.0, 2)

            self.ticks_data.append(m["ticks"])
            self.mem_used_data.append(used_mb)
            self.procs_data.append(m["total"])

            self.full_history.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "ticks": m["ticks"],
                "ram_used_mb": used_mb,
                "ram_free_kb": m["free_kb"],
                "total_procs": m["total"],
                "running": m["running"],
                "runnable": m["runnable"],
                "sleeping": m["sleeping"],
            })
            latest_frame = (m, procs)

        if latest_frame is not None:
            m, procs = latest_frame
            self.lbl_ticks.config(text=f"Ticks: {m['ticks']}")
            self.lbl_mem.config(text=f"RAM Libre: {m['free_kb']:,} KB")
            self.lbl_procs.config(
                text=f"Procesos: {m['total']} (Run: {m['running']} | Ready: {m['runnable']} | Sleep: {m['sleeping']})"
            )
            self._refresh_process_table(procs)
            self._redraw_charts()

        if self.running:
            self.update_job = self.root.after(200, self._update_loop)

    def _refresh_process_table(self, procs):
        selected_pid = None
        sel = self.tree.selection()
        if sel:
            selected_pid = self.tree.item(sel[0], "values")[0]

        self.tree.delete(*self.tree.get_children())
        for p in procs:
            tag = p["state"] if p["state"] in ("RUNNING", "RUNNABLE", "SLEEPING", "ZOMBIE") else ""
            item_id = self.tree.insert(
                "",
                tk.END,
                values=(p["pid"], p["name"], p["state"], p["mem_kb"]),
                tags=(tag,),
            )
            if selected_pid is not None and str(p["pid"]) == str(selected_pid):
                self.tree.selection_set(item_id)

    def _redraw_charts(self):
        x = list(self.ticks_data)

        self.ax_mem.clear()
        self.ax_mem.plot(x, list(self.mem_used_data), color="#2563eb", linewidth=2)
        self.ax_mem.fill_between(x, list(self.mem_used_data), color="#93c5fd", alpha=0.3)
        self.ax_mem.set_title("Uso de Memoria RAM en xv6 (MB)")
        self.ax_mem.set_ylabel("MB")
        self.ax_mem.grid(True, linestyle="--", alpha=0.5)

        self.ax_proc.clear()
        self.ax_proc.plot(x, list(self.procs_data), color="#16a34a", linewidth=2, marker="o", markersize=3)
        self.ax_proc.set_title("Procesos Activos en Tabla de Procesos")
        self.ax_proc.set_xlabel("Ticks del Kernel")
        self.ax_proc.set_ylabel("Cantidad")
        self.ax_proc.grid(True, linestyle="--", alpha=0.5)

        self.canvas.draw()

    def on_close(self):
        self.running = False
        if self.update_job is not None:
            self.root.after_cancel(self.update_job)
            self.update_job = None

        if self.qemu_proc:
            try:
                os.killpg(self.qemu_proc.pid, signal.SIGTERM)
                self.qemu_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.qemu_proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.qemu_proc.wait()
            except ProcessLookupError:
                pass

        plt.close(self.fig)
        self.root.quit()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = XV6MonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
