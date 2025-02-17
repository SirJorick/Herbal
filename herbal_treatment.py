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

# ---------------- Optional Selenium Imports ---------------- #
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
except ImportError:
    webdriver = None


# ---------------- Suggestion Fetcher ---------------- #
def get_google_suggestions(query):
    url = "https://suggestqueries.google.com/complete/search?client=firefox&q=" + urllib.parse.quote(query)
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1:
                return data[1]
    except Exception as e:
        return []
    return []


# ---------------- AutocompleteEntry with Floating Toplevel and Modified Focus ---------------- #
class AutocompleteEntry(tk.Entry):
    def __init__(self, master, suggestion_fetcher, **kwargs):
        super().__init__(master, **kwargs)
        self.suggestion_fetcher = suggestion_fetcher
        self.suggestions_window = None  # Toplevel window for suggestions
        self.bind("<KeyRelease>", self.on_keyrelease)
        self.bind("<FocusOut>", self.on_focus_out)
        self.bind("<Return>", self.on_return)

    def on_focus_out(self, event):
        # Delay hiding suggestions to allow listbox click events to process.
        self.after(100, self.hide_suggestions)

    def on_return(self, event):
        # If a suggestion is highlighted, select it.
        if self.suggestions_window and self.suggestions_listbox.curselection():
            index = self.suggestions_listbox.curselection()[0]
            value = self.suggestions_listbox.get(index)
            self.delete(0, tk.END)
            self.insert(0, value)
        self.hide_suggestions()
        # Trigger the search event.
        self.event_generate("<<SearchTriggered>>")

    def on_keyrelease(self, event):
        # Skip navigation keys.
        if event.keysym in ("Return", "Up", "Down"):
            return
        text = self.get()
        if text == "":
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
        # Create a borderless Toplevel window that "floats" over the application.
        self.suggestions_window = tk.Toplevel(self)
        self.suggestions_window.wm_overrideredirect(True)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self.suggestions_window.wm_geometry("+%d+%d" % (x, y))
        self.suggestions_listbox = tk.Listbox(self.suggestions_window, height=min(6, len(suggestions)))
        self.suggestions_listbox.pack()
        # Bind the mouse click event on the listbox items.
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
        self.root.title("General Search and Herbs App")
        self.root.geometry("1500x900")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.herb_tab = HerbTab(self.notebook)
        self.general_tab = GeneralSearchTab(self.notebook)

        self.notebook.add(self.herb_tab.frame, text="Herbs")
        self.notebook.add(self.general_tab.frame, text="General Search")


# ---------------- HerbTab (Existing Functionality) ---------------- #
class HerbTab:
    def __init__(self, parent):
        self.frame = tk.Frame(parent)

        # Top frame with herb selection
        top_frame = tk.Frame(self.frame)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(top_frame, text="Select Herb:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.herb_combo = ttk.Combobox(top_frame, state="readonly", font=("Helvetica", 14))
        self.herb_combo.pack(side=tk.LEFT, padx=5)
        self.herb_combo.bind("<<ComboboxSelected>>", self.on_herb_selected)

        # Create main frame for details and images
        main_frame = tk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=4)
        main_frame.rowconfigure(0, weight=1)

        # Left panel for details
        left_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.detail_text = tk.Text(left_frame, wrap=tk.WORD, font=("Helvetica", 12))
        self.detail_text.pack(fill=tk.BOTH, expand=True)

        # Right panel for images
        right_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        self.image_frame = tk.Frame(right_frame)
        self.image_frame.pack(fill=tk.BOTH, expand=True)

        # Console at bottom -- now create it BEFORE loading CSV
        console_frame = tk.Frame(self.frame, bd=2, relief=tk.SUNKEN)
        console_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.console_text = tk.Text(console_frame, height=5, state="disabled", font=("Helvetica", 10))
        self.console_text.pack(fill=tk.X)

        # Now load CSV after console_text is created
        self.herb_data = self.load_csv("herbal.csv")
        herbs = [row["name"] for row in self.herb_data]
        self.herb_combo['values'] = herbs
        if herbs:
            self.herb_combo.current(0)

        self.log_event("Herb tab loaded.")
        self.on_herb_selected(None)

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

    def fetch_html(self, url, headers, force_selenium=False):
        if not force_selenium:
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                self.log_event(f"Requests GET {url} returned status code: {resp.status_code}")
                if resp.status_code != 200 or "unusual traffic" in resp.text.lower():
                    raise Exception("Blocked or CAPTCHA")
                return resp.text
            except Exception as e:
                self.log_event(f"Requests failed for {url}: {e}. Trying Selenium fallback.")
        if webdriver is None:
            self.log_event("Selenium not installed.")
            return ""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            html = driver.page_source
            driver.quit()
            return html
        except Exception as se:
            self.log_event("Selenium fallback failed: " + str(se))
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

        # Launch threads to fetch details and images (using herb name + parts)
        threading.Thread(target=self.fetch_web_details_duckduckgo, args=(herb_name + " " + parts,), daemon=True).start()
        threading.Thread(target=self.fetch_images_google, args=(herb_name + " " + parts,), daemon=True).start()

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
                snippet = result.find("a", class_="result__snippet")
                if snippet is None:
                    snippet = result.find("div", class_="result__snippet")
                if snippet:
                    text = snippet.get_text().strip()
                    if text and len(text.split()) > 5:
                        snippets.append(text)
                if len(snippets) >= 5:
                    break
        if snippets:
            formatted = "\n\n".join(self.format_text(s) for s in snippets)
            self.detail_text.insert(tk.END, "\n\nWeb Details (DuckDuckGo):\n" + formatted)
            self.log_event("Web details fetched successfully.")
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
        for tag in soup.find_all("img"):
            img_url = tag.get("data-src") or tag.get("src")
            if img_url and img_url.startswith("http") and img_url not in img_urls:
                img_urls.append(img_url)
            if len(img_urls) >= 9:
                break
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        photos = []
        for index, img_url in enumerate(img_urls):
            try:
                img_resp = requests.get(img_url, headers=headers, timeout=10)
                image = Image.open(io.BytesIO(img_resp.content))
                image = image.resize((175, 175))
                photo = ImageTk.PhotoImage(image)
                photos.append(photo)
                container = tk.Frame(self.image_frame, bd=1, relief=tk.RAISED)
                container.grid(row=index // 3, column=index % 3, padx=5, pady=5)
                img_label = tk.Label(container, image=photo, cursor="hand2")
                img_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                caption = tk.Label(container, text=self.herb_combo.get(), font=("Helvetica", 12))
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


# ---------------- GeneralSearchTab (New Functionality) ---------------- #
class GeneralSearchTab:
    def __init__(self, parent):
        self.frame = tk.Frame(parent)
        # Top search frame with auto-suggest entry
        search_frame = tk.Frame(self.frame)
        search_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(search_frame, text="Search:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.search_entry = AutocompleteEntry(search_frame, get_google_suggestions, font=("Helvetica", 14))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        # Bind the custom event from AutocompleteEntry to trigger search on Enter.
        self.search_entry.bind("<<SearchTriggered>>", lambda e: self.on_search())
        self.search_button = tk.Button(search_frame, text="Search", font=("Helvetica", 14), command=self.on_search)
        self.search_button.pack(side=tk.LEFT, padx=5)

        # Main frame split into Details (left) and Images (right)
        main_frame = tk.Frame(self.frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=4)
        main_frame.rowconfigure(0, weight=1)

        # Left panel for details
        left_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.detail_text = tk.Text(left_frame, wrap=tk.WORD, font=("Helvetica", 12))
        self.detail_text.pack(fill=tk.BOTH, expand=True)

        # Right panel for images
        right_frame = tk.Frame(main_frame, bd=2, relief=tk.SUNKEN)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        self.image_frame = tk.Frame(right_frame)
        self.image_frame.pack(fill=tk.BOTH, expand=True)

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

    def fetch_html(self, url, headers, force_selenium=False):
        if not force_selenium:
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                self.log_event(f"Requests GET {url} returned {resp.status_code}")
                if resp.status_code != 200 or "unusual traffic" in resp.text.lower():
                    raise Exception("Blocked or CAPTCHA")
                return resp.text
            except Exception as e:
                self.log_event(f"Requests failed for {url}: {e}. Trying Selenium fallback.")
        if webdriver is None:
            self.log_event("Selenium not installed.")
            return ""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            html = driver.page_source
            driver.quit()
            return html
        except Exception as se:
            self.log_event("Selenium fallback failed: " + str(se))
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
                snippet = result.find("a", class_="result__snippet")
                if snippet is None:
                    snippet = result.find("div", class_="result__snippet")
                if snippet:
                    text = snippet.get_text().strip()
                    if text and len(text.split()) > 5:
                        snippets.append(text)
                if len(snippets) >= 5:
                    break
        if snippets:
            formatted = "\n\n".join(self.format_text(s) for s in snippets)
            self.detail_text.insert(tk.END, "\n\nWeb Details (DuckDuckGo):\n" + formatted)
            self.log_event("Web details fetched successfully.")
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
        for tag in soup.find_all("img"):
            img_url = tag.get("data-src") or tag.get("src")
            if img_url and img_url.startswith("http") and img_url not in img_urls:
                img_urls.append(img_url)
            if len(img_urls) >= 9:
                break
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        photos = []
        for index, img_url in enumerate(img_urls):
            try:
                img_resp = requests.get(img_url, headers=headers, timeout=10)
                image = Image.open(io.BytesIO(img_resp.content))
                image = image.resize((175, 175))
                photo = ImageTk.PhotoImage(image)
                photos.append(photo)
                container = tk.Frame(self.image_frame, bd=1, relief=tk.RAISED)
                container.grid(row=index // 3, column=index % 3, padx=5, pady=5)
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
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()
