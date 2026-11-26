"""Native controls for the local Windows operator."""
import os
import sqlite3

import win32api
import win32con
import win32gui

TITLE = "NotarAI V2 Preview"
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
    child = win32con.WS_CHILD | win32con.WS_VISIBLE
    button = child | win32con.WS_TABSTOP
    frame = (win32con.WS_POPUP | win32con.WS_VISIBLE | win32con.WS_CAPTION | win32con.WS_SYSMENU
             | win32con.DS_CENTER | win32con.DS_MODALFRAME | win32con.DS_SETFONT)
    code = invite()
    template = [
        [TITLE, (0, 0, 278, 113), frame, win32con.WS_EX_APPWINDOW, (9, "Segoe UI")],
        ["STATIC", "Tylko dane testowe", -1, (12, 9, 253, 11), child],
        ["STATIC", "Kod parowania do Pocket (ważny przez 5 minut)", -1, (12, 29, 253, 10), child],
        ["EDIT", code, CODE, (12, 42, 253, 17),
         child | win32con.WS_TABSTOP | win32con.WS_BORDER | win32con.ES_READONLY | win32con.ES_AUTOHSCROLL],
        ["BUTTON", "Otwórz Pocket", OPEN_POCKET, (12, 71, 98, 17), button | win32con.BS_DEFPUSHBUTTON],
        ["BUTTON", "Nowy kod parowania", NEW_CODE, (117, 71, 110, 17), button],
        ["STATIC", "Zamknięcie tego okna zatrzyma Pocket.", -1, (12, 96, 253, 10), child],
    ]

    def on_init(hwnd, *_):
        if open_on_start:
            open_pocket(url)
        return 1

    def on_close(hwnd, *_):
        win32gui.EndDialog(hwnd, 0)
        return 1

    def on_command(hwnd, _, wparam, lparam):
        control = win32api.LOWORD(wparam)
        if control == OPEN_POCKET:
            open_pocket(url)
        elif control == NEW_CODE:
            try:
                win32gui.SetDlgItemText(hwnd, CODE, invite())
            except sqlite3.Error:
                message("Nie udało się wygenerować kodu. Spróbuj ponownie.", hwnd)
        elif control == win32con.IDCANCEL:
            return on_close(hwnd)
        else:
            return 0
        return 1

    win32gui.DialogBoxIndirect(win32api.GetModuleHandle(None), template, 0, {
        win32con.WM_INITDIALOG: on_init,
        win32con.WM_COMMAND: on_command,
        win32con.WM_CLOSE: on_close,
    })
