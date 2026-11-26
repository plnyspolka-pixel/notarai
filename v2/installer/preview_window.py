"""Native controls for the local Windows operator."""
import os
import sqlite3

import win32api
import win32con
import win32gui

TITLE = "NotarAI V2 Preview"
WINDOW_CLASS = "NotarAIV2PreviewDialog"
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
        [TITLE, (0, 0, 278, 113), frame, win32con.WS_EX_APPWINDOW, (9, "Segoe UI"), None, WINDOW_CLASS],
        ["STATIC", "Tylko dane testowe", -1, (12, 9, 253, 11), child],
        ["STATIC", "Kod parowania do Pocket (ważny przez 5 minut)", -1, (12, 29, 253, 10), child],
        ["EDIT", code, CODE, (12, 42, 253, 17),
         child | win32con.WS_TABSTOP | win32con.WS_BORDER | win32con.ES_READONLY | win32con.ES_AUTOHSCROLL],
        ["BUTTON", "Otwórz Pocket", OPEN_POCKET, (12, 71, 98, 17), button | win32con.BS_DEFPUSHBUTTON],
        ["BUTTON", "Nowy kod parowania", NEW_CODE, (117, 71, 110, 17), button],
        ["STATIC", "Zamknięcie tego okna zatrzyma Pocket.", -1, (12, 96, 253, 10), child],
    ]

    def handle_dialog(hwnd, event, wparam, _):
        if event == win32con.WM_INITDIALOG:
            if open_on_start:
                open_pocket(url)
            return 1
        if event == win32con.WM_CLOSE:
            win32gui.EndDialog(hwnd, 0)
            return 1
        if event != win32con.WM_COMMAND:
            return 0

        control = wparam & 0xFFFF
        if control == OPEN_POCKET:
            open_pocket(url)
        elif control == NEW_CODE:
            try:
                win32gui.SetWindowText(win32gui.GetDlgItem(hwnd, CODE), invite())
            except sqlite3.Error:
                message("Nie udało się wygenerować kodu. Spróbuj ponownie.", hwnd)
        elif control == win32con.IDCANCEL:
            win32gui.EndDialog(hwnd, 0)
        else:
            return 0
        return 1

    instance = win32api.GetModuleHandle(None)
    window_class = win32gui.WNDCLASS()
    window_class.SetDialogProc()
    window_class.hInstance = instance
    window_class.lpszClassName = WINDOW_CLASS
    window_class.cbWndExtra = win32con.DLGWINDOWEXTRA
    window_class.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
    window_class.hbrBackground = win32con.COLOR_BTNFACE + 1
    window_class.lpfnWndProc = handle_dialog
    win32gui.RegisterClass(window_class)
    win32gui.DialogBoxIndirect(instance, template, 0, {})
