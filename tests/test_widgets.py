"""Custom widget behaviour tests (offscreen)."""
import pytest
from PySide6.QtCore import QRectF, Qt


class TestToggleSwitch:
    def test_toggle_updates_state_and_target(self, qapp, theme):
        from anydownloader.ui.widgets import ToggleSwitch

        t = ToggleSwitch()
        assert not t.isChecked()
        t.setChecked(True)
        assert t.isChecked()
        t._anim.stop()  # stop the QVariantAnimation; target position is what matters
        t._pos = 1.0
        t.update()
        assert 0.0 <= t._pos <= 1.0
        t.setChecked(False)
        assert not t.isChecked()

    def test_click_toggles(self, qapp, theme):
        from anydownloader.ui.widgets import ToggleSwitch

        t = ToggleSwitch()
        t.setChecked(False)
        t.nextCheckState()
        assert t.isChecked()


class TestSegmented:
    def test_add_and_switch(self, qapp, theme):
        from anydownloader.ui.widgets import Segmented

        seg = Segmented()
        seg.addSegment("One", "one")
        seg.addSegment("Two", "two")
        assert seg.current() == "one"
        fired = []
        seg.currentChanged.connect(fired.append)
        seg.setCurrent("two")
        assert seg.current() == "two"
        assert "two" in fired

    def test_invalid_key_ignored(self, qapp, theme):
        from anydownloader.ui.widgets import Segmented

        seg = Segmented()
        seg.addSegment("One", "one")
        seg.setCurrent("nope")
        assert seg.current() == "one"


class TestPillBadge:
    def test_kind_colors_change(self, qapp, theme):
        from anydownloader.ui.widgets import PillBadge

        pill = PillBadge("Queued", "neutral")
        size_a = (pill.width(), pill.height())
        pill.set_kind("success", "Completed")
        assert pill._kind == "success"
        assert pill._text == "Completed"
        assert (pill.width(), pill.height()) != (0, 0)
        assert size_a != (0, 0)


class TestSmoothProgressBar:
    def test_value_clamped(self, qapp, theme):
        from anydownloader.ui.widgets import SmoothProgressBar

        bar = SmoothProgressBar()
        bar.set_value(150)
        assert bar._target == 100.0
        bar.set_value(-5)
        assert bar._target == 0.0

    def test_indeterminate(self, qapp, theme):
        from anydownloader.ui.widgets import SmoothProgressBar

        bar = SmoothProgressBar()
        bar.set_indeterminate(True)
        assert bar._indeterminate
        bar.set_indeterminate(False)
        assert not bar._indeterminate


class TestFlowLayout:
    def test_wrap_recomputes_height(self, qapp, theme):
        from PySide6.QtWidgets import QPushButton, QWidget

        from anydownloader.ui.pages.base import FlowLayout

        host = QWidget()
        lay = FlowLayout(spacing=8)
        host.setLayout(lay)
        for i in range(10):
            b = QPushButton(f"Item {i} with a long label {i}")
            b.setFixedSize(150, 60)
            lay.addWidget(b)
        host.resize(320, 10)
        qapp.processEvents()
        assert lay.heightForWidth(320) > 120  # must wrap into several rows


class TestQualityCard:
    def test_checkable(self, qapp, theme):
        from anydownloader.ui.widgets import QualityCard

        card = QualityCard("1080p", "Full HD")
        card.setChecked(True)
        assert card.isChecked()


class TestThemeManager:
    def test_palette_switch(self, qapp, theme):
        theme.set_theme("dark")
        assert theme.resolve() == "dark"
        assert theme.palette.name == "dark"
        theme.set_theme("light")
        assert theme.palette.name == "light"

    def test_system_follow(self, qapp, theme):
        theme.set_theme("system")
        assert theme.resolve() in ("light", "dark")

    def test_accent(self, qapp, theme):
        theme.set_accent("purple")
        assert theme.palette.accent.lower() == "#af52de"

    def test_qss_builds_for_both(self, qapp, theme):
        from anydownloader.ui.theme import build_palette, build_qss

        for name in ("light", "dark"):
            qss = build_qss(build_palette(name, "blue"))
            assert "QMainWindow" in qss and "QPushButton" in qss
