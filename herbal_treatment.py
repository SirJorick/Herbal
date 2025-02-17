import tkinter as tk
from tkinter import ttk, messagebox
import csv
import threading
import requests
from PIL import Image, ImageTk
import io
import urllib.parse  # For URL encoding
from bs4 import BeautifulSoup
import chardet  # For encoding detection
import re

# ---------------- Optional Selenium Imports ---------------- #
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
except ImportError:
    webdriver = None

# ---------------- Splash Screen ---------------- #
class SplashScreen(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Loading...")
        self.overrideredirect(True)  # Remove window decorations
        width, height = 300, 150
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        label = tk.Label(self, text="Loading, please wait...", font=("Helvetica", 14))
        label.pack(expand=True, fill="both", padx=20, pady=20)
        self.after(2000, self.destroy)

# ---------------- Main Application ---------------- #
class HerbApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Herbal Medicine App")
        # Enlarge the main window so the image pane is more spacious.
        self.root.geometry("1500x900")
        self.setup_ui()
        self.herb_data = self.load_csv("herbal.csv")
        self.populate_combobox()
        self.log_event("Application started.")

    def setup_ui(self):
        # Top frame for combobox
        top_frame = tk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        tk.Label(top_frame, text="Select Herb:", font=("Helvetica", 14)).pack(side=tk.LEFT, padx=5)
        self.herb_combo = ttk.Combobox(top_frame, state="readonly", font=("Helvetica", 14))
        self.herb_combo.pack(side=tk.LEFT, padx=5)
        self.herb_combo.bind("<<ComboboxSelected>>", self.on_herb_selected)

        # Main frame split into details (left) and images (right)
        main_frame = tk.Frame(self.root)
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

        # Footer console frame for event logs
        console_frame = tk.Frame(self.root, bd=2, relief=tk.SUNKEN)
        console_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.console_text = tk.Text(console_frame, height=5, state='disabled', font=("Helvetica", 10))
        self.console_text.pack(fill=tk.X)

    def log_event(self, message):
        """Append a message to the console text box."""
        self.console_text.config(state='normal')
        self.console_text.insert(tk.END, message + "\n")
        self.console_text.see(tk.END)
        self.console_text.config(state='disabled')

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

    def populate_combobox(self):
        herbs = [row["name"] for row in self.herb_data]
        self.herb_combo['values'] = herbs
        if herbs:
            self.herb_combo.current(0)
            self.on_herb_selected(None)
            self.log_event("Herb combobox populated.")

    def format_text(self, text):
        """
        Split text into sentences using punctuation and rejoin with newlines.
        """
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return "\n".join(sentence.strip() for sentence in sentences if sentence)

    def on_herb_selected(self, event):
        herb_name = self.herb_combo.get()
        self.detail_text.delete("1.0", tk.END)
        # Clear existing images
        for widget in self.image_frame.winfo_children():
            widget.destroy()

        # Display CSV info and parts
        parts = ""
        details = f"Herb: {herb_name}\n"
        for row in self.herb_data:
            if row["name"].lower() == herb_name.lower():
                parts = row.get("parts", "")
                details += f"Parts used: {parts}\n"
                break
        self.detail_text.insert(tk.END, details)
        self.log_event(f"Herb selected: {herb_name} (Parts: {parts})")

        # Launch threads: DuckDuckGo for web details and Google for images.
        threading.Thread(target=self.fetch_web_details_duckduckgo, args=(herb_name, parts), daemon=True).start()
        threading.Thread(target=self.fetch_images_google, args=(herb_name, parts), daemon=True).start()

    def fetch_html(self, url, headers, force_selenium=False):
        """
        Fetch HTML using requests. If blocked or force_selenium is True, use Selenium.
        """
        if not force_selenium:
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                self.log_event(f"Requests GET {url} returned status code: {resp.status_code}")
                if resp.status_code != 200 or "unusual traffic" in resp.text.lower():
                    raise Exception("Blocked or CAPTCHA detected via requests.")
                return resp.text
            except Exception as e:
                self.log_event(f"Requests failed for URL {url}: {e}. Trying Selenium fallback.")
        if webdriver is None:
            self.log_event("Selenium is not installed. Cannot use fallback.")
            return ""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            html = driver.page_source
            driver.quit()
            return html
        except Exception as se:
            self.log_event("Selenium fallback failed: " + str(se))
            return ""

    # ---------------- DuckDuckGo Web Details Methods ---------------- #
    def _get_duckduckgo_snippets(self, url, headers, force_selenium=False):
        html = self.fetch_html(url, headers, force_selenium=force_selenium)
        if not html:
            return []
        snippets = []
        soup = BeautifulSoup(html, "html.parser")
        # DuckDuckGo's HTML version wraps each result in a <div class="result">
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
        return snippets

    def fetch_web_details_duckduckgo(self, herb_name, parts):
        base_query = herb_name + (" " + parts if parts else "")
        query_str = base_query + " uses"
        query = urllib.parse.quote(query_str)
        url = "https://html.duckduckgo.com/html/?q=" + query
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        self.log_event(f"Fetching web details from DuckDuckGo with query: '{query_str}'")
        snippets = self._get_duckduckgo_snippets(url, headers)
        if not snippets:
            self.log_event("No valid snippets found with requests. Trying forced Selenium for primary query.")
            snippets = self._get_duckduckgo_snippets(url, headers, force_selenium=True)
        if not snippets:
            fallback_query_str = base_query + " medicinal uses"
            fallback_query = urllib.parse.quote(fallback_query_str)
            fallback_url = "https://html.duckduckgo.com/html/?q=" + fallback_query
            self.log_event(f"No valid snippets found. Trying fallback query: '{fallback_query_str}'")
            snippets = self._get_duckduckgo_snippets(fallback_url, headers)
            if not snippets:
                self.log_event("Fallback (medicinal uses) did not return any snippets. Trying forced Selenium for fallback query.")
                snippets = self._get_duckduckgo_snippets(fallback_url, headers, force_selenium=True)

        if snippets:
            formatted_snippets = [self.format_text(snippet) for snippet in snippets]
            details_text = "\n\nWeb Details (DuckDuckGo):\n\n" + "\n\n".join(formatted_snippets)
            self.detail_text.insert(tk.END, details_text)
            self.log_event("Web details fetched successfully from DuckDuckGo.")
        else:
            self.detail_text.insert(tk.END, "\nNo additional web details found from DuckDuckGo.")
            self.log_event("No additional web details found from DuckDuckGo.")

    # ---------------- Google Image Fetching ---------------- #
    def fetch_images_google(self, herb_name, parts):
        query_text = herb_name + (" " + parts if parts else "")
        query = urllib.parse.quote(query_text)
        url = "https://www.google.com/search?tbm=isch&q=" + query
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            self.log_event("Fetching images from Google...")
            html = self.fetch_html(url, headers)
            if not html:
                self.image_frame.after(0, lambda: tk.Label(self.image_frame, text="Error fetching images",
                                                           font=("Helvetica", 14)).pack())
                return

            soup = BeautifulSoup(html, "html.parser")
            img_urls = []
            # Look for image tags; filter out non-result images
            for tag in soup.find_all("img"):
                img_url = tag.get("data-src") or tag.get("src")
                if img_url and img_url.startswith("http") and img_url not in img_urls:
                    img_urls.append(img_url)
                if len(img_urls) >= 9:
                    break

            # Clear existing images
            self.image_frame.after(0, lambda: [w.destroy() for w in self.image_frame.winfo_children()])

            photos = []
            for index, img_url in enumerate(img_urls):
                try:
                    img_resp = requests.get(img_url, headers=headers, timeout=10)
                    image = Image.open(io.BytesIO(img_resp.content))
                    image = image.resize((175, 175))  # Resize image to 175x175 pixels
                    photo = ImageTk.PhotoImage(image)
                    photos.append(photo)

                    def add_image(photo=photo, row=index // 3, col=index % 3, image_url=img_url):
                        container = tk.Frame(self.image_frame, bd=1, relief=tk.RAISED)
                        container.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                        img_label = tk.Label(container, image=photo, cursor="hand2")
                        img_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                        caption_text = f"{self.herb_combo.get()}"
                        if parts:
                            caption_text += f" - {parts}"
                        caption = tk.Label(container, text=caption_text, font=("Helvetica", 12))
                        caption.pack(side=tk.BOTTOM, fill=tk.X)
                        img_label.bind("<Button-1>", lambda e, u=image_url: self.show_image_details(u))
                    self.image_frame.after(0, add_image)
                except Exception as e:
                    self.log_event("Error processing image: " + str(e))
            self.image_frame.photos = photos

            if not img_urls:
                self.image_frame.after(0, lambda: tk.Label(self.image_frame, text="No image available",
                                                           font=("Helvetica", 14)).pack())
            self.log_event("Images fetched successfully from Google.")
        except Exception as e:
            self.image_frame.after(0, lambda: [w.destroy() for w in self.image_frame.winfo_children()])
            self.image_frame.after(0, lambda: tk.Label(self.image_frame, text="Error fetching images",
                                                       font=("Helvetica", 14)).pack())
            self.log_event("Error fetching images from Google: " + str(e))

    def show_image_details(self, image_url):
        details = f"Image URL:\n{image_url}"
        messagebox.showinfo("Image Details", details)
        self.log_event("Image clicked: " + image_url)

# ---------------- Main Execution ---------------- #
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide main window during splash
    splash = SplashScreen(root)
    root.after(2000, lambda: (root.deiconify(), HerbApp(root)))
    root.mainloop()
