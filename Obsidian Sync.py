import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import tempfile
import os
import json
import winreg

CONFIG_FILE = "obsidian_sync_config.json"

def find_winscp():
    """Ищет WinSCP.com в стандартных папках установки"""
    paths = [
        r"C:\Program Files (x86)\WinSCP\WinSCP.com",
        r"C:\Program Files\WinSCP\WinSCP.com"
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    return ""

def get_winscp_sessions():
    """Читает сохраненные сессии из реестра WinSCP"""
    sessions = []
    try:
        # Открываем ветку реестра WinSCP (для текущего пользователя)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Martin Prikryl\WinSCP 2\Sessions")
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                # Дефолтную сессию пропускаем
                if subkey_name.lower() != "default settings":
                    # WinSCP кодирует имена сессий в реестре, декодируем базовые символы
                    name = subkey_name.replace("%3A", ":").replace("%2F", "/").replace("%5C", "\\")
                    sessions.append(name)
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except FileNotFoundError:
        # WinSCP не установлен или нет сохраненных сессий
        pass
    return sessions


class ObsidianSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Obsidian Sync")
        self.root.geometry("420x380")
        self.root.resizable(False, False)

        # Переменные настроек
        self.winscp_path = tk.StringVar()
        self.session_name = tk.StringVar()
        self.local_vault = tk.StringVar()

        # Переменные интерфейса
        self.allow_delete = tk.BooleanVar(value=False)
        self.preview_only = tk.BooleanVar(value=False)

        # Загрузка настроек
        self.load_config()

        # Стили
        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))

        self.setup_ui()

        # Если путь к WinSCP пуст, пробуем найти автоматически
        if not self.winscp_path.get():
            found_path = find_winscp()
            if found_path:
                self.winscp_path.set(found_path)

        # Если настройки не завершены, открываем окно настроек
        if not self.is_config_valid():
            self.root.after(100, self.open_settings)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.winscp_path.set(data.get("winscp", ""))
                    self.session_name.set(data.get("session", ""))
                    self.local_vault.set(data.get("local", ""))
            except Exception:
                pass

    def save_config(self):
        data = {
            "winscp": self.winscp_path.get(),
            "session": self.session_name.get(),
            "local": self.local_vault.get()
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def is_config_valid(self):
        return all([self.winscp_path.get(), self.session_name.get(), self.local_vault.get()])

    def setup_ui(self):
        # Шапка
        header_frame = ttk.Frame(root, padding=10)
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text="Obsidian Sync", style="Header.TLabel").pack()
        ttk.Label(header_frame, text="Синхронизация ПК ⇄ Телефон").pack()

        # Информация о текущем хранилище
        info_frame = ttk.Frame(root, padding=10)
        info_frame.pack(fill=tk.X)
        ttk.Label(info_frame, text="Локальное хранилище:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.vault_label = ttk.Label(info_frame, text="Не выбрано", foreground="gray")
        self.vault_label.grid(row=0, column=1, sticky=tk.W, pady=2)
        self.update_info_label()

        # Настройки синхронизации
        settings_frame = ttk.LabelFrame(root, text=" Опции синхронизации ", padding=10)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Checkbutton(
            settings_frame,
            text="Разрешить удаление (Зеркалирование)",
            variable=self.allow_delete
        ).pack(anchor=tk.W)
        ttk.Label(settings_frame, text="(Если выключено: файлы только добавляются и обновляются)", 
                  foreground="gray", font=("Segoe UI", 8)).pack(anchor=tk.W)
        
        ttk.Checkbutton(
            settings_frame,
            text="Только предпросмотр (не применять изменения)",
            variable=self.preview_only
        ).pack(anchor=tk.W, pady=(5,0))

        # Кнопки действий
        btn_frame = ttk.Frame(root, padding=10)
        btn_frame.pack(fill=tk.BOTH, expand=True)

        self.btn_push = ttk.Button(btn_frame, text="⬆ Отправить на телефон (ПК → Телефон)", command=lambda: self.sync("remote"))
        self.btn_push.pack(fill=tk.X, pady=3)

        self.btn_pull = ttk.Button(btn_frame, text="⬇ Скачать на ПК (Телефон → ПК)", command=lambda: self.sync("local"))
        self.btn_pull.pack(fill=tk.X, pady=3)

        # Нижние кнопки
        bottom_frame = ttk.Frame(root, padding=10)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Button(bottom_frame, text="⚙ Настройки", command=self.open_settings).pack(side=tk.LEFT)
        ttk.Button(bottom_frame, text="Выход", command=self.root.destroy).pack(side=tk.RIGHT)

    def update_info_label(self):
        vault = self.local_vault.get()
        if vault:
            self.vault_label.config(text=vault, foreground="black")
        else:
            self.vault_label.config(text="Не выбрано", foreground="gray")

    def toggle_buttons(self, state):
        self.btn_push.config(state=state)
        self.btn_pull.config(state=state)
        self.root.config(cursor="watch" if state == tk.DISABLED else "")

    def sync(self, direction):
        if not self.is_config_valid():
            messagebox.showwarning("Внимание", "Сначала укажите пути в настройках!")
            self.open_settings()
            return

        winscp = self.winscp_path.get()
        local = self.local_vault.get()
        session = self.session_name.get()

        if not os.path.exists(winscp):
            messagebox.showerror("Ошибка", f"Файл WinSCP не найден:\n{winscp}")
            return
        if not os.path.isdir(local):
            messagebox.showerror("Ошибка", f"Локальная папка не найдена:\n{local}")
            return

        # Формируем команду
        command = f"synchronize {direction}"
        
        # Если включено удаление - добавляем флаг mirror.
        # Без него WinSCP скопирует новые и измененные файлы, но не удалит старые.
        if self.allow_delete.get():
            command += " -mirror"
            
        if self.preview_only.get():
            command += " -preview"

        script = f"""option batch abort
option confirm off
open "{session}"
lcd "{local}"
cd /
{command}
exit
"""

        # Создаем временный файл скрипта
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as f:
            f.write(script)
            script_name = f.name

        self.toggle_buttons(tk.DISABLED)

        try:
            # Запускаем WinSCP, перехватывая вывод
            result = subprocess.run(
                [winscp, f"/script={script_name}"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW # Скрываем черное окно консоли
            )

            if result.returncode == 0:
                if self.preview_only.get():
                    messagebox.showinfo("Предпросмотр", "Предпросмотр завершен успешно.")
                else:
                    messagebox.showinfo("Успех", "Синхронизация завершена успешно!")
            else:
                # Показываем ошибки
                error_msg = result.stdout or result.stderr or "Неизвестная ошибка"
                messagebox.showerror("Ошибка WinSCP", error_msg)

        except Exception as e:
            messagebox.showerror("Критическая ошибка", str(e))
        finally:
            os.remove(script_name)
            self.toggle_buttons(tk.NORMAL)

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Настройки")
        win.geometry("500x250")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        # Путь к WinSCP
        ttk.Label(win, text="Путь к WinSCP.com:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        winscp_entry = ttk.Entry(win, textvariable=self.winscp_path, width=40)
        winscp_entry.grid(row=0, column=1, padx=10, pady=10)
        ttk.Button(win, text="...", width=3, command=lambda: self.browse_file(winscp_entry)).grid(row=0, column=2, padx=5, pady=10)

        # Сессия (выпадающий список)
        ttk.Label(win, text="Сессия WinSCP:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        sessions = get_winscp_sessions()
        session_combo = ttk.Combobox(win, textvariable=self.session_name, values=sessions, width=37)
        session_combo.grid(row=1, column=1, padx=10, pady=10)

        # Локальное хранилище
        ttk.Label(win, text="Локальное хранилище:").grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
        vault_entry = ttk.Entry(win, textvariable=self.local_vault, width=40)
        vault_entry.grid(row=2, column=1, padx=10, pady=10)
        ttk.Button(win, text="...", width=3, command=lambda: self.browse_dir(vault_entry)).grid(row=2, column=2, padx=5, pady=10)

        # Кнопки сохранения
        btn_frame = ttk.Frame(win)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=15)
        ttk.Button(btn_frame, text="Сохранить", command=lambda: self.save_settings(win)).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Отмена", command=win.destroy).pack(side=tk.LEFT, padx=10)

    def browse_file(self, entry_widget):
        filepath = filedialog.askopenfilename(filetypes=[("WinSCP Console", "WinSCP.com"), ("Все файлы", "*.*")])
        if filepath:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, filepath)

    def browse_dir(self, entry_widget):
        dirpath = filedialog.askdirectory()
        if dirpath:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, dirpath)

    def save_settings(self, window):
        self.save_config()
        self.update_info_label()
        window.destroy()
        messagebox.showinfo("Успех", "Настройки сохранены!")


if __name__ == "__main__":
    root = tk.Tk()
    app = ObsidianSyncApp(root)
    root.mainloop()