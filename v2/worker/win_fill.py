"""Windows programs: fill a window through UI Automation, the interface screen readers use.

Works with any program whose fields are reachable by a screen reader (Win32, WinForms, WPF,
Delphi/VCL, Java with the access bridge). Each field gets the label a person would read: its
own accessible name, or else the nearest text to its left on the same line, or just above it.
Only the window whose title matches the procedure is touched.
"""
import io
import os
import re

from .autofill import Control, FillError, norm

FIELD_TYPES = {"Edit": "text", "Document": "text", "ComboBox": "select", "CheckBox": "check",
               "RadioButton": "check", "Button": "button", "SplitButton": "button"}


# What a person navigates a program with. The agent sees these too (`controls(deep=True)`), so a program can be
# mapped and driven by the names Windows itself gives its menus, tabs, trees and lists (UI Automation).
NAVIGATION_TYPES = {"MenuItem": "menu", "TabItem": "zakładka", "TreeItem": "gałąź", "ListItem": "pozycja",
                    "DataItem": "wiersz", "Hyperlink": "odnośnik"}


# Classic Windows programs (Delphi/VCL such as many office programs, old MFC): UI Automation often shows their
# fields without names or not at all, while every field is an ordinary window with a class. Read the old way,
# the same fields get a kind from their class.
LEGACY_CLASSES = (
    (r"(^|T|Tcx|TDB|TMask|TLabeled|TJv)(Mask|DB|Custom|Labeled|Button|Text|Date|Calc|Spin)*(Edit|Memo)\d*$|RichEdit|^Edit$", "Edit"),
    (r"Combo", "ComboBox"),
    (r"Check", "CheckBox"),
    (r"Radio", "RadioButton"),
    (r"(BitBtn|Button|Btn)\d*$", "Button"),
    (r"^Static$|StaticText|TLabel", "Text"),
)
MIN_NAMED = 3          # fewer named fields and buttons than this through UI Automation: read the classic way too


def legacy_type(class_name: str, friendly: str = "") -> str | None:
    if friendly in {"Edit", "ComboBox", "CheckBox", "RadioButton", "Button", "Static"}:
        return "Text" if friendly == "Static" else friendly
    for pattern, kind in LEGACY_CLASSES:
        if re.search(pattern, class_name or ""):
            return kind
    return None


class _Act:
    """A menu entry or a tab of a classic program: something to press that is not a window of its own."""
    def __init__(self, press):
        self._press = press

    def invoke(self):
        self._press()


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

    def __init__(self, *, backend=None, legacy=None):
        """`legacy`: the classic (win32) desktop for tests; on Windows it is created when needed."""
        self._backend, self._legacy_backend = backend, legacy
        self._window = None
        self.read_by = ""            # how the last deep read got its fields: "UI Automation" or "klasyczne okna Windows"
        self.password_field = False

    def _legacy(self):
        if self._legacy_backend is not None:
            return self._legacy_backend
        if os.name != "nt":
            return None
        try:
            from pywinauto import Desktop as ClassicDesktop
            return ClassicDesktop(backend="win32")
        except Exception:
            return None

    def _legacy_controls(self) -> list:
        """The same window read as classic Windows windows: fields by class, menus and tabs by their texts."""
        desktop = self._legacy()
        if desktop is None:
            return []
        try:
            window = desktop.window(handle=self._window.element_info.handle)
            elements = window.descendants()
        except Exception:
            return []
        items = []
        for element in elements[:4000]:
            try:
                kind = legacy_type(element.class_name(), element.friendly_class_name())
                if kind is None or not element.is_visible() or (kind != "Text" and not element.is_enabled()):
                    continue
                rect = element.rectangle()
                name = "" if kind in {"Edit", "ComboBox"} else (element.window_text() or "")
                value = ""
                if kind == "Edit":
                    value = element.window_text() or ""
                    if element.has_style(0x20):                      # ES_PASSWORD
                        self.password_field, value = True, ""
                elif kind == "ComboBox":
                    value = element.window_text() or ""
                elif kind in {"CheckBox", "RadioButton"}:
                    try:
                        value = "tak" if element.get_check_state() == 1 else "nie"
                    except Exception:
                        value = ""
                items.append({"type": kind, "name": name.replace("&", ""), "value": value, "element": element,
                              "rect": (rect.left, rect.top, rect.right, rect.bottom)})
            except Exception:
                continue
        controls, unnamed, repeats = [], 0, {}
        for item in sorted(label_controls(items), key=lambda i: (i["rect"][1] // 12, i["rect"][0])):
            label = item["label"]
            if not label:                 # a Delphi label is painted, not a window: the field keeps its place in the form
                unnamed += 1
                label = f"pole bez nazwy {unnamed}"
            repeats[label] = repeats.get(label, 0) + 1
            if repeats[label] > 1:        # two fields under one caption: the second is told apart by its order
                label = f"{label} ({repeats[label]})"
            options = []
            if item["kind"] == "select":
                try:
                    options = [str(t) for t in item["element"].item_texts() if str(t).strip()][:40]
                except Exception:
                    options = []
            controls.append(Control(item["element"], item["kind"], label, item["value"], options))
        navigation = []
        try:
            for top in (window.menu().items() if window.menu() else [])[:20]:
                head = (top.text() or "").replace("&", "").split("\t")[0].strip()
                if not head:
                    continue
                entries = (top.sub_menu().items() if top.sub_menu() else [])[:40]
                if not entries:
                    navigation.append(Control(_Act(lambda t=top: t.click_input()), "button", f"{head} (menu)", "", []))
                for entry in entries:
                    text_ = (entry.text() or "").replace("&", "").split("\t")[0].strip()
                    if text_ and entry.is_enabled():
                        navigation.append(Control(_Act(lambda path=f"{top.text()}->{entry.text()}": window.menu_select(path)),
                                                  "button", f"{head} > {text_} (menu)", "", []))
        except Exception:
            pass
        for element in elements[:4000]:
            try:
                if element.friendly_class_name() == "TabControl" and element.is_visible():
                    for index, title in enumerate(element.texts()[1:]):
                        if str(title).strip():
                            navigation.append(Control(_Act(lambda e=element, i=index: e.select(i)), "button",
                                                      f"{str(title).replace('&', '').strip()} (zakładka)", "", []))
            except Exception:
                continue
        return controls + navigation[:400]

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
            self.read_by = "UI Automation"
        controls = []
        for item in label_controls(items):
            options = []
            if item["kind"] == "select":
                try:
                    options = [str(text) for text in item["element"].texts()[1:] if str(text).strip()]
                except Exception:
                    options = []
            controls.append(Control(item["element"], item["kind"], item["label"], item["value"], options))
        if deep and sum(1 for c in controls if c.label.strip()) < MIN_NAMED:
            classic = self._legacy_controls()
            if sum(1 for c in classic if c.kind != "button" or "(" not in c.label) > len(controls) or (classic and not controls):
                self.read_by = "klasyczne okna Windows"
                seen = {c.label for c in classic}
                return classic + [c for c in navigation[:400] if c.label not in seen]
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
        try:                                   # a classic window: its text is its value, a box has a check state
            if kind == "check":
                return "tak" if element.get_check_state() == 1 else "nie"
            if kind in {"text", "select"}:
                return str(element.window_text() or "")
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
            return
        except Exception:
            pass
        try:                                   # a classic check box
            if (control.ref.get_check_state() == 1) != on:
                control.ref.check() if on else control.ref.uncheck()
        except Exception:
            raise FillError("Pole wyboru nie przyjęło wartości.") from None

    def read(self, control):
        return self._value(control.ref, control.kind)

    def click(self, control):
        for way in ("invoke", "select", "expand", "click"):  # a button, a tab or a list item, a menu, a classic button
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
