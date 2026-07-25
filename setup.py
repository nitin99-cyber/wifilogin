import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
from pathlib import Path

from credential_manager import save_account
from config_manager import save_config
from startup import add_to_startup, remove_from_startup
import metadata

def center_window(window, width, height):
    window.update_idletasks()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

def get_icon_path():
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = Path(__file__).parent
    return str(Path(base_path) / "assets" / "icon.ico")

def open_about(parent):
    about_win = tk.Toplevel(parent)
    about_win.title(f"About - {metadata.APP_NAME}")
    about_win.resizable(False, False)
    center_window(about_win, 460, 780)
    about_win.transient(parent)
    about_win.grab_set()

    try:
        about_win.iconbitmap(get_icon_path())
    except Exception:
        pass

    frame = ttk.Frame(about_win, padding=20)
    frame.pack(fill="both", expand=True)

    # Title
    ttk.Label(frame, text=metadata.APP_NAME, font=("Segoe UI", 16, "bold")).pack()
    ttk.Label(frame, text=f"Version {metadata.VERSION}", font=("Segoe UI", 10)).pack(pady=(0, 10))
    ttk.Label(frame, text=metadata.DESCRIPTION, justify="center").pack()

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # Features
    ttk.Label(frame, text="Features", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    features = [
        "• Automatic Login",
        "• Secure Credential Storage",
        "• Multiple Account Support",
        "• Windows Startup",
        "• Lightweight"
    ]
    for feature in features:
        ttk.Label(frame, text=feature).pack(anchor="w", padx=10)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # Privacy
    ttk.Label(frame, text="Privacy", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    privacy_points = [
        "• No passwords are uploaded.",
        "• No personal data is collected.",
        "• No analytics are used.",
        "• Credentials are stored only on your computer.",
        "• The application only communicates with the official MMMUT login portal."
    ]
    for p in privacy_points:
        ttk.Label(frame, text=p).pack(anchor="w", padx=10)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # Developer
    ttk.Label(frame, text="Developer", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(frame, text=f"{metadata.AUTHOR}\nB.Tech CSE'29").pack(anchor="w", padx=10)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # Links
    def add_link_row(label, text):
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=10, font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Label(row, text=text).pack(side="left")

    add_link_row("GitHub", metadata.GITHUB_URL)
    add_link_row("Website", metadata.WEBSITE)
    add_link_row("Email", metadata.EMAIL)
    add_link_row("License", metadata.LICENSE)
    add_link_row("Copyright", metadata.COPYRIGHT)

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    # Message
    ttk.Label(frame, text="Made for MMMUT students.\nPlease leave a review and stay updated with the\ndeveloper for the next version with rich feature support.", justify="center").pack(pady=(0, 10))

    ttk.Button(frame, text="Close", command=about_win.destroy).pack(pady=(5, 0))


def run():
    root = tk.Tk()
    root.title(metadata.APP_NAME)
    root.resizable(False, False)
    center_window(root, 360, 580)

    try:
        root.iconbitmap(get_icon_path())
    except Exception:
        pass

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    # Header
    ttk.Label(
        frame,
        text=metadata.APP_NAME,
        font=("Segoe UI", 16, "bold")
    ).pack()
    
    ttk.Label(
        frame,
        text=f"Version {metadata.VERSION}",
        font=("Segoe UI", 10)
    ).pack(pady=(0, 10))

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 15))

    # Form
    form_frame = ttk.Frame(frame)
    form_frame.pack(fill="x")

    ttk.Label(form_frame, text="Username 1").pack(anchor="w")
    username1_entry = ttk.Entry(form_frame)
    username1_entry.pack(fill="x", pady=(2, 10))

    ttk.Label(form_frame, text="Password").pack(anchor="w")
    password1_entry = ttk.Entry(form_frame, show="*")
    password1_entry.pack(fill="x", pady=(2, 15))

    ttk.Label(form_frame, text="Username 2 (Optional)").pack(anchor="w")
    username2_entry = ttk.Entry(form_frame)
    username2_entry.pack(fill="x", pady=(2, 10))

    ttk.Label(form_frame, text="Password").pack(anchor="w")
    password2_entry = ttk.Entry(form_frame, show="*")
    password2_entry.pack(fill="x", pady=(2, 15))

    startup_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        form_frame,
        text="Start automatically with Windows",
        variable=startup_var
    ).pack(anchor="w", pady=(0, 15))

    def save():
        username1 = username1_entry.get().strip()
        password1 = password1_entry.get().strip()
        username2 = username2_entry.get().strip()
        password2 = password2_entry.get().strip()

        if not username1 or not password1:
            messagebox.showerror("Error", "Account 1 is required.")
            return

        save_account(1, username1, password1)
        if username2 and password2:
            save_account(2, username2, password2)

        config = {
            "setup_completed": True,
            "startup_enabled": startup_var.get()
        }
        save_config(config)

        if startup_var.get():
            add_to_startup()
        else:
            remove_from_startup()

        messagebox.showinfo("Success", "Setup completed successfully.")
        root.destroy()

    buttons_frame = ttk.Frame(frame)
    buttons_frame.pack(fill="x", pady=(5, 10))

    ttk.Button(buttons_frame, text="Save", command=save).pack(side="left", fill="x", expand=True, padx=(0, 5))
    ttk.Button(buttons_frame, text="About", command=lambda: open_about(root)).pack(side="right", fill="x", expand=True, padx=(5, 0))

    ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

    footer_frame = ttk.Frame(frame)
    footer_frame.pack(fill="x")
    
    footer_label = tk.Label(
        footer_frame,
        text=f"Developed by {metadata.AUTHOR}\n{metadata.COPYRIGHT}",
        font=("Segoe UI", 9),
        fg="blue",
        cursor="hand2"
    )
    footer_label.pack()
    footer_label.bind("<Button-1>", lambda e: open_about(root))

    root.mainloop()