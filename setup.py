import tkinter as tk
from tkinter import ttk, messagebox

from credential_manager import save_account
from config_manager import save_config
from startup import add_to_startup, remove_from_startup


def run():

    root = tk.Tk()
    root.title("MMMUT Wi-Fi Auto Login")
    root.geometry("420x420")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="MMMUT Wi-Fi Auto Login",
        font=("Segoe UI", 16, "bold")
    ).pack(pady=(0, 20))

    ###############################
    # Account 1
    ###############################

    ttk.Label(frame, text="Account 1 Username").pack(anchor="w")
    username1_entry = ttk.Entry(frame)
    username1_entry.pack(fill="x", pady=5)

    ttk.Label(frame, text="Account 1 Password").pack(anchor="w")
    password1_entry = ttk.Entry(frame, show="*")
    password1_entry.pack(fill="x", pady=(5, 20))

    ###############################
    # Account 2
    ###############################

    ttk.Label(frame, text="Account 2 Username (Optional)").pack(anchor="w")
    username2_entry = ttk.Entry(frame)
    username2_entry.pack(fill="x", pady=5)

    ttk.Label(frame, text="Account 2 Password (Optional)").pack(anchor="w")
    password2_entry = ttk.Entry(frame, show="*")
    password2_entry.pack(fill="x", pady=(5, 20))

    ###############################
    # Startup Checkbox
    ###############################

    startup_var = tk.BooleanVar(value=True)

    ttk.Checkbutton(
        frame,
        text="Start automatically with Windows",
        variable=startup_var
    ).pack(anchor="w", pady=10)

    ###############################
    # Save Function
    ###############################

    def save():

        username1 = username1_entry.get().strip()
        password1 = password1_entry.get().strip()

        username2 = username2_entry.get().strip()
        password2 = password2_entry.get().strip()

        if not username1 or not password1:
            messagebox.showerror(
                "Error",
                "Account 1 is required."
            )
            return

        save_account(
            1,
            username1,
            password1
        )

        if username2 and password2:
            save_account(
                2,
                username2,
                password2
            )

        config = {
            "setup_completed": True,
            "startup_enabled": startup_var.get()
        }

        save_config(config)

        if startup_var.get():
            add_to_startup()
        else:
            remove_from_startup()

        messagebox.showinfo(
            "Success",
            "Setup completed successfully."
        )

        root.destroy()

    ###############################
    # Save Button
    ###############################

    ttk.Button(
        frame,
        text="Save",
        command=save
    ).pack(fill="x", pady=20)

    root.mainloop()