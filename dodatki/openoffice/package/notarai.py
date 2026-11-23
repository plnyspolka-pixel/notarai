# -*- coding: utf-8 -*-
"""NotarAI OpenOffice beta: wyłącznie otwiera aplikację, nie czyta dokumentów."""
import webbrowser

URL_NOTARAI = "https://app.notarai.pl"

def OpenNotarAI(*_args):
    """Otwórz aplikację w zwykłej przeglądarce po kliknięciu w Writerze."""
    try:
        context = XSCRIPTCONTEXT.getComponentContext()
        service = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.system.SystemShellExecute", context
        )
        service.execute(URL_NOTARAI, "", 0)
    except Exception:
        webbrowser.open(URL_NOTARAI)

g_exportedScripts = (OpenNotarAI,)

# Apache OpenOffice wymaga rejestracji makra w pakiecie.
import unohelper
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    None,
    "pl.notarai.openoffice.PythonMacroPlaceholder",
    ("pl.notarai.openoffice.PythonMacroPlaceholderService",),
)