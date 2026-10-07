"""Shared, restrained desktop styling for automatic and manual workspaces."""

STYLESHEET = """
QMainWindow { background: #f3f5f9; }
QWidget { color: #263449; font-family: 'Microsoft YaHei UI', 'Segoe UI'; font-size: 12px; }
QWidget#workspace, QWidget#controls, QScrollArea { background: transparent; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: #eaf0f8; color: #52657e; border: 1px solid #dce3ed; border-radius: 7px; padding: 9px 20px; margin-right: 8px; }
QTabBar::tab:selected { background: #356be5; color: #ffffff; border-color: #356be5; }
QTabBar::tab:!selected:hover { background: #edf3ff; color: #285bcc; }
QWidget#sidebar, QWidget#previewCard { background: #ffffff; border: 1px solid #e1e6ef; border-radius: 12px; }
QLabel { background: transparent; border: none; }
QLabel#title { font-size: 23px; font-weight: 600; color: #182b47; }
QLabel#subtitle, QLabel#hint { color: #78869a; }
QLabel#sectionTitle { font-size: 15px; font-weight: 600; color: #263f62; padding: 6px 0; }
QLabel#badge { color: #3462c8; background: #eaf0ff; border-radius: 12px; padding: 6px 14px; }
QLabel#status { color: #52657e; padding: 4px 0; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #f8faff; border: 1px solid #dce3ed; border-radius: 6px;
    padding: 6px 8px; min-height: 22px; selection-background-color: #356be5;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #5682e8; background: #ffffff; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: #9ca8b9; background: #f1f3f7; }
QComboBox::drop-down { border: none; width: 24px; }
QPushButton { background: #ffffff; border: 1px solid #dce3ed; border-radius: 7px; padding: 8px 12px; min-height: 22px; font-weight: 500; }
QPushButton:hover { background: #edf3ff; border-color: #a8bff0; color: #285bcc; }
QPushButton:pressed { background: #dfeaff; }
QPushButton#primary { color: #ffffff; background: #356be5; border-color: #356be5; font-weight: 600; }
QPushButton#primary:hover { background: #2459cc; }
QPushButton:disabled, QPushButton#primary:disabled { color: #9ca8b9; background: #edf0f5; border-color: #e2e7ef; }
QPushButton#cancel { min-height: 16px; padding: 4px 10px; }
QGroupBox { background: #ffffff; border: 1px solid #e1e6ef; border-radius: 9px; margin-top: 12px; padding: 14px 10px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #52657e; font-weight: 600; }
QCheckBox { spacing: 8px; padding: 4px 0; }
QCheckBox::indicator { width: 15px; height: 15px; }
QProgressBar { border: none; border-radius: 4px; background: #eaf0f8; height: 8px; min-height: 8px; max-height: 8px; }
QProgressBar::chunk { background: #356be5; border-radius: 4px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 4px 0; }
QScrollBar::handle:vertical { background: #cdd6e4; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QSplitter::handle { background: transparent; width: 12px; }
QToolBar { background: #ffffff; border: none; padding: 8px; spacing: 10px; }
QStatusBar { background: #f3f5f9; }
QToolTip { color: #263449; background: #ffffff; border: 1px solid #dce3ed; padding: 6px; }
"""


def apply_theme(window):
    window.setStyleSheet(STYLESHEET)
