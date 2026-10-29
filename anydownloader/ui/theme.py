"""iOS-inspired design tokens, stylesheet builder and theme manager."""
from __future__ import annotations

import logging
import weakref
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget

log = logging.getLogger(__name__)

ACCENTS: dict[str, str] = {
    "blue":   "#007AFF",
    "purple": "#AF52DE",
    "pink":   "#FF2D55",
    "red":    "#FF3B30",
    "orange": "#FF9500",
    "green":  "#34C759",
    "teal":   "#30B0C7",
    "indigo": "#5856D6",
    "mint":   "#00C7BE",
}

FONT_STACK = '"Segoe UI Variable Text","Segoe UI Variable","Segoe UI","SF Pro Text",system-ui,sans-serif'
MONO_STACK = '"Cascadia Code","Cascadia Mono","Consolas","SF Mono",monospace'


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def mix(c1: str, c2: str, t: float) -> str:
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    return "#%02X%02X%02X" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def alpha(color: str, a: float) -> str:
    r, g, b = _hex_to_rgb(color)
    return f"rgba({r},{g},{b},{a})"


@dataclass(frozen=True)
class Palette:
    name: str          # light | dark
    accent: str
    window: str
    sidebar: str
    card: str
    elevated: str      # popovers, menus
    label: str
    secondary: str
    tertiary: str
    separator: str
    fill: str          # control background
    fill_hover: str
    green: str
    red: str
    orange: str

    @property
    def accent_soft(self) -> str:
        return alpha(self.accent, 0.12)

    @property
    def on_accent(self) -> str:
        return "#FFFFFF"


def build_palette(theme: str, accent_key: str = "blue") -> Palette:
    accent = ACCENTS.get(accent_key, ACCENTS["blue"])
    if theme == "dark":
        return Palette(
            name="dark", accent=accent,
            window="#000000", sidebar="#161618", card="#1C1C1E", elevated="#2C2C2E",
            label="#FFFFFF", secondary="#EBEBF5", tertiary="#8E8E93",
            separator="#38383A", fill="#2A2A2D", fill_hover="#3A3A3E",
            green="#30D158", red="#FF453A", orange="#FF9F0A",
        )
    return Palette(
        name="light", accent=accent,
        window="#F2F2F7", sidebar="#E9E9EE", card="#FFFFFF", elevated="#F7F7FA",
        label="#000000", secondary="#3C3C43", tertiary="#8E8E93",
        separator="#E2E2E7", fill="#EFEFF4", fill_hover="#E4E4EA",
        green="#34C759", red="#FF3B30", orange="#FF9500",
    )


def _secondary_label(p: Palette) -> str:
    return alpha(p.secondary, 0.6)


def build_qss(p: Palette) -> str:
    return f"""
* {{
    font-family: {FONT_STACK};
    outline: none;
}}
QMainWindow, QDialog {{ background: {p.window}; }}
QWidget {{ color: {p.label}; font-size: 13px; }}
QToolTip {{
    background: {p.elevated}; color: {p.label}; border: 1px solid {p.separator};
    border-radius: 8px; padding: 6px 10px; font-size: 12px;
}}

/* ---- labels ---- */
QLabel[role="largeTitle"] {{ font-size: 28px; font-weight: 800; letter-spacing: -0.5px; }}
QLabel[role="title"] {{ font-size: 17px; font-weight: 700; }}
QLabel[role="subtitle"] {{ font-size: 13px; color: {_secondary_label(p)}; }}
QLabel[role="caption"] {{ font-size: 11px; color: {p.tertiary}; }}
QLabel[role="sectionTitle"] {{
    font-size: 12px; font-weight: 700; color: {p.tertiary};
    letter-spacing: 0.8px; text-transform: uppercase;
}}
QLabel[role="mono"] {{ font-family: {MONO_STACK}; font-size: 12px; }}
QLabel[role="bigNumber"] {{ font-size: 22px; font-weight: 800; }}

/* ---- cards & frames ---- */
QFrame#card {{
    background: {p.card}; border: 1px solid {p.separator};
    border-radius: 16px;
}}
QFrame#cardFlat {{ background: {p.card}; border-radius: 16px; }}
QFrame#hairline {{ background: {p.separator}; border: none; max-height: 1px; }}

/* ---- inputs ---- */
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {p.fill}; color: {p.label};
    border: 1px solid transparent; border-radius: 10px;
    padding: 8px 12px; selection-background-color: {alpha(p.accent, 0.35)};
    selection-color: {p.label};
}}
QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover {{ background: {p.fill_hover}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 2px solid {p.accent}; padding: 7px 11px; background: {p.card};
}}
QLineEdit:disabled, QComboBox:disabled {{ color: {p.tertiary}; }}
QLineEdit[error="true"] {{ border: 2px solid {p.red}; padding: 7px 11px; }}
QPlainTextEdit {{ padding: 10px 12px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{
    image: none; border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid {p.tertiary}; margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: {p.elevated}; color: {p.label}; border: 1px solid {p.separator};
    border-radius: 12px; selection-background-color: {p.accent_soft};
    selection-color: {p.label}; padding: 4px; outline: 0;
}}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 18px; border: none; background: transparent;
}}

/* ---- buttons ---- */
QPushButton {{
    background: {p.fill}; color: {p.label}; border: none;
    border-radius: 10px; padding: 8px 16px; font-weight: 600; font-size: 13px;
}}
QPushButton:hover {{ background: {p.fill_hover}; }}
QPushButton:pressed {{ background: {mix(p.fill, p.label, 0.18)}; }}
QPushButton:disabled {{ color: {p.tertiary}; background: {p.fill}; }}
QPushButton#primary {{
    background: {p.accent}; color: {p.on_accent}; font-weight: 700;
    padding: 10px 20px; border-radius: 12px;
}}
QPushButton#primary:hover {{ background: {mix(p.accent, "#FFFFFF", 0.12)}; }}
QPushButton#primary:pressed {{ background: {mix(p.accent, "#000000", 0.18)}; }}
QPushButton#primary:disabled {{ background: {alpha(p.accent, 0.35)}; color: {alpha('#FFFFFF', 0.7)}; }}
QPushButton#secondary {{
    background: {p.accent_soft}; color: {p.accent}; font-weight: 600;
    padding: 10px 20px; border-radius: 12px;
}}
QPushButton#secondary:hover {{ background: {alpha(p.accent, 0.2)}; }}
QPushButton#secondary:pressed {{ background: {alpha(p.accent, 0.28)}; }}
QPushButton#danger {{ background: {alpha(p.red, 0.12)}; color: {p.red}; }}
QPushButton#danger:hover {{ background: {alpha(p.red, 0.2)}; }}
QPushButton#hero {{
    background: {p.accent}; color: {p.on_accent}; font-size: 15px; font-weight: 700;
    padding: 13px 26px; border-radius: 14px; letter-spacing: 0.1px;
}}
QPushButton#hero:hover {{ background: {mix(p.accent, "#FFFFFF", 0.12)}; }}
QPushButton#hero:pressed {{ background: {mix(p.accent, "#000000", 0.2)}; }}
QPushButton#hero:disabled {{ background: {alpha(p.accent, 0.35)}; }}

/* ---- icon buttons ---- */
QPushButton#iconButton {{
    background: transparent; border-radius: 9px; padding: 6px;
}}
QPushButton#iconButton:hover {{ background: {p.fill}; }}
QPushButton#iconButton:pressed {{ background: {p.fill_hover}; }}

/* ---- segmented control ---- */
QPushButton#segButton {{
    background: transparent; border: none; border-radius: 8px;
    padding: 6px 14px; font-weight: 600; font-size: 12.5px;
    color: {_secondary_label(p)};
}}
QPushButton#segButton:checked {{ color: {p.label}; }}
QPushButton#segButton:hover {{ color: {p.label}; }}

/* ---- settings rows ---- */
QWidget#settingsRow {{ background: transparent; }}

/* ---- sidebar ---- */
QWidget#sidebar {{ background: {p.sidebar}; border-right: 1px solid {p.separator}; }}

/* ---- nav ---- */
QPushButton#navButton {{
    background: transparent; border: none; border-radius: 9px;
    padding: 8px 10px; text-align: left; font-size: 13px; font-weight: 600;
    color: {_secondary_label(p)};
}}
QPushButton#navButton:hover {{ background: {alpha(p.label, 0.05)}; }}
QPushButton#navButton:checked {{ background: {p.accent_soft}; color: {p.accent}; }}

/* ---- menus ---- */
QMenu {{
    background: {p.elevated}; border: 1px solid {p.separator}; border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 8px; font-size: 13px; }}
QMenu::item:selected {{ background: {p.accent_soft}; color: {p.accent}; }}
QMenu::separator {{ height: 1px; background: {p.separator}; margin: 5px 8px; }}

/* ---- scrollbars ---- */
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {alpha(p.tertiary, 0.45)}; border-radius: 4px; min-height: 30px; margin: 3px 2px;
}}
QScrollBar::handle:vertical:hover {{ background: {alpha(p.tertiary, 0.8)}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {alpha(p.tertiary, 0.45)}; border-radius: 4px; min-width: 30px; margin: 2px 3px;
}}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; border: none; height: 0; width: 0;
}}

/* ---- slider ---- */
QSlider::groove:horizontal {{ height: 4px; border-radius: 2px; background: {p.fill_hover}; }}
QSlider::sub-page:horizontal {{ background: {p.accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 20px; height: 20px; margin: -8px 0; border-radius: 10px;
    background: #FFFFFF; border: 0.5px solid {alpha('#000000', 0.08)};
}}
QSlider::handle:horizontal:hover {{ background: {mix('#FFFFFF', p.accent, 0.15)}; }}

/* ---- scroll area / lists ---- */
QScrollArea {{ background: {p.window}; border: none; }}
QScrollArea > QWidget > QWidget {{ background: {p.window}; }}
QAbstractScrollArea::corner {{ background: {p.window}; }}
QListWidget, QListView, QTreeView, QTreeWidget, QTableView, QTableWidget {{
    background: transparent; border: none; outline: 0;
}}
QTableView::item, QTableWidget::item {{ padding: 6px; }}

/* ---- progress ---- */
QProgressBar {{ background: transparent; border: none; }}

/* ---- checkbox fallback ---- */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 20px; height: 20px; border-radius: 6px;
    border: 1.5px solid {p.tertiary}; background: {p.card};
}}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}
"""


class ThemeManager(QObject):
    """Owns palette selection; notifies custom-painted widgets on change."""

    theme_changed = Signal()

    _instance: "ThemeManager | None" = None

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._app = app
        self._theme_pref = "system"
        self._system_theme = "light"
        self._accent = "blue"
        self._palette = build_palette("light")
        self._painted: "weakref.WeakSet[QWidget]" = weakref.WeakSet()
        self._reduce_animations = False

    # ------------------------------------------------------------- singleton
    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager(QApplication.instance())
        return cls._instance

    @classmethod
    def install(cls, app: QApplication, theme: str, accent: str,
                reduce_animations: bool = False) -> "ThemeManager":
        mgr = cls(app)
        mgr._theme_pref = theme
        mgr._accent = accent
        mgr._reduce_animations = reduce_animations
        mgr.refresh_system_theme()
        mgr.apply()
        cls._instance = mgr
        return mgr

    # ----------------------------------------------------------------- state
    def refresh_system_theme(self) -> None:
        try:
            import winreg
        except ImportError:  # non-Windows — assume light
            self._system_theme = "light"
            return
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                self._system_theme = "light" if value == 1 else "dark"
        except OSError:
            self._system_theme = "light"

    def resolve(self) -> str:
        return self._system_theme if self._theme_pref == "system" else self._theme_pref

    def apply(self) -> None:
        self._palette = build_palette(self.resolve(), self._accent)
        self._app.setStyleSheet(build_qss(self._palette))
        self.theme_changed.emit()
        for w in list(self._painted):
            try:
                w.update()
            except RuntimeError:  # pragma: no cover - deleted C++ object
                pass

    # ---------------------------------------------------------------- getters
    @property
    def palette(self) -> Palette:
        return self._palette

    @property
    def reduce_animations(self) -> bool:
        return self._reduce_animations

    def set_theme(self, pref: str) -> None:
        if pref in ("system", "light", "dark") and pref != self._theme_pref:
            self._theme_pref = pref
            self.apply()

    def set_accent(self, key: str) -> None:
        if key in ACCENTS and key != self._accent:
            self._accent = key
            self.apply()

    def set_reduce_animations(self, value: bool) -> None:
        self._reduce_animations = value

    def register_painted(self, widget: QWidget) -> None:
        self._painted.add(widget)


def current_palette() -> Palette:
    return ThemeManager.instance().palette


def palette() -> Palette:  # alias used across widgets
    return ThemeManager.instance().palette
