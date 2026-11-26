"""Native controls for the local Windows operator."""
import os
import sqlite3

import win32api
import win32con
import win32gui

TITLE = "NotarAI V2 Preview"
WINDOW_CLASS = "NotarAIV2PreviewWindow"
CODE = 100
NEW_CODE = 101
OPEN_POCKET = 102


def message(text, parent=0):
    win32gui.MessageBox(parent, text, TITLE, win32con.MB_OK | win32con.MB_ICONWARNING)


def open_pocket(url):
    try:
        os.startfile(url)
    except OSError:
        message(f"Otwórz Pocket w przeglądarce pod adresem:\n{url}")


def show(url, invite, *, open_on_start):
    instance = win32api.GetModuleHandle(None)
    code = invite()

    def handle_window(hwnd, event, wparam, lparam):
        if event == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        if event == win32con.WM_COMMAND:
            control = wparam & 0xFFFF
            if control == OPEN_POCKET:
                open_pocket(url)
                return 0
            if control == NEW_CODE:
                try:
                    win32gui.SetWindowText(code_field, invite())
                except (sqlite3.Error, win32gui.error):
                    message("Nie udało się wygenerować kodu. Spróbuj ponownie.", hwnd)
                return 0
        return win32gui.DefWindowProc(hwnd, event, wparam, lparam)

    window_class = win32gui.WNDCLASS()
    window_class.hInstance = instance
    window_class.lpszClassName = WINDOW_CLASS
    window_class.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
    window_class.hbrBackground = win32con.COLOR_BTNFACE + 1
    window_class.lpfnWndProc = handle_window
    win32gui.RegisterClass(window_class)
    frame = win32con.WS_CAPTION | win32con.WS_SYSMENU | win32con.WS_MINIMIZEBOX
    default = win32con.CW_USEDEFAULT
    window = win32gui.CreateWindowEx(
        0, WINDOW_CLASS, TITLE, frame, default, default, 516, 241, 0, 0, instance, None,
    )
    common_style = win32con.WS_CHILD | win32con.WS_VISIBLE
    focus_style = common_style | win32con.WS_TABSTOP
    font = win32gui.GetStockObject(17)  # DEFAULT_GUI_FONT

    def add(kind, caption, identifier, style, left, top, width, height):
        control = win32gui.CreateWindowEx(
            0, kind, caption, style, left, top, width, height, window, identifier, instance, None,
        )
        win32gui.SendMessage(control, win32con.WM_SETFONT, font, 0)
        return control

    add("STATIC", "Tylko dane testowe", 0, common_style, 18, 15, 460, 22)
    add("STATIC", "Kod parowania do Pocket (ważny przez 5 minut)", 0, common_style, 18, 45, 460, 22)
    code_field = add(
        "EDIT", code, CODE,
        focus_style | win32con.WS_BORDER | win32con.ES_READONLY | win32con.ES_AUTOHSCROLL,
        18, 70, 460, 26,
    )
    add("BUTTON", "Otwórz Pocket", OPEN_POCKET, focus_style, 18, 115, 160, 30)
    add("BUTTON", "Nowy kod parowania", NEW_CODE, focus_style, 192, 115, 180, 30)
    add("STATIC", "Zamknięcie tego okna zatrzyma Pocket.", 0, common_style, 18, 168, 460, 22)

    win32gui.ShowWindow(window, win32con.SW_SHOW)
    win32gui.SetFocus(code_field)
    if open_on_start:
        open_pocket(url)
    win32gui.PumpMessages()
