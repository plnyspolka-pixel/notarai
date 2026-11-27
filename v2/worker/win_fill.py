"""Windows programs: fill a window through UI Automation, the interface screen readers use.

Works with any program whose fields are reachable by a screen reader (Win32, WinForms, WPF,
Delphi/VCL, Java with the access bridge). Each field gets the label a person would read: its
own accessible name, or else the nearest text to its left on the same line, or just above it.
Only the window whose title matches the procedure is touched.
"""
import io
import os

from .autofill import Control, FillError, norm

FIELD_TYPES = {"Edit": "text", "Document": "text", "ComboBox": "select", "CheckBox": "check",
               "RadioButton": "check", "Button": "button", "SplitButton": "button"}


# What a person navigates a program with. The agent sees these too (`controls(deep=True)`), so a program can be
# mapped and driven by the names Windows itself gives its menus, tabs, trees and lists (UI Automation).
NAVIGATION_TYPES = {"MenuItem": "menu", "TabItem": "zakładka", "TreeItem": "gałąź", "ListItem": "pozycja",
                    "DataItem": "wiersz", "Hyperlink": "odnośnik"}


def label_controls(items: list[dict]) -> list[dict]:
    """Assign labels by geometry. `items`: dicts with type, name, rect=(left, top, right, bottom)."""
    texts = [i for i in items if i["type"] == "Text" and i["name"].strip()]
    out = []
    for item in items:
        kind = FIELD_TYPES.get(item["type"])
        if kind is None:
            continue
        label = item["name"].strip()
        if kind in {"text", "select"} and (not label or label == item.get("value", "")):
            left, top, right, bottom = item["rect"]
            best, distance = "", 10**9
            for text in texts:
                l2, t2, r2, b2 = text["rect"]
                same_line = b2 > top + 2 and t2 < bottom - 2 and r2 <= left + 4
                above = b2 <= top + 4 and l2 < right and r2 > left - 40 and top - b2 < 60
                if same_line:
                    d = left - r2
                elif above:
                    d = 1000 + top - b2
                else:
                    continue
                if d < distance:
                    best, distance = text["name"].strip(), d
            label = best or label
        out.append({**item, "kind": kind, "label": label.rstrip(":").strip()})
    return out


class Desktop:
    """UI Automation through pywinauto. One window per fill, chosen by its title."""

    def __init__(self, *, backend=None):
        self._backend = backend
        self._window = None

    def _desktop(self):
        if self._backend is not None:
            return self._backend
        if os.name != "nt":
            raise FillError("Programy wypełniam tylko na Windows.")
        try:
            from pywinauto import Desktop as UiaDesktop
        except Exception:
            raise FillError("Brakuje modułu do obsługi okien Windows. Zainstaluj NotarAI ponownie.") from None
        return UiaDesktop(backend="uia")

    def windows(self) -> list[str]:
        return [w.window_text() for w in self._desktop().windows() if w.window_text().strip()]

    def focus(self, title):
        wanted = norm(title)
        candidates = [w for w in self._desktop().windows() if wanted and wanted in norm(w.window_text())]
        if len(candidates) != 1:
            names = ", ".join(sorted({w.window_text() for w in candidates})[:5])
            raise FillError("Nie znalazłem okna programu „" + str(title) + "”. Otwórz w nim formularz i spróbuj ponownie."
                            if not candidates else f"Pasuje kilka okien ({names}). Zostaw otwarte jedno.")
        self._window = candidates[0]
        try:
            self._window.set_focus()
        except Exception:
            pass

    def _family(self):
        """The chosen window and the other windows of the same program: an open menu or a dialog is a window of its own."""
        family = [self._window]
        try:
            process = self._window.element_info.process_id
            for other in self._desktop().windows(process=process):
                if other.element_info.handle != self._window.element_info.handle:
                    family.append(other)
        except Exception:
            pass
        return family

    def controls(self, deep: bool = False):
        """`deep`: also menus, tabs, tree and list items, and the program's open menus and dialogs (for the agent)."""
        if self._window is None:
            raise FillError("Nie wybrano okna programu.")
        items, navigation = [], []
        for window in (self._family() if deep else [self._window]):
            try:
                elements = window.descendants()
            except Exception:
                continue
            for element in elements[:4000]:
                try:
                    info = element.element_info
                    kind = info.control_type
                    if deep and kind in NAVIGATION_TYPES:
                        name = (info.name or "").strip()
                        if name and element.is_visible() and element.is_enabled():
                            navigation.append(Control(element, "button", f"{name} ({NAVIGATION_TYPES[kind]})", "", []))
                        continue
                    if kind not in FIELD_TYPES and kind != "Text":
                        continue
                    if not element.is_visible() or (kind != "Text" and not element.is_enabled()):
                        continue
                    rect = element.rectangle()
                    items.append({"type": kind, "name": info.name or "", "rect": (rect.left, rect.top, rect.right, rect.bottom),
                                  "element": element, "value": self._value(element, FIELD_TYPES.get(kind)),
                                  "password": bool(deep and kind == "Edit" and self._is_password(element))})
                except Exception:
                    continue
        if deep:
            self.password_field = any(item.get("password") for item in items)
        controls = []
        for item in label_controls(items):
            options = []
            if item["kind"] == "select":
                try:
                    options = [str(text) for text in item["element"].texts()[1:] if str(text).strip()]
                except Exception:
                    options = []
            controls.append(Control(item["element"], item["kind"], item["label"], item["value"], options))
        return controls + navigation[:400]

    @staticmethod
    def _is_password(element) -> bool:
        try:
            return bool(element.element_info.element.CurrentIsPassword)
        except Exception:
            return False

    @staticmethod
    def _value(element, kind):
        try:
            if kind == "check":
                return "tak" if element.get_toggle_state() == 1 else "nie"
            if kind == "select":
                return str(element.selected_text() or "")
            if kind == "text":
                return str(element.get_value() or "")
        except Exception:
            pass
        return ""

    def type(self, control, value):
        try:
            control.ref.set_edit_text(value)
        except Exception:
            raise FillError("Pole nie przyjęło wartości.") from None

    def choose(self, control, option):
        try:
            control.ref.select(option)
        except Exception:
            raise FillError("Lista nie przyjęła wartości.") from None

    def check(self, control, on):
        try:
            if (control.ref.get_toggle_state() == 1) != on:
                control.ref.toggle()
        except Exception:
            raise FillError("Pole wyboru nie przyjęło wartości.") from None

    def read(self, control):
        return self._value(control.ref, control.kind)

    def click(self, control):
        for way in ("invoke", "select", "expand"):          # a button, a tab or a list item, a menu
            try:
                getattr(control.ref, way)()
                return
            except Exception:
                continue
        control.ref.click_input()

    def where(self):
        try:
            return self._window.window_text() if self._window is not None else ""
        except Exception:
            return ""

    def snapshot(self):
        try:
            image = self._window.capture_as_image()
            output = io.BytesIO()
            image.convert("RGB").save(output, "JPEG", quality=60)
            return output.getvalue()
        except Exception:
            return None
