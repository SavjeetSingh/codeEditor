import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import jedi
import idlelib.colorizer as ic
import idlelib.percolator as ip

class AutoCompletePopup(tk.Toplevel):
    def __init__(self, parent, suggestions, insert_callback):
        super().__init__(parent)
        self.insert_callback = insert_callback
        self.listbox = tk.Listbox(self, font=("Consolas", 12), activestyle="dotbox")
        self.listbox.pack(fill=tk.BOTH, expand=1)
        self.geometry("+{}+{}".format(parent.winfo_rootx() + 100, parent.winfo_rooty() + 100))
        self.listbox.insert(tk.END, *suggestions)
        self.listbox.focus()
        self.listbox.bind("<Return>", self.select)
        self.listbox.bind("<Double-Button-1>", self.select)
        self.listbox.bind("<Escape>", lambda e: self.destroy())

    def select(self, event):
        selection = self.listbox.get(self.listbox.curselection())
        self.insert_callback(selection)
        self.destroy()

class PythonCodeEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Code Editor with Tabs")
        self.root.geometry("1000x700")
        self.current_theme = "light"
        self.themes = {
            "light": {"editor_bg": "white", "editor_fg": "black", "line_bg": "#f0f0f0", "line_fg": "gray", "output_bg": "black", "output_fg": "white"},
            "dark": {"editor_bg": "#1e1e1e", "editor_fg": "#d4d4d4", "line_bg": "#2a2a2a", "line_fg": "#888", "output_bg": "#000000", "output_fg": "#00ff00"},
        }
        self.tabs = {}
        self.setup_ui()

    def setup_ui(self):
        # Menubar
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Tab", command=self.new_tab)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label="Run", command=self.run_code)
        menubar.add_cascade(label="Run", menu=run_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Theme", command=self.toggle_theme)
        menubar.add_cascade(label="View", menu=view_menu)

        self.root.config(menu=menubar)

        # Tabbed editor
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=1)

        # Output area
        self.output_area = tk.Text(self.root, height=10, font=("Consolas", 12))
        self.output_area.pack(fill=tk.X)
        self.output_area.insert(tk.END, "Output will appear here...\n")

        self.new_tab()  # start with one tab
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Format Code", command=self.format_code)
        menubar.add_cascade(label="Tools", menu=tools_menu)

    def new_tab(self, content=""):
        frame = tk.Frame(self.notebook)
        frame.pack(fill=tk.BOTH, expand=1)

        line_canvas = tk.Canvas(frame, width=40)
        line_canvas.pack(side=tk.LEFT, fill=tk.Y)

        text_area = tk.Text(frame, font=("Consolas", 14), undo=True, wrap="none")
        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        text_area.insert("1.0", content)

        scroll = tk.Scrollbar(frame, command=text_area.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text_area.config(yscrollcommand=scroll.set)

        ip.Percolator(text_area).insertfilter(ic.ColorDelegator())

        # Bindings for line number + autocomplete
        text_area.bind("<KeyRelease>", lambda e: self.update_line_numbers(text_area, line_canvas))
        text_area.bind("<MouseWheel>", lambda e: self.update_line_numbers(text_area, line_canvas))
        text_area.bind("<Button-1>", lambda e: self.update_line_numbers(text_area, line_canvas))
        text_area.bind("<Return>", lambda e: self.update_line_numbers(text_area, line_canvas))
        text_area.bind("<BackSpace>", lambda e: self.update_line_numbers(text_area, line_canvas))
        text_area.bind("<Control-space>", lambda e: self.show_autocomplete(text_area))

        tab_id = f"Tab {len(self.tabs) + 1}"
        self.notebook.add(frame, text=tab_id)
        self.tabs[frame] = {
            "text": text_area,
            "line": line_canvas,
            "file": None
        }
        self.notebook.select(frame)
        self.apply_theme()

    def get_current_tab(self):
        tab = self.notebook.select()
        return self.notebook.nametowidget(tab) if tab else None

    def get_tab_info(self):
        tab = self.get_current_tab()
        return self.tabs.get(tab) if tab else None

    def open_file(self):
        file_path = filedialog.askopenfilename(defaultextension=".py",
                                               filetypes=[("Python Files", "*.py"), ("All Files", "*.*")])
        if file_path:
            with open(file_path, "r") as f:
                content = f.read()
            self.new_tab(content)
            tab_info = self.get_tab_info()
            tab_info["file"] = file_path
            self.notebook.tab(self.get_current_tab(), text=os.path.basename(file_path))

    def save_file(self):
        tab_info = self.get_tab_info()
        if tab_info:
            file_path = tab_info["file"]
            if not file_path:
                file_path = filedialog.asksaveasfilename(defaultextension=".py",
                                                         filetypes=[("Python Files", "*.py"), ("All Files", "*.*")])
                tab_info["file"] = file_path
                if file_path:
                    self.notebook.tab(self.get_current_tab(), text=os.path.basename(file_path))
            if file_path:
                with open(file_path, "w") as f:
                    code = tab_info["text"].get("1.0", tk.END)
                    f.write(code)

    def update_line_numbers(self, text_area, line_canvas):
        line_canvas.delete("all")
        i = text_area.index("@0,0")
        theme = self.themes[self.current_theme]
        while True:
            dline = text_area.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            line_canvas.create_text(2, y, anchor="nw", text=linenum,
                                    font=("Consolas", 12), fill=theme["line_fg"])
            i = text_area.index(f"{i}+1line")

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()

    def apply_theme(self):
        theme = self.themes[self.current_theme]
        for tab in self.tabs:
            info = self.tabs[tab]
            info["text"].config(bg=theme["editor_bg"], fg=theme["editor_fg"], insertbackground=theme["editor_fg"])
            info["line"].config(bg=theme["line_bg"])
        self.output_area.config(bg=theme["output_bg"], fg=theme["output_fg"], insertbackground=theme["output_fg"])

    def run_code(self):
        tab_info = self.get_tab_info()
        if not tab_info:
            return
        code = tab_info["text"].get("1.0", tk.END)
        file_path = tab_info["file"]

        if not file_path:
            file_path = filedialog.asksaveasfilename(defaultextension=".py")
            if not file_path:
                return
            tab_info["file"] = file_path
            self.notebook.tab(self.get_current_tab(), text=os.path.basename(file_path))
            with open(file_path, "w") as f:
                f.write(code)

        try:
            output = subprocess.check_output(["python", file_path], stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError as e:
            output = e.output

        self.output_area.delete("1.0", tk.END)
        self.output_area.insert(tk.END, output)

    def show_autocomplete(self, text_widget):
        code = text_widget.get("1.0", tk.END)
        index = text_widget.index(tk.INSERT)
        row, col = map(int, index.split('.'))
        script = jedi.Script(code, path="dummy.py")
        try:
            completions = script.complete(line=row, column=col)
            if completions:
                suggestions = [c.name for c in completions]
                AutoCompletePopup(self.root, suggestions, lambda s: text_widget.insert(tk.INSERT, s[len(s.split('.')[-1]):]))
        except Exception as e:
            print("Autocomplete error:", e)

    def format_code(self):
        tab_info = self.get_tab_info()
        if not tab_info:
            return

        code = tab_info["text"].get("1.0", tk.END)
        try:
            import black
            mode = black.Mode()
            formatted_code = black.format_str(code, mode=mode)
            tab_info["text"].delete("1.0", tk.END)
            tab_info["text"].insert("1.0", formatted_code)
            self.update_line_numbers(tab_info["text"], tab_info["line"])
            messagebox.showinfo("Format Code", "Code formatted successfully!")
        except Exception as e:
            messagebox.showerror("Format Code Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = PythonCodeEditor(root)
    root.mainloop()
