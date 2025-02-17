import tkinter as tk
from tkinter import ttk
import csv
import re
import requests
from PIL import Image, ImageTk
import io
import json
from bs4 import BeautifulSoup
import urllib.parse  # For URL encoding
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


# ---------------- Herb/Remedy App ---------------- #
class HerbRemedyApp(tk.Tk):
    def __init__(self, csv_file):
        super().__init__()
        self.csv_file = csv_file
        # Expected CSV headers
        self.headers = [
            "Herb/Remedy",
            "Category",
            "Indication(s)/Uses",
            "Preparation",
            "Notes/Cautions"
        ]
        self.data = []  # List of CSV rows (each row is a dict)
        self.indications = []  # Unique values for "Indication(s)/Uses"
        # List of tuples: (PhotoImage, PIL Image) for currently displayed images.
        self.current_images = []

        self.load_csv()  # Load CSV data
        self.create_widgets()  # Build the main GUI
        self.center_window()  # Center the main window

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
                    value = row.get("Indication(s)/Uses", "").strip()
                    if value:
                        unique_indications.add(value)
                self.indications = sorted(list(unique_indications))
        except Exception as e:
            print("Error loading CSV:", e)
            self.data = []
            self.indications = []

    def create_widgets(self):
        self.title("Herb/Remedy CSV Viewer")
        self.geometry("1400x900")

        # Top frame: Combobox and label.
        top_frame = ttk.Frame(self)
        top_frame.pack(pady=5, padx=10, anchor='nw', fill='x')
        label = ttk.Label(top_frame, text="Select Indication(s)/Uses:")
        label.pack(side="left", padx=(0, 10))
        self.combo = ttk.Combobox(top_frame, values=self.indications, state="readonly", width=80)
        self.combo.pack(side="left")
        if self.indications:
            self.combo.current(0)
        self.combo.bind("<<ComboboxSelected>>", self.on_select)

        # Main Paned Window.
        paned = tk.PanedWindow(self, orient="horizontal")
        paned.pack(expand=True, fill="both", padx=10, pady=5)

        # Left Panel: Text widget with remedy details.
        left_frame = ttk.Frame(paned, width=300)
        self.text_widget = tk.Text(left_frame, wrap="word")
        self.text_widget.pack(side="left", fill="both", expand=True)
        left_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=left_scrollbar.set)
        left_scrollbar.pack(side="right", fill="y")
        paned.add(left_frame, minsize=300)

        # Right Panel: Displaying images and remedy name.
        right_frame = ttk.Frame(paned)
        self.image_frame = ttk.Frame(right_frame)
        self.image_frame.pack(expand=True, fill="both", padx=5, pady=5)
        self.image_name_label = ttk.Label(right_frame, text="", anchor="center", font=("Helvetica", 16, "bold"))
        self.image_name_label.pack(pady=5)
        paned.add(right_frame)

        # Context menu for copying text from the left panel.
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self.copy_selection)
        self.text_widget.bind("<Button-3>", self.show_context_menu)

        # Console panel.
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

        # Initially display rows based on the first combobox selection.
        self.on_select()

    def show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def show_image_context_menu(self, event, pil_image):
        # Create a temporary menu for the image.
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Copy Image", command=lambda: self.copy_pil_image(pil_image))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def on_select(self, event=None):
        selected = self.combo.get()
        # If nothing is selected, show all rows; otherwise, filter by the selected indication.
        if not selected:
            filtered_rows = self.data
        else:
            filtered_rows = [row for row in self.data if row.get("Indication(s)/Uses", "").strip() == selected]
        self.update_text_widget(filtered_rows, selected)

    def update_text_widget(self, rows, selected):
        self.text_widget.delete("1.0", tk.END)
        header = f"Indication(s)/Uses: {selected}\n\n" if selected else "Indication(s)/Uses:\nAll\n\n"
        self.text_widget.insert(tk.END, header)
        for i, row in enumerate(rows):
            herb = row.get("Herb/Remedy", "").strip()
            category = row.get("Category", "").strip()
            indications = row.get("Indication(s)/Uses", "").strip()
            preparation = row.get("Preparation", "").strip()
            notes = row.get("Notes/Cautions", "").strip()
            alt_csv = row.get("Alternatives", "").strip() if "Alternatives" in row else ""
            alt_matches = re.finditer(r'(Alternatively,?\s*|Or use\s*)([^.;]+)', notes, flags=re.IGNORECASE)
            alt_extracted = [match.group(2).strip() for match in alt_matches]
            notes_clean = re.sub(r'(Alternatively,?\s*|Or use\s*)[^.;]+[.;]?', '', notes, flags=re.IGNORECASE).strip()
            alternatives = []
            if alt_csv:
                alternatives.append(alt_csv)
            alternatives.extend(alt_extracted)

            # Herb/Remedy hyperlink.
            self.text_widget.insert(tk.END, "Herb/Remedy:\n")
            herb_tag = f"herb_link_{i}"
            self.text_widget.insert(tk.END, f"{herb}\n", herb_tag)
            self.text_widget.tag_configure(herb_tag, foreground="blue", underline=True)
            self.text_widget.tag_bind(herb_tag, "<Enter>",
                                      lambda e, current_tag=herb_tag: self.text_widget.config(cursor="hand2"))
            self.text_widget.tag_bind(herb_tag, "<Leave>", lambda e: self.text_widget.config(cursor=""))
            self.text_widget.tag_bind(herb_tag, "<Button-1>", lambda e, h=herb: self.on_herb_click(h))
            self.text_widget.insert(tk.END, "\n")
            self.text_widget.insert(tk.END, f"Category:\n{category}\n\n")

            # Indication(s)/Uses hyperlink.
            self.text_widget.insert(tk.END, "Indication(s)/Uses:\n")
            ind_tag = f"indication_link_{i}"
            self.text_widget.insert(tk.END, f"{indications}\n\n", ind_tag)
            self.text_widget.tag_configure(ind_tag, foreground="blue", underline=True)
            self.text_widget.tag_bind(ind_tag, "<Enter>",
                                      lambda e, current_tag=ind_tag: self.text_widget.config(cursor="hand2"))
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
                    self.text_widget.tag_bind(alt_tag, "<Enter>",
                                              lambda e, current_tag=alt_tag: self.text_widget.config(cursor="hand2"))
                    self.text_widget.tag_bind(alt_tag, "<Leave>", lambda e: self.text_widget.config(cursor=""))
                    self.text_widget.tag_bind(alt_tag, "<Button-1>",
                                              lambda e, current_alt=alt: self.on_alternative_click(current_alt))
                self.text_widget.insert(tk.END, "\n")
            self.text_widget.insert(tk.END, "-" * 40 + "\n\n")

    def on_herb_click(self, herb):
        print(f"[DEBUG] Herb hyperlink clicked: {herb}")
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.image_name_label.config(text="")
        loading_label = ttk.Label(self.image_frame, text="Loading images...", anchor="center")
        loading_label.pack(expand=True, fill="both")
        self.update_idletasks()
        images = self.fetch_images(herb, count=4)
        if images:
            self.display_images(images, herb)
        else:
            for widget in self.image_frame.winfo_children():
                widget.destroy()
            no_label = ttk.Label(self.image_frame, text="No image found", anchor="center")
            no_label.pack(expand=True, fill="both")
            self.image_name_label.config(text=herb)

    def on_indication_click(self, indication):
        print(f"[DEBUG] Indication hyperlink clicked: {indication}")
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.image_name_label.config(text="")
        loading_label = ttk.Label(self.image_frame, text="Loading images...", anchor="center")
        loading_label.pack(expand=True, fill="both")
        self.update_idletasks()
        images = self.fetch_images(indication, count=4, search_type="indication")
        if images:
            self.display_images(images, indication)
        else:
            for widget in self.image_frame.winfo_children():
                widget.destroy()
            no_label = ttk.Label(self.image_frame, text="No image found", anchor="center")
            no_label.pack(expand=True, fill="both")
            self.image_name_label.config(text=indication)

    def on_alternative_click(self, alt):
        print(f"[DEBUG] Alternative hyperlink clicked: {alt}")
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.image_name_label.config(text="")
        loading_label = ttk.Label(self.image_frame, text="Loading images...", anchor="center")
        loading_label.pack(expand=True, fill="both")
        self.update_idletasks()
        images = self.fetch_images(alt, count=4)
        if images:
            self.display_images(images, alt)
        else:
            for widget in self.image_frame.winfo_children():
                widget.destroy()
            no_label = ttk.Label(self.image_frame, text="No image found", anchor="center")
            no_label.pack(expand=True, fill="both")
            self.image_name_label.config(text=alt)

    def fetch_images(self, query, count=4, search_type="herb"):
        """
        Fetch up to 'count' images using Bing image search.
        Returns a list of tuples: (PhotoImage, PIL Image)
        The 'search_type' parameter allows us to alter the search query.
        """
        images = []
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            # Refine query based on search type.
            if search_type == "herb":
                refined_query = f"{query} herb plant photo"
            elif search_type == "indication":
                refined_query = f"{query} remedy natural medicine"
            else:
                refined_query = query

            q = urllib.parse.quote(refined_query)
            # Use Bing's photo filter parameter to return only photos.
            search_url = f"https://www.bing.com/images/search?q={q}&qft=+filterui:photo-photo&FORM=HDRSC2"
            print(f"[DEBUG] Requesting Bing search for '{refined_query}' at URL: {search_url}")
            response = requests.get(search_url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"[DEBUG] Bing search response non-200 for '{query}': {response.status_code}")
                return images

            soup = BeautifulSoup(response.text, 'html.parser')
            image_elements = soup.find_all("a", class_="iusc")
            for elem in image_elements:
                if len(images) >= count:
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
                print(f"[DEBUG] Found image URL for '{query}': {image_url}")
                img_response = requests.get(image_url, headers=headers, timeout=10)
                if img_response.status_code == 200:
                    try:
                        pil_image = Image.open(io.BytesIO(img_response.content))
                        pil_image.thumbnail((300, 300), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(pil_image)
                        images.append((photo, pil_image))
                    except Exception as e:
                        print(f"[DEBUG] Error processing image: {e}")
                        continue

            # Fallback: if no images were found with the refined query, try with the original query.
            if not images:
                print("[DEBUG] No images found with refined query, trying fallback query.")
                q_fallback = urllib.parse.quote(query)
                fallback_url = f"https://www.bing.com/images/search?q={q_fallback}&qft=+filterui:photo-photo&FORM=HDRSC2"
                response = requests.get(fallback_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    image_elements = soup.find_all("a", class_="iusc")
                    for elem in image_elements:
                        if len(images) >= count:
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
                        print(f"[DEBUG] Found fallback image URL for '{query}': {image_url}")
                        img_response = requests.get(image_url, headers=headers, timeout=10)
                        if img_response.status_code == 200:
                            try:
                                pil_image = Image.open(io.BytesIO(img_response.content))
                                pil_image.thumbnail((300, 300), Image.Resampling.LANCZOS)
                                photo = ImageTk.PhotoImage(pil_image)
                                images.append((photo, pil_image))
                            except Exception as e:
                                print(f"[DEBUG] Error processing fallback image: {e}")
                                continue
            return images
        except Exception as e:
            print(f"[DEBUG] Error fetching images for '{query}': {e}")
            return images

    def display_images(self, images, query):
        for widget in self.image_frame.winfo_children():
            widget.destroy()
        self.current_images = images
        self.image_name_label.config(text=query)
        cols = 2
        for index, (photo, pil_image) in enumerate(images):
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
