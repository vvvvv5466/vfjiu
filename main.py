import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
import os
from datetime import datetime
from threading import Thread

# ---------- Конфигурация ----------
API_URL = "https://api.exchangerate-api.com/v4/latest/"  # Бесплатный API, ключ не требуется
HISTORY_FILE = "conversion_history.json"

# ---------- Загрузка / сохранение истории ----------
def load_history():
    """Загружает историю из JSON-файла, если он существует."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history):
    """Сохраняет историю в JSON-файл."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

# ---------- Функция получения курса (асинхронно) ----------
def fetch_exchange_rate(from_currency, to_currency, callback):
    """
    Запрашивает курс из from_currency в to_currency через API.
    Вызывает callback(rate, error) по завершении.
    """
    def task():
        try:
            response = requests.get(API_URL + from_currency, timeout=10)
            response.raise_for_status()
            data = response.json()
            rate = data["rates"].get(to_currency)
            if rate is None:
                callback(None, f"Валюта {to_currency} не найдена")
            else:
                callback(rate, None)
        except requests.exceptions.RequestException as e:
            callback(None, f"Ошибка сети: {str(e)}")
        except (KeyError, ValueError) as e:
            callback(None, f"Ошибка ответа API: {str(e)}")
    Thread(target=task, daemon=True).start()

# ---------- Основное приложение ----------
class CurrencyConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Currency Converter")
        self.root.geometry("750x500")
        self.root.resizable(True, True)

        # История
        self.history = load_history()

        # Список популярных валют (можно расширить)
        self.currencies = [
            "USD", "EUR", "GBP", "JPY", "CNY", "RUB", "CAD", "AUD",
            "CHF", "INR", "BRL", "ZAR", "TRY", "NZD", "MXN", "KRW"
        ]

        # ---------- Виджеты ----------
        # Верхняя панель: выбор валюты и сумма
        control_frame = ttk.LabelFrame(root, text="Конвертация", padding=10)
        control_frame.pack(fill="x", padx=10, pady=5)

        # Валюта "из"
        ttk.Label(control_frame, text="Из:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.from_currency = ttk.Combobox(control_frame, values=self.currencies, state="readonly", width=10)
        self.from_currency.grid(row=0, column=1, padx=5, pady=5)
        self.from_currency.set("USD")

        # Валюта "в"
        ttk.Label(control_frame, text="В:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.to_currency = ttk.Combobox(control_frame, values=self.currencies, state="readonly", width=10)
        self.to_currency.grid(row=0, column=3, padx=5, pady=5)
        self.to_currency.set("EUR")

        # Сумма
        ttk.Label(control_frame, text="Сумма:").grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self.amount_entry = ttk.Entry(control_frame, width=15)
        self.amount_entry.grid(row=0, column=5, padx=5, pady=5)

        # Кнопка конвертации
        self.convert_btn = ttk.Button(control_frame, text="Конвертировать", command=self.start_conversion)
        self.convert_btn.grid(row=0, column=6, padx=15, pady=5)

        # Результат (отображается временно)
        self.result_label = ttk.Label(control_frame, text="", foreground="blue")
        self.result_label.grid(row=1, column=0, columnspan=7, pady=5)

        # Таблица истории
        history_frame = ttk.LabelFrame(root, text="История конвертаций", padding=10)
        history_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("datetime", "from", "to", "amount", "result", "rate")
        self.tree = ttk.Treeview(history_frame, columns=columns, show="headings", height=12)
        self.tree.heading("datetime", text="Дата/Время")
        self.tree.heading("from", text="Из")
        self.tree.heading("to", text="В")
        self.tree.heading("amount", text="Сумма")
        self.tree.heading("result", text="Результат")
        self.tree.heading("rate", text="Курс")
        self.tree.column("datetime", width=140)
        self.tree.column("from", width=60)
        self.tree.column("to", width=60)
        self.tree.column("amount", width=100)
        self.tree.column("result", width=100)
        self.tree.column("rate", width=100)

        # Скроллбар
        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Кнопки управления историей
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=10, pady=5)

        self.clear_btn = ttk.Button(btn_frame, text="Очистить историю", command=self.clear_history)
        self.clear_btn.pack(side="left", padx=5)

        self.refresh_btn = ttk.Button(btn_frame, text="Обновить таблицу", command=self.refresh_table)
        self.refresh_btn.pack(side="left", padx=5)

        # Заполнить таблицу имеющейся историей
        self.refresh_table()

    # ---------- Валидация суммы ----------
    def validate_amount(self, amount_str):
        """Проверяет, что введено положительное число."""
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError("Сумма должна быть больше нуля")
            return amount
        except ValueError:
            messagebox.showerror("Ошибка ввода", "Введите положительное число (например, 100.50)")
            return None

    # ---------- Конвертация (асинхронная) ----------
    def start_conversion(self):
        """Запускает процесс конвертации (проверка ввода + запрос)."""
        amount = self.validate_amount(self.amount_entry.get())
        if amount is None:
            return

        from_curr = self.from_currency.get()
        to_curr = self.to_currency.get()
        if not from_curr or not to_curr:
            messagebox.showerror("Ошибка", "Выберите валюты")
            return

        # Блокируем кнопку на время запроса
        self.convert_btn.config(state="disabled", text="Загрузка...")
        self.result_label.config(text="Получение курса...")

        fetch_exchange_rate(from_curr, to_curr, lambda rate, error: self.on_rate_received(amount, from_curr, to_curr, rate, error))

    def on_rate_received(self, amount, from_curr, to_curr, rate, error):
        """Callback после получения курса."""
        self.convert_btn.config(state="normal", text="Конвертировать")
        if error:
            self.result_label.config(text="")
            messagebox.showerror("Ошибка API", error)
            return

        # Вычисляем результат
        result = amount * rate
        result_str = f"{result:.4f} {to_curr}"
        # Отображаем результат
        self.result_label.config(text=f"{amount} {from_curr} = {result_str} (курс: {rate:.4f})")

        # Сохраняем в историю
        new_record = {
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from": from_curr,
            "to": to_curr,
            "amount": amount,
            "result": result,
            "rate": rate
        }
        self.history.append(new_record)
        save_history(self.history)

        # Обновляем таблицу
        self.refresh_table()

    # ---------- Работа с историей ----------
    def refresh_table(self):
        """Очищает Treeview и заполняет заново из self.history."""
        for row in self.tree.get_children():
            self.tree.delete(row)
        for record in self.history:
            self.tree.insert("", "end", values=(
                record["datetime"],
                record["from"],
                record["to"],
                f"{record['amount']:.2f}",
                f"{record['result']:.4f}",
                f"{record['rate']:.4f}"
            ))

    def clear_history(self):
        """Очищает историю (после подтверждения пользователя)."""
        if messagebox.askyesno("Подтверждение", "Удалить всю историю конвертаций?"):
            self.history = []
            save_history(self.history)
            self.refresh_table()
            self.result_label.config(text="История очищена")

# ---------- Запуск приложения ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = CurrencyConverterApp(root)
    root.mainloop()

