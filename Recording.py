
import tkinter as tk
import threading
import time
import json
from pynput import mouse, keyboard

class App:
    def __init__(self, root):
        import ctypes
        self.root = root
        self.root.title("Auto")
        self.batch_mode = False  # Flag to indicate if running in batch mode (with JSON argument)

        # Create menu bar
        self.menu_bar = tk.Menu(self.root)

        import tkinter.font as tkfont
        button_font = tkfont.Font(family="TkDefaultFont", size=10)
        
        # Apply button_font to be used for buttons and labels
        self.common_font = button_font

        # File menu
        file_menu = tk.Menu(self.menu_bar, tearoff=0, font=button_font)
        file_menu.add_command(label="Export File", command=self.export_bat_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        self.menu_bar.add_cascade(label="File", menu=file_menu, font=button_font)

        # Playback menu
        # Removed Playback and Record menus as per user request

        # Help menu
        help_menu = tk.Menu(self.menu_bar, tearoff=0, font=button_font)
        def show_about():
            import tkinter.messagebox
            tkinter.messagebox.showinfo("About", "Auto Recorder v1.0\n\nCTRL+1 - Pause\nCTRL+2 - Resume\nESC - 2 Secs Hold - Terminate\nEND - End Recording\n\nCreated by MAA")
        help_menu.add_command(label="About", command=show_about)
        self.menu_bar.add_cascade(label="Help", menu=help_menu, font=button_font)

        # Set the menu bar
        self.root.config(menu=self.menu_bar)

        # Detect system DPI scaling on Windows and get desktop resolution and layout
        self.system_scale_factor = 1.0
        self.desktop_width = 0
        self.desktop_height = 0
        self.desktop_scale_factor = 1.0
        self.desktop_layout = "Unknown"
        try:
            user32 = ctypes.windll.user32

            # Try to set process DPI awareness to per-monitor if possible (Windows 8.1+)
            try:
                shcore = ctypes.windll.shcore
                PROCESS_PER_MONITOR_DPI_AWARE = 2
                shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
            except Exception:
                # Fallback to system DPI aware
                user32.SetProcessDPIAware()

            # Get DPI for primary monitor
            dc = user32.GetDC(0)
            LOGPIXELSX = 88
            dpi_x = ctypes.windll.gdi32.GetDeviceCaps(dc, LOGPIXELSX)
            self.system_scale_factor = dpi_x / 96.0
            self.desktop_scale_factor = self.system_scale_factor

            # Get desktop resolution using Windows API
            self.desktop_width = user32.GetSystemMetrics(0)
            self.desktop_height = user32.GetSystemMetrics(1)

            # Determine desktop layout (orientation)
            if self.desktop_width >= self.desktop_height:
                self.desktop_layout = "Landscape"
            else:
                self.desktop_layout = "Portrait"
        except Exception:
            pass

        # Set window always on top
        self.root.attributes("-topmost", True)

        self.root.update_idletasks()
        import ctypes
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        window_width = 300
        window_height = 120
        x = screen_width - window_width - 10  # 10 pixels from right edge
        y = 150  # moved lower from top edge
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.resizable(False, False)

        # Remove tkinter Escape key bindings
        # Use global keyboard listener for Escape key detection
        self.escape_pressed_time = None
        self.escape_press_timer = None

        from pynput import keyboard

        def escape_timer():
            # Called in a thread when escape key is pressed
            self.escape_pressed_time = time.time()
            time.sleep(2)
            if self.escape_pressed_time is not None:
                # Long press detected, terminate process
                self.terminate_process()

        ctrl_pressed = False

        def on_press(key):
            nonlocal ctrl_pressed
            try:
                print(f"Key pressed: {key}, ctrl_pressed={ctrl_pressed}")
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    ctrl_pressed = True
                    print("Ctrl pressed set to True")
                elif key == keyboard.Key.esc:
                    if self.escape_press_timer is None or not self.escape_press_timer.is_alive():
                        self.escape_press_timer = threading.Thread(target=escape_timer, daemon=True)
                        self.escape_press_timer.start()
                elif ctrl_pressed and (key == keyboard.KeyCode.from_char('1')):
                    print("Ctrl+1 detected")
                    # Pause playback on Ctrl+1 key press
                    if self.is_running and not self.paused:
                        self.pause()
                elif key == keyboard.Key.end:
                    # Stop recording on END key press but do not terminate process (keep GUI open)
                    if self.is_recording:
                        self.stop_record()
                    # Do not call terminate_process() to keep GUI open
                elif ctrl_pressed and (key == keyboard.KeyCode.from_char('2')):
                    print("Ctrl+2 detected")
                    # Resume playback on Ctrl+2 key press
                    if self.is_running and self.paused:
                        with self.playback_lock:
                            self.paused = False
                        self.status_label.config(text="Status: Running")
                        self.start_button.config(state=tk.DISABLED)
                        self.pause_button.config(state=tk.NORMAL)
                        # print("Playback resumed")
            except Exception as e:
                print(f"Exception in on_press: {e}")

        def on_release(key):
            nonlocal ctrl_pressed
            try:
                print(f"Key released: {key}, ctrl_pressed={ctrl_pressed}")
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    ctrl_pressed = False
                    print("Ctrl pressed set to False")
                # print(f"Key released: {key}")
                if key == keyboard.Key.esc:
                    if self.escape_pressed_time is not None:
                        elapsed = time.time() - self.escape_pressed_time
                        self.escape_pressed_time = None
                        if elapsed < 3:
                            self.handle_escape_single_press()
            except Exception as e:
                print(f"Exception in on_release: {e}")

        self.global_keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.global_keyboard_listener.start()

        self.is_running = False
        self.is_recording = False
        self.recorded_events = []
        self.record_start_time = None
        self.mouse_listener = None
        self.keyboard_listener = None
        self.log_file = None
        self.log_file_path = None

        # Playback control variables
        self.playback_thread = None
        self.playback_index = 0
        self.paused = False
        self.playback_lock = threading.Lock()

        self.button_frame = tk.Frame(root)
        self.button_frame.pack(pady=10)

        button_width = 10
        button_height = 1

        # Adjust start button width to better fit the GUI window width
        # Window width is 300, so set button width accordingly (approximate)
        start_button_width = 28  # Adjusted width for better fit

        self.start_button = tk.Button(self.button_frame, text="Start", command=self.start, width=start_button_width, height=button_height, font=self.common_font)
        self.start_button.grid(row=0, column=0, columnspan=2, padx=3, pady=3)

        # Keep pause button for functionality but do not display it
        self.pause_button = tk.Button(self.button_frame, text="Pause", command=self.pause, width=button_width, height=button_height, state=tk.DISABLED, font=self.common_font)
        self.pause_button.grid_forget()

        # Adjust select file and record button widths to better fit GUI
        select_record_button_width = 13  # Adjusted width for better fit

        self.select_file_button = tk.Button(self.button_frame, text="Select File", command=self.select_file, width=select_record_button_width, height=button_height, font=self.common_font)
        self.select_file_button.grid(row=1, column=0, padx=3, pady=3)

        self.record_button = tk.Button(self.button_frame, text="Record", command=self.record, width=select_record_button_width, height=button_height, font=self.common_font)
        self.record_button.grid(row=1, column=1, padx=3, pady=3)

        self.status_label = tk.Label(self.button_frame, text="Status: Stopped", font=self.common_font)
        self.status_label.grid(row=2, column=0, columnspan=3, pady=5)

        # Add resolution selection dropdown
        import tkinter.font as tkfont
        small_font = tkfont.Font(size=8)
        self.resolution_label = tk.Label(self.button_frame, text="Select Resolution :", fg="grey", font=self.common_font)
        # self.resolution_label.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        self.resolution_var = tk.StringVar()
        self.resolution_var.set("Auto")  # default value changed to "Auto"

        # Disable resolution options to enforce auto-detect
        self.resolution_options = ["Auto"]
        font = tkfont.Font(size=8)  # Decrease font size for smaller letters inside resolution box
        self.resolution_menu = tk.OptionMenu(self.button_frame, self.resolution_var, *self.resolution_options, command=self.on_resolution_change)
        self.resolution_menu.config(font=font, state="disabled")
        # self.resolution_menu.grid(row=4, column=0, sticky="ew", pady=5)
        # Center the text in the resolution menu button
        self.resolution_menu["menu"].config(font=font)
        # Remove previous attempt to access child widget, set padding directly on OptionMenu
        self.resolution_menu.config(padx=20)

        self.scale_label = tk.Label(self.button_frame, text="Select Scale :", fg="grey", font=self.common_font)
        # self.scale_label.grid(row=3, column=1, sticky="ew", pady=(10, 0))

        self.scale_var = tk.StringVar()
        # Set default scale_var to detected system scale factor as percentage string
        self.scale_var.set(f"{int(self.system_scale_factor * 100)}%")
        # Disable scale options to enforce auto-detect
        self.scale_options = ["100%"]
        self.scale_menu = tk.OptionMenu(self.button_frame, self.scale_var, *self.scale_options)
        self.scale_menu.config(font=font, state="disabled")
        # self.scale_menu.grid(row=4, column=1, sticky="ew", pady=5)
        # Center the text in the scale menu button
        self.scale_menu["menu"].config(font=font)
        # Remove previous attempt to access child widget, set padding directly on OptionMenu
        self.scale_menu.config(padx=20)

        # Add desktop layout label
        self.layout_label = tk.Label(self.button_frame, text=f"Layout: {self.desktop_layout}", fg="grey", font=self.common_font)
        # self.layout_label.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        # Add calibration button
        # self.calibrate_button = tk.Button(self.button_frame, text="Calibrate", command=self.calibrate, width=10, height=1)
        # self.calibrate_button.grid(row=1, column=2, padx=3, pady=3)

        # Calibration factor initialized to 1.0 (no adjustment)
        self.calibration_factor = 1.0

        # Create minimized window with stop button
        self.minimized_window = tk.Toplevel(self.root)
        self.minimized_window.title("Recording...")
        # Position at top right corner of Windows desktop using Windows API
        import ctypes
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        window_width = 80
        window_height = 50
        x = screen_width - window_width - 10
        y = 10
        self.minimized_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minimized_window.attributes("-topmost", True)
        self.minimized_window.protocol("WM_DELETE_WINDOW", self.stop_record)  # Make close button stop recording
        # Remove minimize and fullscreen buttons
        self.minimized_window.resizable(False, False)
        self.minimized_window.overrideredirect(False)
        try:
            self.minimized_window.wm_attributes("-toolwindow", True)
        except Exception:
            pass
        self.minimized_window.attributes("-toolwindow", True)
        self.minimized_window.withdraw()

        self.minimized_stop_button = tk.Button(self.minimized_window, text="", command=self.minimized_stop_button_action, width=6, height=1, bg="red", activebackground="darkred", relief="flat", font=self.common_font)
        self.minimized_stop_button.pack(expand=True, pady=10)

    def calibrate(self):
        import tkinter.simpledialog
        import tkinter.messagebox
        # Ask user to input calibration scale factor
        answer = tkinter.simpledialog.askfloat("Calibration", "Enter calibration scale factor (e.g., 0.8 for 80%):", minvalue=0.1, maxvalue=2.0)
        if answer is not None:
            self.calibration_factor = answer
            tkinter.messagebox.showinfo("Calibration", f"Calibration factor set to {self.calibration_factor:.2f}")
        else:
            tkinter.messagebox.showinfo("Calibration", "Calibration cancelled")

    # Override scale factor getter to include calibration factor
    def get_effective_scale_factor(self):
        try:
            if self.resolution_var.get() == "Auto":
                # Use system scale factor for Auto mode
                ui_scale_factor = self.system_scale_factor
            else:
                ui_scale_factor = float(self.scale_var.get().strip('%')) / 100.0
        except Exception:
            ui_scale_factor = 1.0
        return ui_scale_factor * self.calibration_factor

        # Update on_move, on_click, on_scroll to use get_effective_scale_factor instead of direct scale_var
    def on_move(self, x, y):
        if self.is_recording:
            # Record raw coordinates without scaling to match playback scaling
            event = {
                'type': 'move',
                'time': time.time() - self.record_start_time,
                'position': (x, y)
            }
            self.recorded_events.append(event)
            print(f"Mouse moved to {x}, {y} at {event['time']:.4f} seconds")

    def on_click(self, x, y, button, pressed):
        if self.is_recording:
            # Record raw coordinates without scaling to match playback scaling
            event = {
                'type': 'click',
                'time': time.time() - self.record_start_time,
                'position': (x, y),
                'button': str(button),
                'pressed': pressed
            }
            self.recorded_events.append(event)

    def on_scroll(self, x, y, dx, dy):
        if self.is_recording:
            # Record raw coordinates without scaling to match playback scaling
            event = {
                'type': 'scroll',
                'time': time.time() - self.record_start_time,
                'position': (x, y),
                'dx': dx,
                'dy': dy
            }
            self.recorded_events.append(event)

    # Update playback scaling to use calibration factor
    def playback(self):
        import json
        from pynput.mouse import Controller as MouseController, Button
        from pynput.keyboard import Controller as KeyboardController, Key
        import time
        import tkinter as tk
        from tkinter import messagebox

        mouse_ctrl = MouseController()
        keyboard_ctrl = KeyboardController()

        # Use stored desktop resolution instead of tkinter screen resolution
        screen_width = self.desktop_width
        screen_height = self.desktop_height

        try:
            with open(self.selected_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to load file: {e}")
            self.status_label.config(text="Status: Failed to load file")
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.DISABLED)
            return

        # Extract metadata and events
        metadata = data.get("metadata", {})
        events = data.get("events", [])

        # Use recorded screen resolution and scale factor if available
        recorded_width = metadata.get("screen_width", screen_width)
        recorded_height = metadata.get("screen_height", screen_height)
        recorded_scale = metadata.get("scale_factor", 1.0)

        # Always use recorded resolution and scale factor for playback scaling
        res_width, res_height = recorded_width, recorded_height
        res_scale_x = 1.0
        res_scale_y = 1.0

        # Use recorded scale factor only, ignore UI scale and calibration for playback
        scale_factor = recorded_scale

        # Determine original recording resolution from metadata or first move event
        original_width = recorded_width
        original_height = recorded_height
        for event in events:
            if event['type'] == 'move':
                pos = event['position']
                if pos[0] > 0 and pos[1] > 0:
                    original_width = max(original_width, pos[0])
                    original_height = max(original_height, pos[1])
                break

        start_time = time.time()
        # Adjust start_time to account for playback_index
        if self.playback_index > 0 and self.playback_index < len(events):
            start_time -= events[self.playback_index]['time']

        while self.playback_index < len(events):
            with self.playback_lock:
                if self.paused:
                    time.sleep(0.1)
                    continue
                if not self.is_running:
                    print("Playback stopped")
                    break

            event = events[self.playback_index]
            event_time = event['time']
            now = time.time() - start_time
            wait_time = event_time - now
            if wait_time > 0:
                time.sleep(wait_time)

            etype = event['type']
            if etype == 'move':
                x, y = event['position']
                # Scale coordinates from recorded resolution to current screen resolution
                scaled_x = int(x * screen_width / recorded_width)
                scaled_y = int(y * screen_height / recorded_height)
                mouse_ctrl.position = (scaled_x, scaled_y)
            elif etype == 'click':
                x, y = event['position']
                scaled_x = int(x * screen_width / recorded_width)
                scaled_y = int(y * screen_height / recorded_height)
                button = getattr(Button, event['button'].split('.')[-1])
                pressed = event['pressed']
                mouse_ctrl.position = (scaled_x, scaled_y)
                if pressed:
                    mouse_ctrl.press(button)
                else:
                    mouse_ctrl.release(button)
            elif etype == 'scroll':
                x, y = event['position']
                scaled_x = int(x * screen_width / recorded_width)
                scaled_y = int(y * screen_height / recorded_height)
                dx = event['dx']
                dy = event['dy']
                mouse_ctrl.position = (scaled_x, scaled_y)
                mouse_ctrl.scroll(dx, dy)
            elif etype == 'key_press':
                key_str = event['key']
                key = self._parse_key(key_str)
                keyboard_ctrl.press(key)
            elif etype == 'key_release':
                key_str = event['key']
                key = self._parse_key(key_str)
                keyboard_ctrl.release(key)

            self.playback_index += 1

            if self.playback_index >= len(events):
                # Playback finished
                root = tk.Tk()
                root.withdraw()
                tk.messagebox.showinfo("System", "Complete!")
                root.destroy()

                self.is_running = False
                self.paused = False
                self.playback_index = 0
                self.start_button.config(state=tk.NORMAL)
                if hasattr(self, 'pause_button'):
                    self.pause_button.config(state=tk.DISABLED)
                self.status_label.config(text="Status: Stopped")
                print("Playback finished")

                if self.batch_mode:
                    # Close the GUI after playback finishes in batch mode
                    self.root.quit()
                    # Terminate the process after user clicks OK on messagebox
                    import sys
                    sys.exit(0)

            # After playback, generate activity log file

    def on_resolution_change(self, value):
        # Removed references to self.custom_resolution_entry as it is not defined
        # if value == "Custom":
        #     self.custom_resolution_entry.grid()
        # else:
        #     self.custom_resolution_entry.grid_remove()

        # Bind ALT+P and ALT+p to pause playback
        self.root.bind_all('<Alt-p>', self.handle_alt_p)
        self.root.bind_all('<Alt-P>', self.handle_alt_p)

    def handle_alt_p(self, event):
        if self.is_running and not self.paused:
            self.pause()

    def minimized_stop_button_action(self):
        if self.is_recording:
            self.stop_record()
        elif self.is_running:
            self.pause()

    def stop_record(self):
        if self.is_recording:
            self.is_recording = False
            self.stop_listeners()
            self.save_recording()
            self.record_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.DISABLED)
            self.status_label.config(text="Status: Stopped")
            print("Recording stopped by minimized stop button")

            # Hide minimized window and show main window
            self.minimized_window.withdraw()
            self.root.deiconify()

    def start(self):
        if not self.is_running:
            if not hasattr(self, 'selected_file') or not self.selected_file:
                print("No JSON file selected to run.")
                self.status_label.config(text="Status: No file selected")
                return
            if self.playback_thread and self.playback_thread.is_alive():
                # Resume playback
                with self.playback_lock:
                    self.paused = False
                self.status_label.config(text="Status: Running")
                self.start_button.config(state=tk.DISABLED)
                self.pause_button.config(state=tk.NORMAL)
                print("Resuming playback")
            else:
                # Start new playback
                self.is_running = True
                self.paused = False
                self.playback_index = 0
                self.start_button.config(state=tk.DISABLED)
                self.pause_button.config(state=tk.NORMAL)
                self.status_label.config(text="Status: Running")
                print("Started playback")
                self.playback_thread = threading.Thread(target=self.playback, daemon=True)
                self.playback_thread.start()
                self.root.withdraw()

    def pause(self):
        if self.is_running and not self.paused:
            with self.playback_lock:
                self.paused = True
            self.status_label.config(text="Status: Paused")
            self.start_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.DISABLED)
            print("Playback paused")

    def toggle_pause_resume(self):
        if self.is_running:
            with self.playback_lock:
                if self.paused:
                    # Resume playback
                    self.paused = False
                    self.status_label.config(text="Status: Running")
                    self.start_button.config(state=tk.DISABLED)
                    self.pause_button.config(state=tk.NORMAL)
                    print("Playback resumed")
                else:
                    # Pause playback
                    self.paused = True
                    self.status_label.config(text="Status: Paused")
                    self.start_button.config(state=tk.NORMAL)
                    self.pause_button.config(state=tk.DISABLED)
                    print("Playback paused")

    def playback(self):
        import json
        from pynput.mouse import Controller as MouseController, Button
        from pynput.keyboard import Controller as KeyboardController, Key
        import time
        import tkinter as tk
        from tkinter import messagebox

        mouse_ctrl = MouseController()
        keyboard_ctrl = KeyboardController()

        # Get current screen resolution
        root = tk.Tk()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.destroy()

        try:
            with open(self.selected_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to load file: {e}")
            self.status_label.config(text="Status: Failed to load file")
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.DISABLED)
            return

        # Extract metadata and events
        metadata = data.get("metadata", {})
        events = data.get("events", [])

        # Use recorded screen resolution and scale factor if available
        recorded_width = metadata.get("screen_width", self.desktop_width)
        recorded_height = metadata.get("screen_height", self.desktop_height)
        recorded_scale = metadata.get("scale_factor", self.desktop_scale_factor)

        # Always use recorded resolution and scale factor for playback scaling
        res_width, res_height = recorded_width, recorded_height
        res_scale_x = 1.0
        res_scale_y = 1.0

        # Use recorded scale factor only, ignore UI scale and calibration for playback
        scale_factor = recorded_scale

        # Determine original recording resolution from metadata or first move event
        original_width = recorded_width
        original_height = recorded_height
        for event in events:
            if event['type'] == 'move':
                pos = event['position']
                if pos[0] > 0 and pos[1] > 0:
                    original_width = max(original_width, pos[0])
                    original_height = max(original_height, pos[1])
                break

        start_time = time.time()
        # Adjust start_time to account for playback_index
        if self.playback_index > 0 and self.playback_index < len(events):
            start_time -= events[self.playback_index]['time']

        while self.playback_index < len(events):
            with self.playback_lock:
                if self.paused:
                    time.sleep(0.1)
                    continue
                if not self.is_running:
                    print("Playback stopped")
                    break

            event = events[self.playback_index]
            event_time = event['time']
            now = time.time() - start_time
            wait_time = event_time - now
            if wait_time > 0:
                time.sleep(wait_time)

            etype = event['type']
            if etype == 'move':
                x, y = event['position']
                scaled_x = int(x * res_scale_x * scale_factor)
                scaled_y = int(y * res_scale_y * scale_factor)
                print(f"Playback move to scaled position: ({scaled_x}, {scaled_y})")
                mouse_ctrl.position = (scaled_x, scaled_y)
            elif etype == 'click':
                x, y = event['position']
                scaled_x = int(x * res_scale_x * scale_factor)
                scaled_y = int(y * res_scale_y * scale_factor)
                print(f"Playback click at scaled position: ({scaled_x}, {scaled_y})")
                button = getattr(Button, event['button'].split('.')[-1])
                pressed = event['pressed']
                mouse_ctrl.position = (scaled_x, scaled_y)
                if pressed:
                    mouse_ctrl.press(button)
                else:
                    mouse_ctrl.release(button)
            elif etype == 'scroll':
                x, y = event['position']
                scaled_x = int(x * res_scale_x * scale_factor)
                scaled_y = int(y * res_scale_y * scale_factor)
                print(f"Playback scroll at scaled position: ({scaled_x}, {scaled_y})")
                dx = event['dx']
                dy = event['dy']
                mouse_ctrl.position = (scaled_x, scaled_y)
                mouse_ctrl.scroll(dx, dy)
            elif etype == 'key_press':
                key_str = event['key']
                key = self._parse_key(key_str)
                keyboard_ctrl.press(key)
            elif etype == 'key_release':
                key_str = event['key']
                key = self._parse_key(key_str)
                keyboard_ctrl.release(key)

            self.playback_index += 1

            if self.playback_index >= len(events):
                # Playback finished
                # root = tk.Tk()
                # root.withdraw()
                # tk.messagebox.showinfo("System", "Complete!")
                # root.destroy()

                self.is_running = False
                self.paused = False
                self.playback_index = 0
                self.start_button.config(state=tk.NORMAL)
                self.pause_button.config(state=tk.DISABLED)
                self.status_label.config(text="Status: Stopped")
                print("Playback finished")
                if self.batch_mode:
                    # Close the GUI after playback finishes in batch mode
                    self.root.quit()
                    self.terminate_process()
                else:
                    # Keep GUI open for normal start
                    self.root.deiconify()

        # After playback, generate activity log file
            self.generate_activity_log(events)

    def generate_activity_log(self, events):
        import os
        activity_log_dir = os.path.join(os.path.dirname(__file__), "activity_log")
        if not os.path.exists(activity_log_dir):
            os.makedirs(activity_log_dir)
        log_filename = os.path.join(activity_log_dir, f"activity_log_{int(time.time())}.txt")

        def format_key(key_str):
            # Convert key string to readable format
            if key_str.startswith('Key.'):
                # Special keys
                return key_str.split('.')[1].capitalize()
            elif len(key_str) == 1:
                return key_str
            else:
                return key_str

        with open(log_filename, 'w', encoding='utf-8') as log_file:
            log_file.write("Activity Log\n")
            log_file.write("====================\n")
            for event in events:
                etype = event.get('type', 'unknown')
                timestamp = event.get('time', 0)
                if etype == 'move':
                    pos = event.get('position', (0, 0))
                    log_file.write(f"[{timestamp:.4f}] Mouse moved to {pos}\n")
                elif etype == 'click':
                    pos = event.get('position', (0, 0))
                    button = event.get('button', '')
                    pressed = event.get('pressed', False)
                    action = 'pressed' if pressed else 'released'
                    log_file.write(f"[{timestamp:.4f}] Mouse {button} {action} at {pos}\n")
                elif etype == 'scroll':
                    pos = event.get('position', (0, 0))
                    dx = event.get('dx', 0)
                    dy = event.get('dy', 0)
                    log_file.write(f"[{timestamp:.4f}] Mouse scrolled at {pos} by ({dx}, {dy})\n")
                elif etype == 'key_press':
                    key = event.get('key', '')
                    formatted_key = format_key(key)
                    log_file.write(f"[{timestamp:.4f}] Key pressed: {formatted_key}\n")
                elif etype == 'key_release':
                    key = event.get('key', '')
                    formatted_key = format_key(key)
                    log_file.write(f"[{timestamp:.4f}] Key released: {formatted_key}\n")
                else:
                    log_file.write(f"[{timestamp:.4f}] Unknown event: {event}\n")
        print(f"Activity log saved to {log_filename}")

    def _parse_key(self, key_str):
        from pynput.keyboard import Key
        # Handle special keys
        if key_str.startswith('Key.'):
            try:
                return getattr(Key, key_str.split('.')[1])
            except AttributeError:
                return key_str
        # Handle normal characters
        if len(key_str) == 1:
            return key_str
        return key_str

    def select_file(self):
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="Select JSON file",
            filetypes=[("JSON files", "*.json")])
        if file_path:
            self.selected_file = file_path
            print(f"Selected file: {file_path}")

    def export_bat_file(self):
        import os
        from tkinter import filedialog, messagebox

        if not hasattr(self, 'selected_file') or not self.selected_file:
            messagebox.showwarning("Warning", "Please select a JSON file first.")
            return

        # Suggest default filename based on selected JSON file
        default_dir = os.path.dirname(self.selected_file)
        default_base_name = os.path.splitext(os.path.basename(self.selected_file))[0]
        default_file = os.path.join(default_dir, default_base_name + ".bat")

        # Ask user to specify full path and filename to save .bat file
        bat_file_path = filedialog.asksaveasfilename(
            title="Save .bat file as",
            defaultextension=".bat",
            initialdir=default_dir,
            initialfile=default_base_name + ".bat",
            filetypes=[("Batch files", "*.bat")]
        )
        if not bat_file_path:
            return  # User cancelled

        # Generate .bat file content to run test.py with the JSON file as argument and --auto-start flag
        # Use python executable from sys.executable to ensure correct python path
        import sys
        python_executable = sys.executable.replace('\\', '\\\\')  # Escape backslashes for batch file

        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.basename(__file__)))

        bat_content = f"""@echo off
echo Starting...

start /min \"\" \"{python_executable}\" \"{script_path}\" \"{self.selected_file}\" --auto-start
"""
#\"{script_path}\"
        try:
            with open(bat_file_path, 'w') as bat_file:
                bat_file.write(bat_content)
            messagebox.showinfo("Success", f".bat file saved to:\n{bat_file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save .bat file: {e}")

    def on_move(self, x, y):
        if self.is_recording:
            scale_factor = self.get_effective_scale_factor()
            # Determine resolution scale factor
            if self.resolution_var.get() != "Auto" and self.resolution_var.get() != "Custom":
                try:
                    res_width, res_height = map(int, self.resolution_var.get().split('x'))
                    screen_width = self.root.winfo_screenwidth()
                    screen_height = self.root.winfo_screenheight()
                    res_scale_x = screen_width / res_width
                    res_scale_y = screen_height / res_height
                except Exception:
                    res_scale_x = 1.0
                    res_scale_y = 1.0
            else:
                res_scale_x = 1.0
                res_scale_y = 1.0

            norm_x = int(x / scale_factor / res_scale_x)
            norm_y = int(y / scale_factor / res_scale_y)
            event = {
                'type': 'move',
                'time': time.time() - self.record_start_time,
                'position': (norm_x, norm_y)
            }
            self.recorded_events.append(event)
            print(f"Mouse moved to {norm_x}, {norm_y} at {event['time']:.4f} seconds")

    def on_click(self, x, y, button, pressed):
        if self.is_recording:
            scale_factor = self.get_effective_scale_factor()
            if self.resolution_var.get() != "Auto" and self.resolution_var.get() != "Custom":
                try:
                    res_width, res_height = map(int, self.resolution_var.get().split('x'))
                    screen_width = self.root.winfo_screenwidth()
                    screen_height = self.root.winfo_screenheight()
                    res_scale_x = screen_width / res_width
                    res_scale_y = screen_height / res_height
                except Exception:
                    res_scale_x = 1.0
                    res_scale_y = 1.0
            else:
                res_scale_x = 1.0
                res_scale_y = 1.0

            norm_x = int(x / scale_factor / res_scale_x)
            norm_y = int(y / scale_factor / res_scale_y)
            event = {
                'type': 'click',
                'time': time.time() - self.record_start_time,
                'position': (norm_x, norm_y),
                'button': str(button),
                'pressed': pressed
            }
            self.recorded_events.append(event)

    def on_scroll(self, x, y, dx, dy):
        if self.is_recording:
            scale_factor = self.get_effective_scale_factor()
            if self.resolution_var.get() != "Auto" and self.resolution_var.get() != "Custom":
                try:
                    res_width, res_height = map(int, self.resolution_var.get().split('x'))
                    screen_width = self.root.winfo_screenwidth()
                    screen_height = self.root.winfo_screenheight()
                    res_scale_x = screen_width / res_width
                    res_scale_y = screen_height / res_height
                except Exception:
                    res_scale_x = 1.0
                    res_scale_y = 1.0
            else:
                res_scale_x = 1.0
                res_scale_y = 1.0

            norm_x = int(x / scale_factor / res_scale_x)
            norm_y = int(y / scale_factor / res_scale_y)
            event = {
                'type': 'scroll',
                'time': time.time() - self.record_start_time,
                'position': (norm_x, norm_y),
                'dx': dx,
                'dy': dy
            }
            self.recorded_events.append(event)

    def on_press(self, key):
        if self.is_recording:
            try:
                key_str = key.char
            except AttributeError:
                key_str = str(key)
            event = {
                'type': 'key_press',
                'time': time.time() - self.record_start_time,
                'key': key_str
            }
            self.recorded_events.append(event)

    def on_release(self, key):
        if self.is_recording:
            try:
                key_str = key.char
            except AttributeError:
                key_str = str(key)
            event = {
                'type': 'key_release',
                'time': time.time() - self.record_start_time,
                'key': key_str
            }
            self.recorded_events.append(event)

    def start_listeners(self):
        self.mouse_listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click,
            on_scroll=self.on_scroll)
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release)
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def stop_listeners(self):
        if self.mouse_listener is not None:
            self.mouse_listener.stop()
            self.mouse_listener = None
        if self.keyboard_listener is not None:
            self.keyboard_listener.stop()
            self.keyboard_listener = None

    def save_recording(self):
        import os
        recording_dir = os.path.join(os.path.dirname(__file__), "recording")
        if not os.path.exists(recording_dir):
            os.makedirs(recording_dir)
        filename = os.path.join(recording_dir, f"recording_{int(time.time())}.json")

        # Save recorded events along with metadata for resolution and scale
        if self.resolution_var.get() != "Auto" and self.resolution_var.get() != "Custom":
            try:
                res_width, res_height = map(int, self.resolution_var.get().split('x'))
            except Exception:
                res_width, res_height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        else:
            res_width, res_height = self.desktop_width, self.desktop_height

        data_to_save = {
            "metadata": {
                "screen_width": res_width,
                "screen_height": res_height,
                "scale_factor": float(self.scale_var.get().strip('%')) / 100.0
            },
            "events": self.recorded_events
        }

        with open(filename, 'w') as f:
            json.dump(data_to_save, f, indent=2)
        print(f"Recording saved to {filename}")

    def record(self):
        if not self.is_recording:
            self.is_recording = True
            self.recorded_events = []
            self.record_start_time = time.time()
            self.start_listeners()
            self.record_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL)
            self.status_label.config(text="Status: Recording")
            print("Recording started")

            # Hide main window and show minimized window with stop button
            self.root.withdraw()
            self.minimized_window.deiconify()

    def handle_escape_press(self, event):
        pass

    def handle_escape_release(self, event):
        pass

    def terminate_process(self):
        import sys
        import os
        print("Terminating application due to long Escape key press.")
        self.status_label.config(text="Status: Terminating application...")
        self.stop_listeners()
        self.root.destroy()
        os._exit(0)

import sys
import os
import threading
import tkinter as tk

import argparse

if __name__ == "__main__":
    import sys
    parser = argparse.ArgumentParser(description="Auto Recorder Playback")
    parser.add_argument("json_file", nargs='?', help="Path to JSON file for playback")
    parser.add_argument("--auto-start", action="store_true", help="Automatically start playback")
    parser.add_argument("--auto-pause", action="store_true", help="Automatically pause playback after starting")
    args = parser.parse_args()

    root = tk.Tk()
    app = App(root)

    if args.json_file and os.path.isfile(args.json_file) and args.json_file.lower().endswith('.json'):
        print("Starting...")  # Added to replicate batch file behavior
        app.selected_file = args.json_file
        app.batch_mode = True

        # Withdraw root window immediately to hide GUI in batch mode
        root.withdraw()

        def start_playback():
            app.start()
            if args.auto_pause:
                # Pause shortly after starting to ensure playback has begun
                time.sleep(0.5)
                app.pause()

        if args.auto_start:
            # Delay slightly to allow GUI to initialize before starting playback
            def delayed_start():
                time.sleep(0.5)
                start_playback()
            threading.Thread(target=delayed_start, daemon=True).start()
    else:
        if args.json_file:
            print(f"Invalid JSON file path provided: {args.json_file}")

    root.mainloop()
