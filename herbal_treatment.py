import tkinter as tk
from tkinter import ttk
import csv
import re
import requests
from PIL import Image, ImageTk
import io
import json
from bs4 import BeautifulSoup
import urllib.parse
import sys

# For copying image to clipboard (Windows only)
import win32clipboard
import win32con


# ---------------- Custom Console Output ---------------- #
class TextRedirector:
    def __init__(self, widget):
        self.widget = widget

    def write(self, s):
        self.widget.insert(tk.END, s)
        self.widget.see(tk.END)
        self.widget.update_idletasks()

    def flush(self):
        pass


# ---------------- Splash Screen ---------------- #
class SplashScreen(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Loading...")
        self.overrideredirect(True)
        width, height = 300, 150
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        label = tk.Label(self, text="Loading, please wait...", font=("Helvetica", 14))
        label.pack(expand=True, fill="both", padx=20, pady=20)
        self.after(500, self.destroy)


# ---------------- Search Engine Functions ---------------- #
def fetch_images_duckduckgo(query, count=4):
    imgs = []
    headers = {"User-Agent": "Mozilla/5.0"}
    params = {'q': query}
    res = requests.get("https://duckduckgo.com/", params=params, headers=headers, timeout=10)
    token_match = re.search(r"vqd=([\d-]+)&", res.text)
    if not token_match:
        token_match = re.search(r"vqd='([\d-]+)'", res.text)
    if not token_match:
        print(f"[DEBUG] DuckDuckGo: vqd token not found for query '{query}'")
        return imgs
    vqd = token_match.group(1)
    search_url = "https://duckduckgo.com/i.js"
    params = {
        "l": "us-en",
        "o": "json",
        "q": query,
        "vqd": vqd,
        "f": "",
        "p": "1"
    }
    while len(imgs) < count:
        print(f"[DEBUG] DuckDuckGo: Requesting search for '{query}'")
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[DEBUG] DuckDuckGo: Non-200 response: {response.status_code}")
            break
        data = response.json()
        results = data.get("results", [])
        if not results:
            break
        for result in results:
            if len(imgs) >= count:
                break
            image_url = result.get("image")
            if not image_url:
                continue
            print(f"[DEBUG] DuckDuckGo: Found image URL: {image_url}")
            try:
                img_response = requests.get(image_url, headers=headers, timeout=10)
                if img_response.status_code == 200:
                    pil_image = Image.open(io.BytesIO(img_response.content))
                    pil_image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(pil_image)
                    imgs.append((photo, pil_image))
            except Exception as e:
                print(f"[DEBUG] DuckDuckGo: Error processing image: {e}")
                continue
        next_url = data.get("next")
        if not next_url:
            break
        if next_url.startswith("/"):
            search_url = "https://duckduckgo.com" + next_url
        else:
            search_url = next_url
    return imgs


def fetch_images_bing(query, count=4):
    imgs = []
    headers = {"User-Agent": "Mozilla/5.0"}
    q = urllib.parse.quote(query)
    search_url = f"https://www.bing.com/images/search?q={q}&qft=+filterui:photo-photo&FORM=HDRSC2"
    print(f"[DEBUG] Bing: Requesting URL: {search_url}")
    response = requests.get(search_url, headers=headers, timeout=10)
    if response.status_code != 200:
        print(f"[DEBUG] Bing: Non-200 response: {response.status_code}")
        return imgs
    soup = BeautifulSoup(response.text, 'html.parser')
    image_elements = soup.find_all("a", class_="iusc")
    for elem in image_elements:
        if len(imgs) >= count:
            break
        m_json = elem.get("m")
        if not m_json:
            continue
        try:
            image_info = json.loads(m_json)
        except Exception:
            continue
        image_url = image_info.get("murl")
        if not image_url:
            continue
        print(f"[DEBUG] Bing: Found image URL: {image_url}")
        try:
            img_response = requests.get(image_url, headers=headers, timeout=10)
            if img_response.status_code == 200:
                pil_image = Image.open(io.BytesIO(img_response.content))
                pil_image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(pil_image)
                imgs.append((photo, pil_image))
        except Exception as e:
            print(f"[DEBUG] Bing: Error processing image: {e}")
            continue
    return imgs


def fetch_images_yandex(query, count=4):
    imgs = []
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://yandex.com/images/search?text={urllib.parse.quote(query)}"
    print(f"[DEBUG] Yandex: Requesting URL: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        print(f"[DEBUG] Yandex: Non-200 response: {response.status_code}")
        return imgs
    soup = BeautifulSoup(response.text, 'html.parser')
    for img_tag in soup.find_all("img"):
        if len(imgs) >= count:
            break
        src = img_tag.get("src") or img_tag.get("data-src")
        if not src or src.startswith("data:"):
            continue
        print(f"[DEBUG] Yandex: Found image URL: {src}")
        try:
            img_response = requests.get(src, headers=headers, timeout=10)
            if img_response.status_code == 200:
                pil_image = Image.open(io.BytesIO(img_response.content))
                pil_image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(pil_image)
                imgs.append((photo, pil_image))
        except Exception as e:
            print(f"[DEBUG] Yandex: Error processing image: {e}")
            continue
    return imgs


def fetch_images_qwant(query, count=4):
    imgs = []
    headers = {"User-Agent": "Mozilla/5.0"}
    search_url = "https://api.qwant.com/api/search/images"
    params = {
        "count": count,
        "q": query,
        "t": "images",
        "safesearch": 1,
        "locale": "en_US",
        "uiv": 4
    }
    print(f"[DEBUG] Qwant: Requesting API for query: {query}")
    response = requests.get(search_url, params=params, headers=headers, timeout=10)
    if response.status_code != 200:
        print(f"[DEBUG] Qwant: Non-200 response: {response.status_code}")
        return imgs
    data = response.json()
    results = data.get("data", {}).get("result", {}).get("items", [])
    for result in results:
        if len(imgs) >= count:
            break
        image_url = result.get("media")
        if not image_url:
            continue
        print(f"[DEBUG] Qwant: Found image URL: {image_url}")
        try:
            img_response = requests.get(image_url, headers=headers, timeout=10)
            if img_response.status_code == 200:
                pil_image = Image.open(io.BytesIO(img_response.content))
                pil_image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(pil_image)
                imgs.append((photo, pil_image))
        except Exception as e:
            print(f"[DEBUG] Qwant: Error processing image: {e}")
            continue
    return imgs


def fetch_images_google(query, count=4):
    imgs = []
    headers = {"User-Agent": "Mozilla/5.0"}
    q = urllib.parse.quote(query)
    url = f"https://www.google.com/search?tbm=isch&q={q}"
    print(f"[DEBUG] Google: Requesting URL: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        print(f"[DEBUG] Google: Non-200 response: {response.status_code}")
        return imgs
    soup = BeautifulSoup(response.text, 'html.parser')
    for img_tag in soup.find_all("img"):
        if len(imgs) >= count:
            break
        src = img_tag.get("src")
        if not src or src.startswith("data:"):
            continue
        print(f"[DEBUG] Google: Found image URL: {src}")
        try:
            img_response = requests.get(src, headers=headers, timeout=10)
            if img_response.status_code == 200:
                pil_image = Image.open(io.BytesIO(img_response.content))
                pil_image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(pil_image)
                imgs.append((photo, pil_image))
        except Exception as e:
            print(f"[DEBUG] Google: Error processing image: {e}")
            continue
    return imgs


def fetch_images_baidu(query, count=4):
    imgs = []
    headers = {"User-Agent": "Mozilla/5.0"}
    q = urllib.parse.quote(query)
    url = f"https://image.baidu.com/search/index?tn=baiduimage&word={q}"
    print(f"[DEBUG] Baidu: Requesting URL: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        print(f"[DEBUG] Baidu: Non-200 response: {response.status_code}")
        return imgs
    soup = BeautifulSoup(response.text, 'html.parser')
    for img_tag in soup.find_all("img"):
        if len(imgs) >= count:
            break
        src = img_tag.get("src") or img_tag.get("data-src")
        if not src or src.startswith("data:"):
            continue
        print(f"[DEBUG] Baidu: Found image URL: {src}")
        try:
            img_response = requests.get(src, headers=headers, timeout=10)
            if img_response.status_code == 200:
                pil_image = Image.open(io.BytesIO(img_response.content))
                pil_image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(pil_image)
                imgs.append((photo, pil_image))
        except Exception as e:
            print(f"[DEBUG] Baidu: Error processing image: {e}")
            continue
    return imgs


# ---------------- Herb/Remedy App ---------------- #
class HerbRemedyApp(tk.Tk):
    def __init__(self, csv_file):
        super().__init__()
        self.csv_file = csv_file
        self.headers = [
            "Herb/Remedy",
            "Category",
            "Indication(s)/Uses",
            "Preparation",
            "Notes/Cautions"
        ]
        self.data = []  # CSV rows as dicts
        self.indications = []  # Unique values for "Indication(s)/Uses"
        self.current_images = []  # List of tuples: (PhotoImage, PIL Image)
        self.load_csv()
        self.create_widgets()
        self.center_window()

    def center_window(self):
        self.update_idletasks()
        width = 1400
        height = 900
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def load_csv(self):
        try:
            with open(self.csv_file, newline='', encoding='cp1252') as csvfile:
                reader = csv.DictReader(csvfile)
                self.data = list(reader)
                unique_indications = set()
                for row in self.data:
                    val = row.get("Indication(s)/Uses", "").strip()
                    if val:
                        unique_indications.add(val)
                self.indications = sorted(list(unique_indications))
        except Exception as e:
            print("Error loading CSV:", e)
            self.data = []
            self.indications = []

    def create_widgets(self):
        self.title("Herb/Remedy CSV Viewer")
        self.geometry("1400x900")
        top_frame = ttk.Frame(self)
        top_frame.pack(pady=5, padx=10, anchor='nw', fill='x')

        # Combobox for selecting Indication(s)/Uses
        ind_label = ttk.Label(top_frame, text="Select Indication(s)/Uses:")
        ind_label.pack(side="left", padx=(0, 10))
        self.combo = ttk.Combobox(top_frame, values=self.indications, state="readonly", width=40)
        self.combo.pack(side="left")
        if self.indications:
            self.combo.current(0)
        self.combo.bind("<<ComboboxSelected>>", self.on_select)

        # New Combobox for selecting Search Engine
        eng_label = ttk.Label(top_frame, text="Select Search Engine:")
        eng_label.pack(side="left", padx=(20, 10))
        search_engines = ["Google", "Bing", "DuckDuckGo", "Qwant", "Baidu", "Yandex"]
        self.engine_combo = ttk.Combobox(top_frame, values=search_engines, state="readonly", width=20)
        self.engine_combo.pack(side="left")
        self.engine_combo.current(search_engines.index("Google"))

        paned = tk.PanedWindow(self, orient="horizontal")
        paned.pack(expand=True, fill="both", padx=10, pady=5)
        left_frame = ttk.Frame(paned, width=300)
        self.text_widget = tk.Text(left_frame, wrap="word")
        self.text_widget.pack(side="left", fill="both", expand=True)
        left_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=left_scrollbar.set)
        left_scrollbar.pack(side="right", fill="y")
        paned.add(left_frame, minsize=300)

        right_frame = ttk.Frame(paned)
        self.image_frame = ttk.Frame(right_frame)
        self.image_frame.pack(expand=True, fill="both", padx=5, pady=5)
        # Label for remedy name
        self.image_name_label = ttk.Label(right_frame, text="", anchor="center", font=("Helvetica", 16, "bold"))
        self.image_name_label.pack(pady=5)
        # Label to show which search engine was used.
        self.engine_label = ttk.Label(right_frame, text="", anchor="center", font=("Helvetica", 12))
        self.engine_label.pack(pady=2)
        paned.add(right_frame)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self.copy_selection)
        self.text_widget.bind("<Button-3>", self.show_context_menu)

        console_frame = ttk.Frame(self)
        console_frame.pack(fill="both", padx=10, pady=(5, 10))
        console_label = ttk.Label(console_frame, text="Console Output:")
        console_label.pack(anchor="w")
        self.console_text = tk.Text(console_frame, wrap="word", height=8, background="black", foreground="white")
        self.console_text.pack(side="left", fill="both", expand=True)
        console_scrollbar = ttk.Scrollbar(console_frame, orient="vertical", command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=console_scrollbar.set)
        console_scrollbar.pack(side="right", fill="y")
        sys.stdout = TextRedirector(self.console_text)
        self.on_select()

    def show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def show_image_context_menu(self, event, pil_image):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Copy Image", command=lambda: self.copy_pil_image(pil_image))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def on_select(self, event=None):
        selected = self.combo.get()
        if not selected:
            filtered = self.data
        else:
            filtered = [row for row in self.data if row.get("Indication(s)/Uses", "").strip() == selected]
        self.update_text_widget(filtered, selected)

    def update_text_widget(self, rows, selected):
        self.text_widget.delete("1.0", tk.END)
        header = f"Indication(s)/Uses: {selected}\n\n" if selected else "Indication(s)/Uses: All\n\n"
        self.text_widget.insert(tk.END, header)
        for i, row in enumerate(rows):
            herb = row.get("Herb/Remedy", "").strip()
            category = row.get("Category", "").strip()
            indications = row.get("Indication(s)/Uses", "").strip()
            preparation = row.get("Preparation", "").strip()
            notes = row.get("Notes/Cautions", "").strip()
            alt_csv = row.get("Alternatives", "").strip() if "Alternatives" in row else ""
            alt_extracted = [m.group(2).strip() for m in re.finditer(r'(Alternatively,?\s*|Or use\s*)([^.;]+)', notes, flags=re.IGNORECASE)]
            notes_clean = re.sub(r'(Alternatively,?\s*|Or use\s*)[^.;]+[.;]?', '', notes, flags=re.IGNORECASE).strip()
            alternatives = []
            if alt_csv:
                alternatives.append(alt_csv)
            alternatives.extend(alt_extracted)
            self.text_widget.insert(tk.END, "Herb/Remedy:\n")
            herb_tag = f"herb_link_{i}"
            self.text_widget.insert(tk.END, f"{herb}\n", herb_tag)
            self.text_widget.tag_configure(herb_tag, foreground="blue", underline=True)
            self.text_widget.tag_bind(herb_tag, "<Enter>", lambda e, tag=herb_tag: self.text_widget.config(cursor="hand2"))
            self.text_widget.tag_bind(herb_tag, "<Leave>", lambda e: self.text_widget.config(cursor=""))
            self.text_widget.tag_bind(herb_tag, "<Button-1>", lambda e, h=herb: self.on_herb_click(h))
            self.text_widget.insert(tk.END, "\n")
            self.text_widget.insert(tk.END, f"Category:\n{category}\n\n")
            self.text_widget.insert(tk.END, "Indication(s)/Uses:\n")
            ind_tag = f"indication_link_{i}"
            self.text_widget.insert(tk.END, f"{indications}\n\n", ind_tag)
            self.text_widget.tag_configure(ind_tag, foreground="blue", underline=True)
            self.text_widget.tag_bind(ind_tag, "<Enter>", lambda e, tag=ind_tag: self.text_widget.config(cursor="hand2"))
            self.text_widget.tag_bind(ind_tag, "<Leave>", lambda e: self.text_widget.config(cursor=""))
            self.text_widget.tag_bind(ind_tag, "<Button-1>", lambda e, ind=indications: self.on_indication_click(ind))
            self.text_widget.insert(tk.END, f"{preparation}\n\n")
            self.text_widget.insert(tk.END, f"Notes/Cautions:\n{notes_clean}\n\n")
            if alternatives:
                self.text_widget.insert(tk.END, "Alternatives:\n")
                for j, alt in enumerate(alternatives):
                    self.text_widget.insert(tk.END, "• ")
                    alt_tag = f"alt_link_{i}_{j}"
                    self.text_widget.insert(tk.END, f"{alt}\n", alt_tag)
                    self.text_widget.tag_configure(alt_tag, foreground="blue", underline=True)
                    self.text_widget.tag_bind(alt_tag, "<Enter>", lambda e, tag=alt_tag: self.text_widget.config(cursor="hand2"))
                    self.text_widget.tag_bind(alt_tag, "<Leave>", lambda e: self.text_widget.config(cursor=""))
                    self.text_widget.tag_bind(alt_tag, "<Button-1>", lambda e, a=alt: self.on_alternative_click(a))
                self.text_widget.insert(tk.END, "\n")
            self.text_widget.insert(tk.END, "-" * 40 + "\n\n")

    def on_herb_click(self, herb):
        print(f"[DEBUG] Herb clicked: {herb}")
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.image_name_label.config(text="")
        self.engine_label.config(text="")
        loading = ttk.Label(self.image_frame, text="Loading images...", anchor="center")
        loading.pack(expand=True, fill="both")
        self.update_idletasks()
        images, engine = self.fetch_images(herb, count=4)
        if images:
            self.display_images(images, herb, engine)
        else:
            for widget in self.image_frame.winfo_children():
                widget.destroy()
            no_label = ttk.Label(self.image_frame, text="No image found", anchor="center")
            no_label.pack(expand=True, fill="both")
            self.image_name_label.config(text=herb)

    def on_indication_click(self, indication):
        print(f"[DEBUG] Indication clicked: {indication}")
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.image_name_label.config(text="")
        self.engine_label.config(text="")
        loading = ttk.Label(self.image_frame, text="Loading images...", anchor="center")
        loading.pack(expand=True, fill="both")
        self.update_idletasks()
        images, engine = self.fetch_images(indication, count=4, search_type="indication")
        if images:
            self.display_images(images, indication, engine)
        else:
            for widget in self.image_frame.winfo_children():
                widget.destroy()
            no_label = ttk.Label(self.image_frame, text="No image found", anchor="center")
            no_label.pack(expand=True, fill="both")
            self.image_name_label.config(text=indication)

    def on_alternative_click(self, alt):
        print(f"[DEBUG] Alternative clicked: {alt}")
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.image_name_label.config(text="")
        self.engine_label.config(text="")
        loading = ttk.Label(self.image_frame, text="Loading images...", anchor="center")
        loading.pack(expand=True, fill="both")
        self.update_idletasks()
        images, engine = self.fetch_images(alt, count=4)
        if images:
            self.display_images(images, alt, engine)
        else:
            for widget in self.image_frame.winfo_children():
                widget.destroy()
            no_label = ttk.Label(self.image_frame, text="No image found", anchor="center")
            no_label.pack(expand=True, fill="both")
            self.image_name_label.config(text=alt)

    def fetch_images(self, query, count=4, search_type="herb"):
        if search_type == "herb":
            refined = f"{query} herb plant photo"
        elif search_type == "indication":
            refined = f"{query} remedy natural medicine"
        else:
            refined = query

        # Use the selected search engine exclusively.
        engine_functions = {
            "Google": fetch_images_google,
            "Bing": fetch_images_bing,
            "DuckDuckGo": fetch_images_duckduckgo,
            "Qwant": fetch_images_qwant,
            "Baidu": fetch_images_baidu,
            "Yandex": fetch_images_yandex
        }
        selected_engine = self.engine_combo.get() or "Google"
        engine_func = engine_functions.get(selected_engine, fetch_images_google)

        try:
            print(f"[DEBUG] Using {selected_engine} with refined query: '{refined}'")
            imgs = engine_func(refined, count)
        except Exception as e:
            print(f"[DEBUG] {selected_engine} exception: {e}")
            imgs = []
        if not imgs:
            print(f"[DEBUG] No images found for refined query '{refined}', trying original query '{query}'")
            try:
                imgs = engine_func(query, count)
            except Exception as e:
                print(f"[DEBUG] {selected_engine} exception on original query: {e}")
                imgs = []
        return imgs, selected_engine

    def display_images(self, images, query, engine):
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.current_images = images
        self.image_name_label.config(text=query)
        self.engine_label.config(text=f"Search Engine: {engine}")
        # Determine scale factor based on the selected engine.
        if engine == "Google":
            scale_factor = 2.0  # 200% for Google
        elif engine == "Bing":
            scale_factor = 0.35  # 35% for Bing
        else:
            scale_factor = 0.25  # 25% for all others
        cols = 2
        for index, (orig_photo, pil_image) in enumerate(images):
            image = pil_image.copy()
            w, h = image.size
            new_size = (max(1, int(w * scale_factor)), max(1, int(h * scale_factor)))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            lbl = ttk.Label(self.image_frame, image=photo)
            lbl.image = photo
            lbl.bind("<Button-3>", lambda e, pil=pil_image: self.show_image_context_menu(e, pil))
            row = index // cols
            col = index % cols
            lbl.grid(row=row, column=col, padx=5, pady=5)

    def copy_pil_image(self, pil_image):
        if not pil_image:
            print("[DEBUG] No image available to copy")
            return
        try:
            output = io.BytesIO()
            pil_image.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]
            output.close()
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_DIB, data)
            win32clipboard.CloseClipboard()
            print("[DEBUG] Image copied to clipboard")
        except Exception as e:
            print(f"[DEBUG] Error copying image: {e}")

    def copy_selection(self, event=None):
        try:
            selection = self.text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.clipboard_clear()
            self.clipboard_append(selection)
        except tk.TclError:
            pass


# ---------------- Main Application ---------------- #
if __name__ == "__main__":
    app = HerbRemedyApp("herbal.csv")
    splash = SplashScreen(app)
    app.withdraw()
    app.after(600, app.deiconify)
    app.mainloop()
