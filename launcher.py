import os
import sys

# Путь к папке с exe (на флешке или компьютере)
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))

# Загружаем .env из той же папки
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    from dotenv import load_dotenv
    load_dotenv(env_path)
else:
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Ошибка", f"Файл .env не найден!\nПоложи .env рядом с программой:\n{BASE_DIR}")
    sys.exit(1)

# Запускаем бота
from bot.main import main

if __name__ == "__main__":
    main()
