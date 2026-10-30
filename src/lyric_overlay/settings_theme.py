"""Opaque settings palettes, independent of lyric overlay colors."""
PALETTES = {
    "midnight": ("#141820", "#202733", "#EDF2FA", "#79B8FF", "#364153"),
    "graphite": ("#191919", "#272727", "#F2F2F2", "#D0D0D0", "#454545"),
    "warm_dark": ("#211D1A", "#302923", "#F5EDE5", "#E8B995", "#514338"),
    "light": ("#F3F5F8", "#FFFFFF", "#182230", "#2563EB", "#B8C2D0"),
}


def normalize_theme(value):
    return value if value in PALETTES else "midnight"


def settings_stylesheet(theme):
    bg, panel, text, accent, border = PALETTES[normalize_theme(theme)]
    return f"""
        QWidget#settingsPanel, QWidget#tabBody, QScrollArea, QTabWidget::pane {{ background: {bg}; border: none; }}
        QLabel, QCheckBox, QRadioButton {{ color: {text}; background: transparent; }}
        QTabBar::tab {{ color: {text}; background: {bg}; padding: 8px 10px; border-bottom: 2px solid transparent; }}
        QTabBar::tab:selected {{ background: {panel}; border-bottom: 2px solid {accent}; }}
        QLineEdit, QComboBox, QSpinBox, QPushButton, QToolButton {{ background: {panel}; color: {text}; border: 1px solid {border}; border-radius: 8px; padding: 6px 10px; }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {accent}; }}
        QComboBox QAbstractItemView {{ background: {panel}; color: {text}; selection-background-color: {accent}; selection-color: {bg}; border: 1px solid {border}; }}
        QPushButton:hover, QToolButton:hover {{ border-color: {accent}; background: {panel}; }}
        QPushButton:checked, QPushButton#primary {{ background: {accent}; color: {bg}; border-color: {accent}; }}
        QCheckBox::indicator {{ width: 15px; height: 15px; background: {panel}; border: 1px solid {border}; border-radius: 3px; }}
        QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
        QScrollBar::handle:vertical {{ background: {border}; }}
    """
