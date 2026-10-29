"""Windows taskbar progress + dark title bar, via raw Win32/COM (best effort)."""
from __future__ import annotations

import ctypes
import logging
import sys

log = logging.getLogger(__name__)
_IS_WIN = sys.platform == "win32"


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(spec: str) -> _GUID:
    g = _GUID()
    g.Data1 = int(spec[1:9], 16)
    g.Data2 = int(spec[10:14], 16)
    g.Data3 = int(spec[15:19], 16)
    for i in range(8):
        g.Data4[i] = int(spec[20 + i * 2:22 + i * 2], 16)  # type: ignore[index]
    return g


class TaskbarProgress:
    """ITaskbarList3 progress overlay on the app's taskbar button."""

    _CLSID = "{56FDF344-FD6D-11d0-958A-006097C9A090}"
    _IID = "{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}"

    # ITaskbarList3 vtable offsets (incl. IUnknown + ITaskbarList/2)
    _SET_PROGRESS_VALUE = 9
    _SET_PROGRESS_STATE = 10

    def __init__(self) -> None:
        self._obj: ctypes.c_void_p | None = None
        self._last_state = -1
        if not _IS_WIN:
            return
        try:
            ctypes.windll.ole32.CoInitializeEx(None, 0x2)  # COINIT_APARTMENTTHREADED
            clsid = _guid(self._CLSID)
            iid = _guid(self._IID)
            obj = ctypes.c_void_p()
            hr = ctypes.windll.ole32.CoCreateInstance(
                ctypes.byref(clsid), None, 1 | 4, ctypes.byref(iid), ctypes.byref(obj)
            )
            if hr != 0:
                log.debug("CoCreateInstance(ITaskbarList3) hr=0x%08X", hr)
                return
            self._obj = obj
        except Exception as exc:  # pragma: no cover
            log.debug("taskbar COM init failed: %s", exc)

    def _call(self, index: int, argtypes: list, *args) -> None:
        if self._obj is None:
            return
        try:
            vtable = ctypes.cast(
                ctypes.cast(self._obj, ctypes.POINTER(ctypes.c_void_p)).contents,
                ctypes.POINTER(ctypes.c_void_p),
            )
            fn_ptr = ctypes.c_void_p(vtable[index])
            prototype = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)
            fn = prototype(fn_ptr.value)
            hr = fn(self._obj, *args)
            if hr != 0:
                log.debug("taskbar call %d hr=0x%08X", index, hr)
        except Exception as exc:  # pragma: no cover
            log.debug("taskbar call failed: %s", exc)

    def set_progress(self, hwnd: int, completed: int, total: int) -> None:
        if total <= 0:
            return
        self.set_state(hwnd, 2)  # TBPF_NORMAL
        self._call(self._SET_PROGRESS_VALUE,
                   [ctypes.c_ulonglong, ctypes.c_ulonglong],
                   ctypes.c_ulonglong(max(0, completed)),
                   ctypes.c_ulonglong(total))

    def set_state(self, hwnd: int, state: int) -> None:
        """0 no progress, 1 indeterminate, 2 normal, 4 error, 8 paused."""
        if state == self._last_state:
            return
        self._last_state = state
        self._call(self._SET_PROGRESS_STATE, [ctypes.c_int], ctypes.c_int(state))

    def clear(self, hwnd: int) -> None:
        self.set_state(hwnd, 0)


def apply_titlebar_theme(hwnd: int, dark: bool) -> None:
    """DWMWA_USE_IMMERSIVE_DARK_MODE for the window title bar."""
    if not _IS_WIN or not hwnd:
        return
    try:
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # 20 on Win10 20H1+, 19 on older builds
            hr = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(hwnd), attr, ctypes.byref(value), ctypes.sizeof(value)
            )
            if hr == 0:
                return
    except Exception as exc:  # pragma: no cover
        log.debug("titlebar theme failed: %s", exc)
