import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import csv
import urllib.parse
import io
import re
import socket
import subprocess
from PIL import Image, ImageTk
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator  # pip install deep-translator

# ---------------- Helper Functions for Context Menu ---------------- #
def copy_selection(widget):
    try:
        selected_text = widget.selection_get()
        widget.clipboard_clear()
        widget.clipboard_append(selected_text)
    except tk.TclError:
        pass

def add_copy_context_menu(widget):
    def show_context(event):
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Copy", command=lambda: copy_selection(widget))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    widget.bind("<Button-3>", show_context)

# ---------------- Tor Daemon Helpers ---------------- #
def is_tor_running(port=9050):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except Exception:
        return False

def start_tor_daemon():
    tor_path = r"C:\Users\user\PycharmProjects\Herbal\tor_4.0.6\tor\tor.exe"
    try:
        subprocess.Popen([tor_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception as e:
        print("Failed to start Tor daemon:", e)
        return False

# ---------------- Suggestion Fetcher ---------------- #
def get_google_suggestions(query):
    url = "https://suggestqueries.google.com/complete/search?client=firefox&q=" + urllib.parse.quote(query)
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1:
                return data[1]
    except Exception:
        return []
    return []

# ---------------- AutocompleteEntry with Right-Click Paste ---------------- #
class AutocompleteEntry(tk.Entry):
    def __init__(self, master, suggestion_fetcher, **kwargs):
        super().__init__(master, **kwargs)
        self.suggestion_fetcher = suggestion_fetcher
        self.suggestions_window = None
        self.bind("<KeyRelease>", self.on_keyrelease)
        self.bind("<FocusOut>", self.on_focus_out)
        self.bind("<Return>", self.on_return)
        # Enable right-click paste in all search bars
        self.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Paste", command=self.paste_from_clipboard)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def paste_from_clipboard(self):
        try:
            text = self.clipboard_get()
            self.insert(tk.INSERT, text)
        except tk.TclError:
            pass

    def on_focus_out(self, event):
        self.after(100, self.hide_suggestions)

    def on_return(self, event):
        if self.suggestions_window and self.suggestions_listbox.curselection():
            index = self.suggestions_listbox.curselection()[0]
            value = self.suggestions_listbox.get(index)
            self.delete(0, tk.END)
            self.insert(0, value)
        self.hide_suggestions()
        self.event_generate("<<SearchTriggered>>")

    def on_keyrelease(self, event):
        if event.keysym in ("Return", "Up", "Down"):
            return
        text = self.get()
        if not text:
            self.hide_suggestions()
            return
        suggestions = self.suggestion_fetcher(text)
        if suggestions:
            self.show_suggestions(suggestions)
        else:
            self.hide_suggestions()

    def show_suggestions(self, suggestions):
        if self.suggestions_window:
            self.suggestions_window.destroy()
        self.suggestions_window = tk.Toplevel(self)
        self.suggestions_window.wm_overrideredirect(True)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self.suggestions_window.wm_geometry("+%d+%d" % (x, y))
        self.suggestions_listbox = tk.Listbox(self.suggestions_window, height=min(6, len(suggestions)))
        self.suggestions_listbox.pack()
        self.suggestions_listbox.bind("<ButtonRelease-1>", self.on_listbox_select)
        for s in suggestions:
            self.suggestions_listbox.insert(tk.END, s)

    def hide_suggestions(self):
        if self.suggestions_window:
            self.suggestions_window.destroy()
            self.suggestions_window = None

    def on_listbox_select(self, event):
        if self.suggestions_listbox:
            selection = self.suggestions_listbox.curselection()
            if selection:
                value = self.suggestions_listbox.get(selection[0])
                self.delete(0, tk.END)
                self.insert(0, value)
                self.hide_suggestions()

# ---------------- Main Application with Notebook ---------------- #
class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("General Search, Deep Learn & Herbs App")
        self.root.geometry("1700x900")
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.herb_tab = HerbTab(self.notebook)
        self.deep_learn_tab = DeepLearnTab(self.notebook)
        self.general_tab = GeneralSearchTab(self.notebook)
        self.notebook.add(self.herb_tab.frame, text="Herbs")
        self.notebook.add(self.deep_learn_tab.frame, text="Deep Learn")
        self.notebook.add(self.general_tab.frame, text="General Search")

# ---------------- Common Language Data ---------------- #
LANGUAGES = {
    "Afrikaans": "af", "Albanian": "sq", "Amharic": "am", "Arabic": "ar", "Armenian": "hy",
    "Azerbaijani": "az", "Basque": "eu", "Belarusian": "be", "Bengali": "bn", "Bosnian": "bs",
    "Bulgarian": "bg", "Catalan": "ca", "Cebuano": "ceb", "Chichewa": "ny", "Chinese (Simplified)": "zh-cn",
    "Chinese (Traditional)": "zh-tw", "Corsican": "co", "Croatian": "hr", "Czech": "cs", "Danish": "da",
    "Dutch": "nl", "English": "en", "Esperanto": "eo", "Estonian": "et", "Filipino": "tl",
    "Finnish": "fi", "French": "fr", "Frisian": "fy", "Galician": "gl", "Georgian": "ka",
    "German": "de", "Greek": "el", "Gujarati": "gu", "Haitian Creole": "ht", "Hausa": "ha",
    "Hawaiian": "haw", "Hebrew": "he", "Hindi": "hi", "Hmong": "hmn", "Hungarian": "hu",
    "Icelandic": "is", "Igbo": "ig", "Indonesian": "id", "Irish": "ga", "Italian": "it",
    "Japanese": "ja", "Javanese": "jw", "Kannada": "kn", "Kazakh": "kk", "Khmer": "km",
    "Kinyarwanda": "rw", "Korean": "ko", "Kurdish (Kurmanji)": "ku", "Kyrgyz": "ky", "Lao": "lo",
    "Latin": "la", "Latvian": "lv", "Lithuanian": "lt", "Luxembourgish": "lb", "Macedonian": "mk",
    "Malagasy": "mg", "Malay": "ms", "Malayalam": "ml", "Maltese": "mt", "Maori": "mi",
    "Marathi": "mr", "Mongolian": "mn", "Myanmar (Burmese)": "my", "Nepali": "ne", "Norwegian": "no",
    "Odia": "or", "Pashto": "ps", "Persian": "fa", "Polish": "pl", "Portuguese": "pt",
    "Punjabi": "pa", "Romanian": "ro", "Russian": "ru", "Samoan": "sm", "Scots Gaelic": "gd",
    "Serbian": "sr", "Sesotho": "st", "Shona": "sn", "Sindhi": "sd", "Sinhala": "si",
    "Slovak": "sk", "Slovenian": "sl", "Somali": "so", "Spanish": "es", "Sundanese": "su",
    "Swahili": "sw", "Swedish": "sv", "Tagalog": "tl", "Tajik": "tg", "Tamil": "ta",
    "Telugu": "te", "Thai": "th", "Turkish": "tr", "Ukrainian": "uk", "Urdu": "ur",
    "Uzbek": "uz", "Vietnamese": "vi", "Welsh": "cy", "Xhosa": "xh", "Yiddish": "yi",
    "Yoruba": "yo", "Zulu": "zu"
}
LANGUAGE_LIST = sorted(LANGUAGES.keys())

# ---------------- HerbTab with Search Bar, Right-Click Copy & Paste ---------------- #
class HerbTab:
    def __init__(self, parent):
        self.frame = tk.Frame(parent)
        # --------- Disease/Illness Selection Panel --------- #
        top_frame = tk.Frame(self.frame, bg="lightgrey")
        top_frame.config(height=112)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        top_frame.pack_propagate(False)
        tk.Label(top_frame, text="Select Disease/Illness:", font=("Helvetica", 14), bg="lightgrey").pack(side=tk.LEFT, padx=5)
        self.disease_combo = ttk.Combobox(top_frame, state="readonly", font=("Helvetica", 14))
        self.disease_combo.pack(side=tk.LEFT, padx=5)
        self.disease_combo.bind("<<ComboboxSelected>>", self.on_disease_selected)
        self.go_button = tk.Button(top_frame, text="Go", font=("Helvetica", 14), command=self.on_go_clicked)
        self.go_button.pack(side=tk.LEFT, padx=5)

        # --------- New Search Bar Panel --------- #
        search_frame = tk.Frame(self.frame, bg="lightgrey")
        search_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0,5))
        tk.Label(search_frame, text="Search:", font=("Helvetica", 14), bg="lightgrey").pack(side=tk.LEFT, padx=5)
        self.search_entry = AutocompleteEntry(search_frame, get_google_suggestions, font=("Helvetica", 14))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind("<<SearchTriggered>>", lambda e: self.on_search())
        self.search_button = tk.Button(search_frame, text="Search", font=("Helvetica", 14), command=self.on_search)
        self.search_button.pack(side=tk.LEFT, padx=5)
        tk.Label(search_frame, text="Language:", font=("Helvetica", 14), bg="lightgrey").pack(side=tk.LEFT, padx=5)
        self.language_combo = ttk.Combobox(search_frame, state="readonly", font=("Helvetica", 14), width=20)
        self.language_combo['values'] = LANGUAGE_LIST
        self.language_combo.set("English")
        self.language_combo.pack(side=tk.LEFT, padx=5)

        # --------- Main Content Panels --------- #
        main_frame = tk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # --- Left Panel (Details & Output) ---
        left_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(0, weight=0)
        left_frame.grid_rowconfigure(1, weight=0)
        left_frame.grid_rowconfigure(2, weight=1)
        self.detail_text = tk.Text(left_frame, wrap=tk.WORD, font=("Helvetica", 12), height=4)
        self.detail_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        add_copy_context_menu(self.detail_text)
        tk.Label(left_frame, text="Output:", font=("Helvetica", 12, "bold")).grid(row=1, column=0, sticky="nw", padx=5, pady=(5, 0))
        self.output_text = tk.Text(left_frame, wrap=tk.WORD, font=("Helvetica", 12))
        self.output_text.grid(row=2, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.output_text.config(state="disabled")
        add_copy_context_menu(self.output_text)

        # --- Right Panel (Images) ---
        right_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        self.image_canvas = tk.Canvas(right_frame)
        self.image_canvas.grid(row=0, column=0, sticky="nsew")
        self.image_frame = tk.Frame(self.image_canvas)
        self.image_canvas.create_window((0, 0), window=self.image_frame, anchor="nw")
        self.image_frame.bind("<Configure>",
                              lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all")))

        # --------- Console (Logs) --------- #
        console_frame = tk.Frame(self.frame, bd=2, relief=tk.SUNKEN)
        console_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.console_text = tk.Text(console_frame, height=5, state="disabled", font=("Helvetica", 10))
        self.console_text.pack(fill=tk.X)

        self.herb_data = self.load_csv("herbal.csv")
        diseases = sorted({row["Disease/Illness"] for row in self.herb_data})
        self.disease_combo['values'] = diseases
        if diseases:
            self.disease_combo.current(0)
            self.on_disease_selected(None)
        self.log_event("Herb tab loaded.")

    def show_output_context_menu(self, event):
        context_menu = tk.Menu(self.output_text, tearoff=0)
        context_menu.add_command(label="Copy", command=lambda: copy_selection(self.output_text))
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def on_search(self):
        query = self.search_entry.get().strip()
        if not query:
            return
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.log_event(f"Herb tab search initiated for: {query}")
        threading.Thread(target=self.update_output_with_details, args=(query,), daemon=True).start()
        threading.Thread(target=self.show_images_grid, args=(query,), daemon=True).start()

    def on_disease_selected(self, event):
        disease = self.disease_combo.get()
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)
        for widget in self.image_frame.winfo_children():
            widget.destroy()

        selected_row = None
        for row in self.herb_data:
            if row["Disease/Illness"].strip().lower() == disease.strip().lower():
                selected_row = row
                break

        if selected_row:
            disease_val = selected_row.get("Disease/Illness", "N/A")
            herb_val = selected_row.get("Herb", "N/A")
            parts_val = selected_row.get("Parts", "N/A")
            self.detail_text.insert(tk.END, "Disease/Illness: ", "label")
            self.detail_text.insert(tk.END, disease_val, "disease")
            self.detail_text.insert(tk.END, "\nHerb: ", "label")
            self.detail_text.insert(tk.END, herb_val, "herb")
            self.detail_text.insert(tk.END, "\nParts: ", "label")
            self.detail_text.insert(tk.END, parts_val, "parts")
            self.detail_text.tag_config("disease", foreground="blue", underline=1)
            self.detail_text.tag_bind("disease", "<Button-1>",
                                        lambda e, val=disease_val: self.handle_field_click("disease", val))
            self.detail_text.tag_config("herb", foreground="blue", underline=1)
            self.detail_text.tag_bind("herb", "<Button-1>",
                                        lambda e, val=herb_val: self.handle_field_click("herb", val))
            self.detail_text.tag_config("parts", foreground="blue", underline=1)
            self.detail_text.tag_bind("parts", "<Button-1>",
                                        lambda e, val=parts_val: self.handle_field_click("parts", val))
            self.detail_text.config(state="disabled")
            details = f"Disease/Illness: {disease_val}\nHerb: {herb_val}\nParts: {parts_val}\n"
            self.output_text.insert(tk.END, details)
            self.log_event(f"Disease selected: {disease_val} (Herb: {herb_val}, Parts: {parts_val})")
            self.handle_field_click("disease", disease_val)
        else:
            self.detail_text.insert(tk.END, "No data found for the selected disease.")
            self.log_event("No data found for the selected disease.")
        self.output_text.config(state="disabled")

    def on_go_clicked(self):
        self.on_disease_selected(None)

    def handle_field_click(self, field, value):
        query_for_details = f"{value} remedy preparation cure"
        self.log_event(f"Searching details for '{value}' (field: {field})")
        threading.Thread(target=self.update_output_with_details, args=(query_for_details,), daemon=True).start()
        threading.Thread(target=self.show_images_grid, args=(value,), daemon=True).start()

    def fetch_details_from_duckduckgo(self, query):
        query_encoded = urllib.parse.quote(query)
        url = "https://html.duckduckgo.com/html/?q=" + query_encoded
        headers = {"User-Agent": "Mozilla/5.0"}
        self.log_event(f"Fetching details for: {query}")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                raise Exception("Request failed")
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            snippets = []
            for result in soup.find_all("div", class_="result"):
                snippet = result.find("a", class_="result__snippet") or result.find("div", class_="result__snippet")
                if snippet:
                    text = snippet.get_text().strip()
                    if text and len(text.split()) > 5:
                        snippets.append(text)
                if len(snippets) >= 5:
                    break
            details = "\n\n".join(snippets)
            return details
        except Exception as e:
            self.log_event(f"Error fetching details: {e}")
            return None

    def update_output_with_details(self, query):
        details = self.fetch_details_from_duckduckgo(query)
        if details:
            if hasattr(self, "language_combo"):
                selected_language = self.language_combo.get() if self.language_combo.get() else "English"
                lang_code = LANGUAGES.get(selected_language, "en")
                if lang_code != "en":
                    try:
                        details = GoogleTranslator(source='auto', target=lang_code).translate(details)
                        details = f"\n\nAdditional Details (in {selected_language}):\n" + details
                    except Exception as e:
                        self.log_event("Translation error: " + str(e))
                        details = "\n\nAdditional Details:\n" + details
                else:
                    details = "\n\nAdditional Details:\n" + details
            else:
                details = "\n\nAdditional Details:\n" + details
            self.output_text.after(0, lambda: self.append_details_to_output(details))

    def append_details_to_output(self, details):
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, details)
        self.output_text.config(state="disabled")

    def show_images_grid(self, query):
        url = "https://www.google.com/search?tbm=isch&q=" + urllib.parse.quote(query)
        headers = {"User-Agent": "Mozilla/5.0"}
        self.log_event(f"Fetching images for: {query}")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                raise Exception("Image search failed")
            soup = BeautifulSoup(response.text, "html.parser")
            img_urls = []
            for tag in soup.find_all("img"):
                src = tag.get("data-src") or tag.get("src")
                if src and src.startswith("http") and src not in img_urls:
                    img_urls.append(src)
                if len(img_urls) >= 9:
                    break
            for widget in self.image_frame.winfo_children():
                widget.destroy()
            photos = []
            columns = 3
            for index, img_url in enumerate(img_urls):
                try:
                    img_resp = requests.get(img_url, headers=headers, timeout=10)
                    image = Image.open(io.BytesIO(img_resp.content))
                    image = image.resize((200, 200))
                    photo = ImageTk.PhotoImage(image)
                    photos.append(photo)
                    container = tk.Frame(self.image_frame, bd=1, relief=tk.RAISED)
                    container.grid(row=index // columns, column=index % columns, padx=5, pady=5)
                    img_label = tk.Label(container, image=photo, cursor="hand2")
                    img_label.pack()
                    img_label.bind("<Button-1>", lambda e, url=img_url: self.on_image_click(url))
                except Exception as e:
                    self.log_event(f"Error loading image from URL {img_url}: {e}")
            self.image_frame.photos = photos  # Prevent garbage collection.
        except Exception as e:
            self.log_event(f"Error fetching images for '{query}': {e}")
            messagebox.showerror("Image Error", f"Could not fetch images for '{query}'.")

    def on_image_click(self, url):
        messagebox.showinfo("Image Details", f"Image URL:\n{url}")
        self.log_event("Image clicked: " + url)

    def load_csv(self, filename):
        data = []
        try:
            with open(filename, newline="", encoding="utf-8-sig", errors='replace') as csvfile:
                sample = csvfile.read(1024)
                csvfile.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except Exception:
                    dialect = csv.excel
                    dialect.delimiter = "\t"
                reader = csv.DictReader(csvfile, dialect=dialect)
                for row in reader:
                    cleaned_row = {k.strip(): v for k, v in row.items()}
                    data.append(cleaned_row)
            if data:
                print("CSV keys:", data[0].keys())
            self.log_event(f"CSV file '{filename}' loaded successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Error loading CSV file: {e}")
            self.log_event(f"Error loading CSV file: {e}")
        return data

    def log_event(self, message):
        self.console_text.config(state="normal")
        self.console_text.insert(tk.END, message + "\n")
        self.console_text.see(tk.END)
        self.console_text.config(state="disabled")

# ---------------- DeepLearnTab ---------------- #
class DeepLearnTab:
    def __init__(self, parent):
        self.frame = tk.Frame(parent)
        self.error_notified = False
        search_frame = tk.Frame(self.frame)
        search_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(search_frame, text="Deep Search:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.search_entry = AutocompleteEntry(search_frame, get_google_suggestions, font=("Helvetica", 14))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind("<<SearchTriggered>>", lambda e: self.on_search())
        self.search_button = tk.Button(search_frame, text="Search", font=("Helvetica", 14), command=self.on_search)
        self.search_button.pack(side=tk.LEFT, padx=5)
        tk.Label(search_frame, text="Language:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.language_combo = ttk.Combobox(search_frame, state="readonly", font=("Helvetica", 14), width=20)
        self.language_combo['values'] = LANGUAGE_LIST
        self.language_combo.set("English")
        self.language_combo.pack(side=tk.LEFT, padx=5)
        main_frame = tk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=4)
        main_frame.rowconfigure(0, weight=1)
        left_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.detail_text = tk.Text(left_frame, wrap=tk.WORD, font=("Helvetica", 12))
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dt_scroll = tk.Scrollbar(left_frame, command=self.detail_text.yview)
        dt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.detail_text.config(yscrollcommand=dt_scroll.set)
        add_copy_context_menu(self.detail_text)
        right_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        self.image_canvas = tk.Canvas(right_frame)
        self.image_canvas.grid(row=0, column=0, sticky="nsew")
        img_scroll = tk.Scrollbar(right_frame, orient="vertical", command=self.image_canvas.yview)
        img_scroll.grid(row=0, column=1, sticky="ns")
        self.image_canvas.configure(yscrollcommand=img_scroll.set)
        self.image_frame = tk.Frame(self.image_canvas)
        self.image_canvas.create_window((0, 0), window=self.image_frame, anchor="nw")
        self.image_frame.bind("<Configure>",
                              lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all")))
        console_frame = tk.Frame(self.frame, bd=2, relief=tk.SUNKEN)
        console_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.console_text = tk.Text(console_frame, height=5, state="disabled", font=("Helvetica", 10))
        self.console_text.pack(fill=tk.X)
        self.deep_details_base_url = "https://html.duckduckgo.com/html/?q="
        self.deep_images_base_url = "https://www.google.com/search?tbm=isch&q="

    def log_event(self, message):
        self.console_text.config(state="normal")
        self.console_text.insert(tk.END, message + "\n")
        self.console_text.see(tk.END)
        self.console_text.config(state="disabled")

    def fetch_html_deep(self, url, headers):
        proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050"
        }
        try:
            resp = requests.get(url, headers=headers, proxies=proxies, timeout=20)
            self.log_event(f"Deep request GET {url} returned {resp.status_code}")
            if resp.status_code != 200:
                raise Exception("Non-200 status code")
            return resp.text
        except Exception as e:
            self.log_event(f"Deep request failed for {url}: {str(e)}")
            if not self.error_notified:
                self.detail_text.insert(tk.END,
                                        "\nDeep search service is currently unavailable. Please try again later.\n")
                self.error_notified = True
            return ""

    def on_search(self):
        query = self.search_entry.get().strip()
        if not query:
            return
        self.detail_text.delete("1.0", tk.END)
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.log_event(f"Deep search initiated for: {query}")
        threading.Thread(target=self.fetch_deep_web_details, args=(query,), daemon=True).start()
        threading.Thread(target=self.fetch_deep_images, args=(query,), daemon=True).start()

    def fetch_deep_web_details(self, query):
        query_str = query + " uses"
        query_encoded = urllib.parse.quote(query_str)
        url = self.deep_details_base_url + query_encoded
        headers = {"User-Agent": "Mozilla/5.0"}
        self.log_event(f"Deep fetching details: {query_str}")
        html = self.fetch_html_deep(url, headers)
        snippets = []
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for result in soup.find_all("div", class_="result"):
                snippet = result.find("a", class_="result__snippet") or result.find("div", class_="result__snippet")
                if snippet:
                    text = snippet.get_text().strip()
                    if text and len(text.split()) > 5:
                        snippets.append(text)
                if len(snippets) >= 5:
                    break
        if snippets:
            selected_language = self.language_combo.get() if self.language_combo.get() else "English"
            lang_code = LANGUAGES.get(selected_language, "en")
            if lang_code != "en":
                translated_snippets = []
                for s in snippets:
                    try:
                        translation = GoogleTranslator(source='auto', target=lang_code).translate(s)
                        translated_snippets.append(translation)
                    except Exception as e:
                        self.log_event("Translation error: " + str(e))
                        translated_snippets.append(s)
                final_snippets = translated_snippets
                header = f"\n\nWeb Details (DuckDuckGo) in {selected_language}:\n"
            else:
                final_snippets = snippets
                header = "\n\nWeb Details (DuckDuckGo):\n"
            formatted = "\n\n".join(self.format_text(s) for s in final_snippets)
            self.detail_text.insert(tk.END, header + formatted)
            self.log_event("Web details fetched and translated successfully.")
        else:
            self.detail_text.insert(tk.END, "\nNo additional web details found.")
            self.log_event("No web details found.")

    def fetch_deep_images(self, query):
        query_encoded = urllib.parse.quote(query)
        url = self.deep_images_base_url + query_encoded
        headers = {"User-Agent": "Mozilla/5.0"}
        self.log_event(f"Deep fetching images for: {query}")
        html = self.fetch_html_deep(url, headers)
        if not html:
            self.log_event("Error fetching images.")
            return
        soup = BeautifulSoup(html, "html.parser")
        img_urls = []
        max_images = 20
        for tag in soup.find_all("img"):
            img_url = tag.get("data-src") or tag.get("src")
            if img_url and img_url.startswith("http") and img_url not in img_urls:
                img_urls.append(img_url)
            if len(img_urls) >= max_images:
                break
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        photos = []
        columns = 4
        for index, img_url in enumerate(img_urls):
            try:
                img_resp = requests.get(img_url, headers=headers, timeout=10)
                image = Image.open(io.BytesIO(img_resp.content))
                image = image.resize((175, 175))
                photo = ImageTk.PhotoImage(image)
                photos.append(photo)
                container = tk.Frame(self.image_frame, bd=1, relief=tk.RAISED)
                container.grid(row=index // columns, column=index % columns, padx=5, pady=5)
                img_label = tk.Label(container, image=photo, cursor="hand2")
                img_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                caption = tk.Label(container, text=query, font=("Helvetica", 12))
                caption.pack(side=tk.BOTTOM, fill=tk.X)
                img_label.bind("<Button-1>", lambda e, url=img_url: self.on_image_click(url))
            except Exception as e:
                self.log_event("Image error: " + str(e))
        self.image_frame.photos = photos

    def format_text(self, text):
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return "\n".join(sentence.strip() for sentence in sentences if sentence)

    def on_image_click(self, url):
        messagebox.showinfo("Deep Image Details", f"Image URL:\n{url}")
        self.log_event("Deep image clicked: " + url)

# ---------------- GeneralSearchTab ---------------- #
class GeneralSearchTab:
    def __init__(self, parent):
        self.frame = tk.Frame(parent)
        search_frame = tk.Frame(self.frame)
        search_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(search_frame, text="Search:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.search_entry = AutocompleteEntry(search_frame, get_google_suggestions, font=("Helvetica", 14))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind("<<SearchTriggered>>", lambda e: self.on_search())
        self.search_button = tk.Button(search_frame, text="Search", font=("Helvetica", 14), command=self.on_search)
        self.search_button.pack(side=tk.LEFT, padx=5)
        tk.Label(search_frame, text="Language:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.language_combo = ttk.Combobox(search_frame, state="readonly", font=("Helvetica", 14), width=20)
        self.language_combo['values'] = LANGUAGE_LIST
        self.language_combo.set("English")
        self.language_combo.pack(side=tk.LEFT, padx=5)
        main_frame = tk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=4)
        main_frame.rowconfigure(0, weight=1)
        left_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.detail_text = tk.Text(left_frame, wrap=tk.WORD, font=("Helvetica", 12))
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dt_scroll = tk.Scrollbar(left_frame, command=self.detail_text.yview)
        dt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.detail_text.config(yscrollcommand=dt_scroll.set)
        add_copy_context_menu(self.detail_text)
        right_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        self.image_canvas = tk.Canvas(right_frame)
        self.image_canvas.grid(row=0, column=0, sticky="nsew")
        img_scroll = tk.Scrollbar(right_frame, orient="vertical", command=self.image_canvas.yview)
        img_scroll.grid(row=0, column=1, sticky="ns")
        self.image_canvas.configure(yscrollcommand=img_scroll.set)
        self.image_frame = tk.Frame(self.image_canvas)
        self.image_canvas.create_window((0, 0), window=self.image_frame, anchor="nw")
        self.image_frame.bind("<Configure>",
                              lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all")))
        console_frame = tk.Frame(self.frame, bd=2, relief=tk.SUNKEN)
        console_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.console_text = tk.Text(console_frame, height=5, state="disabled", font=("Helvetica", 10))
        self.console_text.pack(fill=tk.X)

    def log_event(self, message):
        self.console_text.config(state="normal")
        self.console_text.insert(tk.END, message + "\n")
        self.console_text.see(tk.END)
        self.console_text.config(state="disabled")

    def fetch_html(self, url, headers):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            self.log_event(f"Requests GET {url} returned {resp.status_code}")
            if resp.status_code != 200 or "unusual traffic" in resp.text.lower():
                raise Exception("Blocked or CAPTCHA")
            return resp.text
        except Exception as e:
            self.log_event(f"Requests failed for {url}: {e}.")
            return ""

    def on_search(self):
        query = self.search_entry.get().strip()
        if not query:
            return
        self.detail_text.delete("1.0", tk.END)
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.log_event(f"General search initiated for: {query}")
        threading.Thread(target=self.fetch_web_details_duckduckgo, args=(query,), daemon=True).start()
        threading.Thread(target=self.fetch_images_google, args=(query,), daemon=True).start()

    def fetch_web_details_duckduckgo(self, query):
        query_str = query + " uses"
        query_encoded = urllib.parse.quote(query_str)
        url = "https://html.duckduckgo.com/html/?q=" + query_encoded
        headers = {"User-Agent": "Mozilla/5.0"}
        self.log_event(f"Fetching details from DuckDuckGo: {query_str}")
        html = self.fetch_html(url, headers)
        snippets = []
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for result in soup.find_all("div", class_="result"):
                snippet = result.find("a", class_="result__snippet") or result.find("div", class_="result__snippet")
                if snippet:
                    text = snippet.get_text().strip()
                    if text and len(text.split()) > 5:
                        snippets.append(text)
                if len(snippets) >= 5:
                    break
        if snippets:
            selected_language = self.language_combo.get() if self.language_combo.get() else "English"
            lang_code = LANGUAGES.get(selected_language, "en")
            if lang_code != "en":
                translated_snippets = []
                for s in snippets:
                    try:
                        translation = GoogleTranslator(source='auto', target=lang_code).translate(s)
                        translated_snippets.append(translation)
                    except Exception as e:
                        self.log_event("Translation error: " + str(e))
                        translated_snippets.append(s)
                final_snippets = translated_snippets
                header = f"\n\nWeb Details (DuckDuckGo) in {selected_language}:\n"
            else:
                final_snippets = snippets
                header = "\n\nWeb Details (DuckDuckGo):\n"
            formatted = "\n\n".join(self.format_text(s) for s in final_snippets)
            self.detail_text.insert(tk.END, header + formatted)
            self.log_event("Web details fetched and translated successfully.")
        else:
            self.detail_text.insert(tk.END, "\nNo additional web details found.")
            self.log_event("No web details found.")

    def fetch_images_google(self, query):
        query_encoded = urllib.parse.quote(query)
        url = "https://www.google.com/search?tbm=isch&q=" + query_encoded
        headers = {"User-Agent": "Mozilla/5.0"}
        self.log_event(f"Fetching images from Google for: {query}")
        html = self.fetch_html(url, headers)
        if not html:
            self.log_event("Error fetching images.")
            return
        soup = BeautifulSoup(html, "html.parser")
        img_urls = []
        max_images = 20
        for tag in soup.find_all("img"):
            img_url = tag.get("data-src") or tag.get("src")
            if img_url and img_url.startswith("http") and img_url not in img_urls:
                img_urls.append(img_url)
            if len(img_urls) >= max_images:
                break
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        photos = []
        columns = 4
        for index, img_url in enumerate(img_urls):
            try:
                img_resp = requests.get(img_url, headers=headers, timeout=10)
                image = Image.open(io.BytesIO(img_resp.content))
                image = image.resize((175, 175))
                photo = ImageTk.PhotoImage(image)
                photos.append(photo)
                container = tk.Frame(self.image_frame, bd=1, relief=tk.RAISED)
                container.grid(row=index // columns, column=index % columns, padx=5, pady=5)
                img_label = tk.Label(container, image=photo, cursor="hand2")
                img_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                caption = tk.Label(container, text=query, font=("Helvetica", 12))
                caption.pack(side=tk.BOTTOM, fill=tk.X)
                img_label.bind("<Button-1>", lambda e, url=img_url: self.on_image_click(url))
            except Exception as e:
                self.log_event("Image error: " + str(e))
        self.image_frame.photos = photos

    def format_text(self, text):
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return "\n".join(sentence.strip() for sentence in sentences if sentence)

    def on_image_click(self, url):
        messagebox.showinfo("Image Details", f"Image URL:\n{url}")
        self.log_event("Image clicked: " + url)

# ---------------- Main Execution ---------------- #
if __name__ == "__main__":
    if not is_tor_running():
        print("Tor is not running. Attempting to start Tor daemon...")
        if start_tor_daemon():
            print("Tor daemon started.")
        else:
            print("Could not start Tor daemon. Deep search functionality may not work.")
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()
