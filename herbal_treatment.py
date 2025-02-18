import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import csv
from PIL import Image, ImageTk
import io
import urllib.parse
from bs4 import BeautifulSoup
import chardet
import re
import socket
import subprocess
import sys
from deep_translator import GoogleTranslator  # pip install deep-translator

# ---------------- Tor Daemon Helpers ---------------- #
def is_tor_running(port=9050):
    """Check if Tor is running by attempting to connect to the default SOCKS port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except Exception:
        return False

def start_tor_daemon():
    """
    Attempt to start the Tor daemon.
    IMPORTANT: This uses the specified tor.exe path.
    """
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

# ---------------- AutocompleteEntry with Floating Toplevel ---------------- #
class AutocompleteEntry(tk.Entry):
    def __init__(self, master, suggestion_fetcher, **kwargs):
        super().__init__(master, **kwargs)
        self.suggestion_fetcher = suggestion_fetcher
        self.suggestions_window = None
        self.bind("<KeyRelease>", self.on_keyrelease)
        self.bind("<FocusOut>", self.on_focus_out)
        self.bind("<Return>", self.on_return)

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
        self.root.geometry("1600x900")

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

# ---------------- HerbTab ---------------- #
class HerbTab:
    def __init__(self, parent):
        self.frame = tk.Frame(parent)
        # Top panel for herb selection and language translator
        top_frame = tk.Frame(self.frame)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(top_frame, text="Select Herb:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.herb_combo = ttk.Combobox(top_frame, state="readonly", font=("Helvetica", 14))
        self.herb_combo.pack(side=tk.LEFT, padx=5)
        self.herb_combo.bind("<<ComboboxSelected>>", self.on_herb_selected)
        self.go_button = tk.Button(top_frame, text="Go", font=("Helvetica", 14), command=self.on_go_clicked)
        self.go_button.pack(side=tk.LEFT, padx=5)
        # Language translator combobox for HerbTab
        tk.Label(top_frame, text="Language:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.language_combo = ttk.Combobox(top_frame, state="readonly", font=("Helvetica", 14), width=20)
        self.language_combo['values'] = LANGUAGE_LIST
        self.language_combo.set("English")
        self.language_combo.pack(side=tk.LEFT, padx=5)

        # Main frame for details and images
        main_frame = tk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=4)
        main_frame.rowconfigure(0, weight=1)

        # Left panel: Scrollable detail text
        left_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.detail_text = tk.Text(left_frame, wrap=tk.WORD, font=("Helvetica", 12))
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dt_scroll = tk.Scrollbar(left_frame, command=self.detail_text.yview)
        dt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.detail_text.config(yscrollcommand=dt_scroll.set)

        # Right panel for images (scrollable)
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
        self.image_frame.bind("<Configure>", lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all")))

        # Console at bottom (already scrollable)
        console_frame = tk.Frame(self.frame, bd=2, relief=tk.SUNKEN)
        console_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.console_text = tk.Text(console_frame, height=5, state="disabled", font=("Helvetica", 10))
        self.console_text.pack(fill=tk.X)

        self.herb_data = self.load_csv("herbal.csv")
        herbs = [row["name"] for row in self.herb_data]
        self.herb_combo['values'] = herbs
        if herbs:
            self.herb_combo.current(0)
            self.on_herb_selected(None)
        self.log_event("Herb tab loaded.")

    def log_event(self, message):
        self.console_text.config(state="normal")
        self.console_text.insert(tk.END, message + "\n")
        self.console_text.see(tk.END)
        self.console_text.config(state="disabled")

    def load_csv(self, filename):
        data = []
        try:
            with open(filename, 'rb') as f:
                rawdata = f.read()
            encoding = chardet.detect(rawdata).get('encoding', 'utf-8')
            with open(filename, newline="", encoding=encoding, errors='replace') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    data.append(row)
            self.log_event(f"CSV file '{filename}' loaded successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Error loading CSV file: {e}")
            self.log_event(f"Error loading CSV file: {e}")
        return data

    def fetch_html(self, url, headers):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            self.log_event(f"Requests GET {url} returned status code: {resp.status_code}")
            if resp.status_code != 200 or "unusual traffic" in resp.text.lower():
                raise Exception("Blocked or CAPTCHA")
            return resp.text
        except Exception as e:
            self.log_event(f"Requests failed for {url}: {e}.")
            return ""

    def on_herb_selected(self, event):
        herb_name = self.herb_combo.get()
        self.detail_text.delete("1.0", tk.END)
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        parts = ""
        details = f"Herb: {herb_name}\n"
        for row in self.herb_data:
            if row["name"].lower() == herb_name.lower():
                parts = row.get("parts", "")
                details += f"Parts used: {parts}\n"
                break
        self.detail_text.insert(tk.END, details)
        self.log_event(f"Herb selected: {herb_name} (Parts: {parts})")

    def on_go_clicked(self):
        herb_name = self.herb_combo.get()
        parts = ""
        for row in self.herb_data:
            if row["name"].lower() == herb_name.lower():
                parts = row.get("parts", "")
                break
        search_query = herb_name + " " + parts
        self.log_event(f"Manual search initiated for: {search_query}")
        self.detail_text.delete("1.0", tk.END)
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        details = f"Herb: {herb_name}\nParts used: {parts}\n"
        self.detail_text.insert(tk.END, details)
        threading.Thread(target=self.fetch_web_details_duckduckgo, args=(search_query,), daemon=True).start()
        threading.Thread(target=self.fetch_images_google, args=(search_query,), daemon=True).start()

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
            # Use the selected language from the translator combobox
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

# ---------------- DeepLearnTab ---------------- #
class DeepLearnTab:
    def __init__(self, parent):
        self.frame = tk.Frame(parent)
        self.error_notified = False

        # Top panel: Deep search entry and language combobox
        search_frame = tk.Frame(self.frame)
        search_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(search_frame, text="Deep Search:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.search_entry = AutocompleteEntry(search_frame, get_google_suggestions, font=("Helvetica", 14))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind("<<SearchTriggered>>", lambda e: self.on_search())
        self.search_button = tk.Button(search_frame, text="Search", font=("Helvetica", 14), command=self.on_search)
        self.search_button.pack(side=tk.LEFT, padx=5)
        # Language combobox for DeepLearnTab
        tk.Label(search_frame, text="Language:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.language_combo = ttk.Combobox(search_frame, state="readonly", font=("Helvetica", 14), width=20)
        self.language_combo['values'] = LANGUAGE_LIST
        self.language_combo.set("English")
        self.language_combo.pack(side=tk.LEFT, padx=5)

        # Main frame for details and images
        main_frame = tk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=4)
        main_frame.rowconfigure(0, weight=1)

        # Left panel: Scrollable detail text
        left_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.detail_text = tk.Text(left_frame, wrap=tk.WORD, font=("Helvetica", 12))
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dt_scroll = tk.Scrollbar(left_frame, command=self.detail_text.yview)
        dt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.detail_text.config(yscrollcommand=dt_scroll.set)

        # Right panel for images (scrollable)
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
        self.image_frame.bind("<Configure>", lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all")))

        # Console at bottom
        console_frame = tk.Frame(self.frame, bd=2, relief=tk.SUNKEN)
        console_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.console_text = tk.Text(console_frame, height=5, state="disabled", font=("Helvetica", 10))
        self.console_text.pack(fill=tk.X)

        # Base URLs for deep search (using Tor proxy)
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
                self.detail_text.insert(tk.END, "\nDeep search service is currently unavailable. Please try again later.\n")
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
                header = f"\n\nDeep Web Details in {selected_language}:\n"
            else:
                final_snippets = snippets
                header = "\n\nDeep Web Details:\n"
            formatted = "\n\n".join(self.format_text(s) for s in final_snippets)
            self.detail_text.insert(tk.END, header + formatted)
            self.log_event("Deep web details fetched and translated successfully.")
        else:
            if not html:
                self.log_event("No deep web details found due to connection issues.")
            else:
                self.detail_text.insert(tk.END, "\nNo deep web details found.")
                self.log_event("No deep web details found.")

    def fetch_deep_images(self, query):
        query_encoded = urllib.parse.quote(query)
        url = self.deep_images_base_url + query_encoded
        headers = {"User-Agent": "Mozilla/5.0"}
        self.log_event(f"Deep fetching images for: {query}")
        html = self.fetch_html_deep(url, headers)
        if not html:
            self.log_event("Error fetching deep images.")
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
                proxies = {
                    "http": "socks5h://127.0.0.1:9050",
                    "https": "socks5h://127.0.0.1:9050"
                }
                img_resp = requests.get(img_url, headers=headers, proxies=proxies, timeout=20)
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
                self.log_event("Deep image error: " + str(e))
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
        # Language combobox for GeneralSearchTab
        tk.Label(search_frame, text="Language:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.language_combo = ttk.Combobox(search_frame, state="readonly", font=("Helvetica", 14), width=20)
        self.language_combo['values'] = LANGUAGE_LIST
        self.language_combo.set("English")
        self.language_combo.pack(side=tk.LEFT, padx=5)

        # Main frame for details and images
        main_frame = tk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=4)
        main_frame.rowconfigure(0, weight=1)

        # Left panel: Scrollable detail text
        left_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.detail_text = tk.Text(left_frame, wrap=tk.WORD, font=("Helvetica", 12))
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dt_scroll = tk.Scrollbar(left_frame, command=self.detail_text.yview)
        dt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.detail_text.config(yscrollcommand=dt_scroll.set)

        # Right panel for images (scrollable)
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
        self.image_frame.bind("<Configure>", lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all")))

        # Console at bottom
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
