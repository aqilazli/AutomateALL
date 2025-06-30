# Auto Recorder for simple task

A Python application that records and plays back mouse and keyboard actions with support for different screen resolutions and scaling factors.

## Features

- Record mouse movements, clicks, scrolls, and keyboard presses
- Play back recorded actions with precise timing
- Handle different screen resolutions and DPI scaling
- Generate batch files for easy playback
- Create activity logs of all actions
- Keyboard shortcuts for control (CTRL+1 to pause, CTRL+2 to resume)
- Minimized recording interface

## Requirements

- Python 3.6+
- Windows OS (uses Windows-specific APIs for DPI detection)
- Required packages:
  - pynput (for mouse/keyboard control)
  - tkinter (for GUI)

Install requirements with:
bash
pip install pynput
