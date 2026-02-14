
import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES, TkinterDnD
class P2PGUI:
    def __init__(self, on_file_selected_callback):
        
        self.on_file_selected = on_file_selected_callback
        
        self.root = TkinterDnD.Tk()
        self.root.title("P2P File Transfer")
        self.root.geometry("500x400")
        self.root.configure(bg='#2b2b2b')
        
        self._setup_ui()
        
    def _setup_ui(self):
        
        
        mode_frame = tk.Frame(self.root, bg='#2b2b2b')
        mode_frame.pack(pady=20)
        
        tk.Label(mode_frame, text="Tryb:", bg='#2b2b2b', fg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=5)
        
        self.mode = tk.StringVar(value='server')
        tk.Radiobutton(mode_frame, text="Serwer", variable=self.mode, value='server', 
                      bg='#2b2b2b', fg='white', selectcolor='#3b3b3b').pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(mode_frame, text="Klient", variable=self.mode, value='client',
                      bg='#2b2b2b', fg='white', selectcolor='#3b3b3b').pack(side=tk.LEFT, padx=10)
        
        self.drop_frame = tk.Frame(self.root, bg='#3b3b3b', relief=tk.RAISED, bd=2)
        self.drop_frame.pack(pady=30, padx=40, fill=tk.BOTH, expand=True)
        
        self.drop_label = tk.Label(
            self.drop_frame,
            text="📁\n\nPrzeciągnij plik tutaj\nlub kliknij aby wybrać",
            bg='#3b3b3b',
            fg='white',
            font=('Arial', 14),
            cursor='hand2'
        )
        self.drop_label.pack(expand=True, fill=tk.BOTH)
        
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind('<<Drop>>', self._on_drop)
        self.drop_label.bind('<Button-1>', lambda e: self._browse_file())
        
        self.status_label = tk.Label(self.root, text="Czekam na plik...", 
                                     bg='#2b2b2b', fg='#888', font=('Arial', 10))
        self.status_label.pack(pady=10)
        
    def _on_drop(self, event):
        filepath = event.data.strip('{}').strip('"').strip("'")
        self.status_label.config(text=f"Plik: {filepath}", fg='#4CAF50')
        if self.on_file_selected:
            self.on_file_selected(filepath)  
    def _browse_file(self):
        filepath = filedialog.askopenfilename()
        if filepath:
            self.status_label.config(text=f"Plik: {filepath}", fg='#4CAF50')
            if self.on_file_selected:
                self.on_file_selected(filepath)  
    def run(self):
        self.root.mainloop()



def handle_file_selected(filepath, mode):
    
    print(f"[{mode.upper()}] Wybrany plik: {filepath}")
    
    


