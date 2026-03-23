#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
休息提醒助手 - Break Reminder Assistant
基于 PyQt5 构建，支持系统托盘、自定义提醒、循环计时
"""

import sys
import os
import json
import platform
from datetime import date

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDialog, QFormLayout, QSpinBox, QComboBox,
    QTextEdit, QGroupBox, QSystemTrayIcon, QMenu, QAction,
    QMessageBox, QFrame, QProgressBar, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QRect
from PyQt5.QtGui import (
    QIcon, QFont, QPixmap, QPainter, QColor, QBrush, QPen,
    QLinearGradient, QRadialGradient, QFontDatabase
)

# ═══════════════════════════════════════════════════════════
# 常量 & 配置
# ═══════════════════════════════════════════════════════════
APP_NAME  = "休息提醒助手"
VERSION   = "1.0.0"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".break_reminder.json")

UNITS     = ["秒", "分钟", "小时"]
UNIT_SECS = [1, 60, 3600]

DEFAULT_CONFIG = {
    "work_value":  60, "work_unit":  1,   # 60 分钟
    "break_value": 15, "break_unit": 1,   # 15 分钟
    "reminder_text": "该休息一下了！\n👀 放松眼睛，起来活动活动~",
    "sound_enabled": True,
    "stats_date": "", "stats_count": 0,
}

# 调色板
CLR_BG        = "#1a1d2e"
CLR_CARD      = "#252840"
CLR_ACCENT    = "#6c63ff"
CLR_ACCENT2   = "#a78bfa"
CLR_SUCCESS   = "#4ade80"
CLR_WARNING   = "#fb923c"
CLR_TEXT      = "#e2e8f0"
CLR_SUBTEXT   = "#94a3b8"
CLR_BORDER    = "#334155"


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════
def to_seconds(value: int, unit_idx: int) -> int:
    return value * UNIT_SECS[unit_idx]


def fmt_time(secs: int) -> str:
    secs = max(0, int(secs))
    h, r = divmod(secs, 3600)
    m, s = divmod(r, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def make_icon(color: str, size: int = 64) -> QIcon:
    """动态生成托盘图标（纯色圆形 + 钟表指针）"""
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    # 背景圆
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, size - 8, size - 8)
    # 简单钟表线条
    cx, cy = size // 2, size // 2
    p.setPen(QPen(Qt.white, max(2, size // 16)))
    import math
    # 分针（12点方向偏一点）
    p.drawLine(cx, cy, cx + int(12 * math.sin(math.radians(30))),
               cy - int(12 * math.cos(math.radians(30))))
    # 时针（3点方向）
    p.drawLine(cx, cy, cx + 10, cy)
    p.end()
    return QIcon(px)


def play_sound():
    if platform.system() == "Windows":
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# 配置管理
# ═══════════════════════════════════════════════════════════
class Config:
    def __init__(self):
        self.data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self.data.update(saved)
        except Exception:
            pass

    def save(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def __getitem__(self, k):  return self.data[k]
    def __setitem__(self, k, v): self.data[k] = v

    @property
    def work_secs(self) -> int:
        return to_seconds(self.data["work_value"], self.data["work_unit"])

    @property
    def break_secs(self) -> int:
        return to_seconds(self.data["break_value"], self.data["break_unit"])

    def today_stats(self) -> int:
        today = str(date.today())
        if self.data["stats_date"] != today:
            self.data["stats_date"] = today
            self.data["stats_count"] = 0
        return self.data["stats_count"]

    def add_break(self):
        self.today_stats()
        self.data["stats_count"] += 1
        self.save()


# ═══════════════════════════════════════════════════════════
# 提醒弹窗
# ═══════════════════════════════════════════════════════════
class ReminderDialog(QDialog):
    """顶置弹窗，显示自定义提醒文本 + 倒计时"""
    dismissed = pyqtSignal()

    def __init__(self, text: str, duration_secs: int, parent=None):
        super().__init__(
            parent,
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Dialog
        )
        self.duration  = duration_secs
        self.remaining = duration_secs
        self._drag_pos = None
        self._build_ui(text)
        self._start_timer()
        self._center()
        play_sound()

    # ── UI ────────────────────────────────────────────────
    def _build_ui(self, text: str):
        self.setFixedSize(460, 320)
        self.setAttribute(Qt.WA_TranslucentBackground)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # 卡片容器
        card = QFrame(self)
        card.setObjectName("ReminderCard")
        card.setStyleSheet(f"""
            #ReminderCard {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6c63ff, stop:1 #a855f7
                );
                border-radius: 20px;
            }}
            QLabel  {{ color: white; background: transparent; }}
            QPushButton {{
                background: rgba(255,255,255,0.18);
                color: white;
                border: 2px solid rgba(255,255,255,0.35);
                border-radius: 10px;
                padding: 8px 22px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover  {{ background: rgba(255,255,255,0.32); }}
            QPushButton:pressed{{ background: rgba(255,255,255,0.45); }}
            QProgressBar {{
                background: rgba(255,255,255,0.20);
                border-radius: 5px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: rgba(255,255,255,0.80);
                border-radius: 5px;
            }}
        """)

        # 阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(36, 30, 36, 28)
        vbox.setSpacing(10)

        # 标题
        lbl_title = QLabel("🔔  休息时间到！")
        lbl_title.setFont(QFont("", 20, QFont.Bold))
        lbl_title.setAlignment(Qt.AlignCenter)
        vbox.addWidget(lbl_title)

        # 用户文本
        lbl_text = QLabel(text)
        lbl_text.setFont(QFont("", 13))
        lbl_text.setAlignment(Qt.AlignCenter)
        lbl_text.setWordWrap(True)
        vbox.addWidget(lbl_text)

        vbox.addSpacing(6)

        # 倒计时
        self.lbl_count = QLabel()
        self.lbl_count.setFont(QFont("Consolas", 34, QFont.Bold))
        self.lbl_count.setAlignment(Qt.AlignCenter)
        vbox.addWidget(self.lbl_count)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setRange(0, self.duration)
        self.progress.setValue(self.duration)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(10)
        vbox.addWidget(self.progress)

        vbox.addSpacing(4)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_skip  = QPushButton("⏭  跳过本次")
        btn_end   = QPushButton("✅  提前结束休息")
        btn_skip.clicked.connect(self._dismiss)
        btn_end.clicked.connect(self._dismiss)
        btn_row.addWidget(btn_skip)
        btn_row.addWidget(btn_end)
        vbox.addLayout(btn_row)

        root.addWidget(card)
        self._refresh_label()

    # ── Timer ─────────────────────────────────────────────
    def _start_timer(self):
        self._qtimer = QTimer(self)
        self._qtimer.timeout.connect(self._tick)
        self._qtimer.start(1000)

    def _tick(self):
        self.remaining -= 1
        self._refresh_label()
        if self.remaining <= 0:
            self._dismiss()

    def _refresh_label(self):
        self.lbl_count.setText(fmt_time(self.remaining))
        self.progress.setValue(self.remaining)

    def _dismiss(self):
        self._qtimer.stop()
        self.dismissed.emit()
        self.close()

    # ── 可拖动 ────────────────────────────────────────────
    def _center(self):
        geo = QApplication.primaryScreen().geometry()
        self.move((geo.width() - self.width()) // 2,
                  (geo.height() - self.height()) // 2)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos() - self._drag_pos)


# ═══════════════════════════════════════════════════════════
# 设置对话框
# ═══════════════════════════════════════════════════════════
class SettingsDialog(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("⚙️  设置")
        self.setFixedSize(400, 370)
        self.setStyleSheet(DIALOG_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        # ── 工作间隔 ──
        wg = QGroupBox("⏱  工作间隔")
        wl = QHBoxLayout(wg)
        self.work_spin = QSpinBox(); self.work_spin.setRange(1, 999)
        self.work_spin.setValue(self.cfg["work_value"])
        self.work_unit = QComboBox(); self.work_unit.addItems(UNITS)
        self.work_unit.setCurrentIndex(self.cfg["work_unit"])
        wl.addWidget(QLabel("每隔"))
        wl.addWidget(self.work_spin)
        wl.addWidget(self.work_unit)
        wl.addWidget(QLabel("提醒一次"))
        wl.addStretch()
        layout.addWidget(wg)

        # ── 休息时长 ──
        bg = QGroupBox("😌  休息时长")
        bl = QHBoxLayout(bg)
        self.break_spin = QSpinBox(); self.break_spin.setRange(1, 999)
        self.break_spin.setValue(self.cfg["break_value"])
        self.break_unit = QComboBox(); self.break_unit.addItems(UNITS)
        self.break_unit.setCurrentIndex(self.cfg["break_unit"])
        bl.addWidget(QLabel("休息"))
        bl.addWidget(self.break_spin)
        bl.addWidget(self.break_unit)
        bl.addStretch()
        layout.addWidget(bg)

        # ── 提醒文本 ──
        tg = QGroupBox("📝  提醒文本")
        tl = QVBoxLayout(tg)
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.cfg["reminder_text"])
        self.text_edit.setFixedHeight(80)
        tl.addWidget(self.text_edit)
        layout.addWidget(tg)

        # ── 按钮行 ──
        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {CLR_BORDER};")
        layout.addWidget(line)

        btn_row = QHBoxLayout()
        btn_save   = QPushButton("  保存")
        btn_cancel = QPushButton("取消")
        btn_save.setObjectName("AccentBtn")
        btn_save.clicked.connect(self._save)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _save(self):
        self.cfg["work_value"]    = self.work_spin.value()
        self.cfg["work_unit"]     = self.work_unit.currentIndex()
        self.cfg["break_value"]   = self.break_spin.value()
        self.cfg["break_unit"]    = self.break_unit.currentIndex()
        self.cfg["reminder_text"] = self.text_edit.toPlainText().strip() or "该休息了！"
        self.cfg.save()
        self.accept()


# ═══════════════════════════════════════════════════════════
# 主窗口
# ═══════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    """
    状态机：
      stopped → working → reminding → working → ...
                       ↑ paused ↓
    """

    STATE_STOPPED   = "stopped"
    STATE_WORKING   = "working"
    STATE_REMINDING = "reminding"
    STATE_PAUSED    = "paused"

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg   = cfg
        self.state = self.STATE_STOPPED
        self.remaining  = 0       # seconds left in current phase
        self._reminder  = None    # active ReminderDialog

        self.setWindowTitle(APP_NAME)
        self.setFixedSize(380, 500)
        self.setStyleSheet(MAIN_STYLE)

        self._build_ui()
        self._build_tray()

        # 主定时器（每秒 tick）
        self._ticker = QTimer(self)
        self._ticker.timeout.connect(self._on_tick)

    # ── UI ────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(0)

        # —— 标题栏 ——
        title_row = QHBoxLayout()
        lbl_app = QLabel(f"⏰  {APP_NAME}")
        lbl_app.setObjectName("AppTitle")
        self.lbl_state = QLabel("就绪")
        self.lbl_state.setObjectName("StateTag")
        title_row.addWidget(lbl_app)
        title_row.addStretch()
        title_row.addWidget(self.lbl_state)
        root.addLayout(title_row)

        root.addSpacing(18)

        # —— 圆形倒计时区域 ——
        self.lbl_phase = QLabel("准备开始")
        self.lbl_phase.setObjectName("PhaseLabel")
        self.lbl_phase.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_phase)

        self.lbl_time = QLabel("--:--")
        self.lbl_time.setObjectName("BigTimer")
        self.lbl_time.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_time)

        self.progress = QProgressBar()
        self.progress.setObjectName("MainProgress")
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        root.addSpacing(16)

        # —— 今日统计 ——
        self.lbl_stats = QLabel()
        self.lbl_stats.setObjectName("StatsLabel")
        self.lbl_stats.setAlignment(Qt.AlignCenter)
        root.addWidget(self.lbl_stats)
        self._refresh_stats()

        root.addStretch()

        # —— 主按钮区 ——
        # 开始 / 暂停
        self.btn_start = QPushButton("▶  开始")
        self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.clicked.connect(self._on_start_pause)
        root.addWidget(self.btn_start)

        root.addSpacing(8)

        # 设置 / 退出
        bottom_row = QHBoxLayout()
        self.btn_settings = QPushButton("⚙  设置")
        btn_exit          = QPushButton("✕  退出")
        self.btn_settings.setObjectName("SecondaryBtn")
        btn_exit.setObjectName("DangerBtn")
        self.btn_settings.clicked.connect(self._open_settings)
        btn_exit.clicked.connect(self._quit)
        bottom_row.addWidget(self.btn_settings)
        bottom_row.addWidget(btn_exit)
        root.addLayout(bottom_row)

        root.addSpacing(4)

        # 小字提示
        hint = QLabel("点击开始后，可最小化到系统托盘")
        hint.setObjectName("HintLabel")
        hint.setAlignment(Qt.AlignCenter)
        root.addWidget(hint)

    # ── 系统托盘 ──────────────────────────────────────────
    def _build_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(make_icon(CLR_ACCENT))
        self._tray.setToolTip(APP_NAME)

        menu = QMenu()
        menu.setStyleSheet(TRAY_MENU_STYLE)

        self._act_show  = QAction("📋  显示主窗口", self)
        self._act_pause = QAction("⏸  暂停计时",  self)
        act_quit        = QAction("✕  退出程序",  self)

        self._act_show.triggered.connect(self._restore_window)
        self._act_pause.triggered.connect(self._on_start_pause)
        act_quit.triggered.connect(self._quit)

        menu.addAction(self._act_show)
        menu.addAction(self._act_pause)
        menu.addSeparator()
        menu.addAction(act_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_click)
        self._tray.show()

    # ── 计时逻辑 ──────────────────────────────────────────
    def _on_tick(self):
        self.remaining -= 1
        self._refresh_display()
        if self.remaining <= 0:
            if self.state == self.STATE_WORKING:
                self._enter_reminding()
            elif self.state == self.STATE_REMINDING:
                self._enter_working()

    def _enter_working(self):
        self.state     = self.STATE_WORKING
        self.remaining = self.cfg.work_secs
        self._ticker.start(1000)
        self._update_state_ui()
        # 关闭弹窗（若还在）
        if self._reminder:
            self._reminder.close()
            self._reminder = None
        self._tray.setIcon(make_icon(CLR_SUCCESS))
        self._tray.setToolTip(f"{APP_NAME} · 工作中")
        self._act_pause.setText("⏸  暂停计时")

    def _enter_reminding(self):
        self.cfg.add_break()
        self._refresh_stats()
        self.state     = self.STATE_REMINDING
        self.remaining = self.cfg.break_secs
        self._ticker.stop()  # 弹窗内部有自己的计时器
        self._update_state_ui()

        self._tray.setIcon(make_icon(CLR_WARNING))
        self._tray.setToolTip(f"{APP_NAME} · 休息中")
        self._tray.showMessage(
            APP_NAME,
            self.cfg["reminder_text"][:60],
            QSystemTrayIcon.Information,
            3000,
        )

        self._reminder = ReminderDialog(
            self.cfg["reminder_text"],
            self.cfg.break_secs,
        )
        self._reminder.dismissed.connect(self._enter_working)
        self._reminder.show()
        self._reminder.activateWindow()
        self._reminder.raise_()

    def _on_start_pause(self):
        if self.state == self.STATE_STOPPED:
            self._enter_working()
            self.btn_start.setText("⏸  暂停")
            self.btn_settings.setEnabled(False)

        elif self.state == self.STATE_WORKING:
            self.state = self.STATE_PAUSED
            self._ticker.stop()
            self.btn_start.setText("▶  继续")
            self._update_state_ui()
            self._tray.setIcon(make_icon(CLR_SUBTEXT))
            self._act_pause.setText("▶  继续计时")

        elif self.state == self.STATE_PAUSED:
            self.state = self.STATE_WORKING
            self._ticker.start(1000)
            self.btn_start.setText("⏸  暂停")
            self._update_state_ui()
            self._tray.setIcon(make_icon(CLR_SUCCESS))
            self._act_pause.setText("⏸  暂停计时")

        elif self.state == self.STATE_REMINDING:
            pass  # 提醒中不响应暂停

    # ── 刷新 UI ───────────────────────────────────────────
    def _refresh_display(self):
        self.lbl_time.setText(fmt_time(self.remaining))
        total = (self.cfg.work_secs if self.state in (
            self.STATE_WORKING, self.STATE_PAUSED
        ) else self.cfg.break_secs)
        if total > 0:
            pct = int(self.remaining / total * 100)
            self.progress.setRange(0, 100)
            self.progress.setValue(pct)

    def _update_state_ui(self):
        texts = {
            self.STATE_STOPPED:   ("就绪",   "准备开始"),
            self.STATE_WORKING:   ("工作中", "距下次休息"),
            self.STATE_REMINDING: ("休息中", "休息剩余时间"),
            self.STATE_PAUSED:    ("已暂停", "距下次休息（已暂停）"),
        }
        tag, phase = texts.get(self.state, ("", ""))
        self.lbl_state.setText(tag)
        self.lbl_phase.setText(phase)

        state_colors = {
            self.STATE_WORKING:   CLR_SUCCESS,
            self.STATE_REMINDING: CLR_WARNING,
            self.STATE_PAUSED:    CLR_SUBTEXT,
            self.STATE_STOPPED:   CLR_ACCENT,
        }
        c = state_colors.get(self.state, CLR_ACCENT)
        self.lbl_state.setStyleSheet(
            f"background:{c}22; color:{c}; border:1px solid {c}66;"
            f"border-radius:6px; padding:2px 8px; font-size:12px; font-weight:bold;"
        )
        self._refresh_display()

    def _refresh_stats(self):
        n = self.cfg.today_stats()
        self.lbl_stats.setText(f"今日已完成休息：{n} 次")

    # ── 设置 ──────────────────────────────────────────────
    def _open_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        dlg.exec_()

    # ── 窗口关闭处理 ──────────────────────────────────────
    def closeEvent(self, event):
        if self.state == self.STATE_STOPPED:
            event.accept()
            return
        reply = QMessageBox(self)
        reply.setWindowTitle(APP_NAME)
        reply.setText("你想做什么？")
        reply.setStyleSheet(DIALOG_STYLE)
        btn_tray = reply.addButton("最小化到托盘", QMessageBox.ActionRole)
        btn_quit = reply.addButton("退出程序",     QMessageBox.DestructiveRole)
        reply.addButton("取消", QMessageBox.RejectRole)
        reply.exec_()
        clicked = reply.clickedButton()
        if clicked == btn_tray:
            event.ignore()
            self.hide()
        elif clicked == btn_quit:
            event.accept()
            self._do_quit()
        else:
            event.ignore()

    def changeEvent(self, event):
        from PyQt5.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized() and self.state != self.STATE_STOPPED:
                self.hide()
        super().changeEvent(event)

    # ── 托盘交互 ──────────────────────────────────────────
    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._restore_window()

    def _restore_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    # ── 退出 ──────────────────────────────────────────────
    def _quit(self):
        self._do_quit()

    def _do_quit(self):
        self._ticker.stop()
        self.cfg.save()
        self._tray.hide()
        QApplication.quit()


# ═══════════════════════════════════════════════════════════
# 样式表
# ═══════════════════════════════════════════════════════════
MAIN_STYLE = f"""
QMainWindow, QWidget {{
    background: {CLR_BG};
    color: {CLR_TEXT};
    font-family: "Microsoft YaHei", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    font-size: 14px;
}}
#AppTitle {{
    font-size: 18px;
    font-weight: bold;
    color: {CLR_TEXT};
}}
#StateTag {{
    font-size: 12px;
    border-radius: 6px;
    padding: 2px 8px;
}}
#PhaseLabel {{
    font-size: 13px;
    color: {CLR_SUBTEXT};
    margin-top: 4px;
}}
#BigTimer {{
    font-size: 56px;
    font-weight: bold;
    color: {CLR_TEXT};
    font-family: "Consolas", "Courier New", monospace;
    letter-spacing: 2px;
}}
#MainProgress {{
    background: {CLR_CARD};
    border-radius: 4px;
    border: none;
    margin: 6px 0;
}}
#MainProgress::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {CLR_ACCENT}, stop:1 {CLR_ACCENT2});
    border-radius: 4px;
}}
#StatsLabel {{
    font-size: 12px;
    color: {CLR_SUBTEXT};
}}
#HintLabel {{
    font-size: 11px;
    color: {CLR_BORDER};
    margin-top: 4px;
}}
#PrimaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {CLR_ACCENT}, stop:1 {CLR_ACCENT2});
    color: white;
    border: none;
    border-radius: 12px;
    padding: 14px;
    font-size: 15px;
    font-weight: bold;
}}
#PrimaryBtn:hover  {{ background: {CLR_ACCENT2}; }}
#PrimaryBtn:pressed{{ opacity: 0.8; }}
#SecondaryBtn, #DangerBtn {{
    background: {CLR_CARD};
    color: {CLR_TEXT};
    border: 1px solid {CLR_BORDER};
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 14px;
}}
#SecondaryBtn:hover {{ background: {CLR_ACCENT}33; border-color: {CLR_ACCENT}; }}
#DangerBtn:hover    {{ background: #ef444433; border-color: #ef4444; color: #ef4444; }}
"""

DIALOG_STYLE = f"""
QDialog, QWidget {{
    background: {CLR_BG};
    color: {CLR_TEXT};
    font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
    font-size: 14px;
}}
QGroupBox {{
    border: 1px solid {CLR_BORDER};
    border-radius: 8px;
    margin-top: 8px;
    padding-top: 8px;
    color: {CLR_SUBTEXT};
    font-size: 13px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
}}
QSpinBox, QComboBox, QTextEdit, QLineEdit {{
    background: {CLR_CARD};
    border: 1px solid {CLR_BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    color: {CLR_TEXT};
    selection-background-color: {CLR_ACCENT};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: {CLR_BORDER};
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background: {CLR_CARD};
    border: 1px solid {CLR_BORDER};
    selection-background-color: {CLR_ACCENT};
}}
QPushButton {{
    background: {CLR_CARD};
    color: {CLR_TEXT};
    border: 1px solid {CLR_BORDER};
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 14px;
}}
QPushButton:hover {{ background: {CLR_BORDER}; }}
#AccentBtn {{
    background: {CLR_ACCENT};
    color: white;
    border: none;
    font-weight: bold;
}}
#AccentBtn:hover {{ background: {CLR_ACCENT2}; }}
"""

TRAY_MENU_STYLE = f"""
QMenu {{
    background: {CLR_CARD};
    color: {CLR_TEXT};
    border: 1px solid {CLR_BORDER};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{ padding: 7px 20px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {CLR_ACCENT}44; }}
QMenu::separator {{ height: 1px; background: {CLR_BORDER}; margin: 4px 8px; }}
"""


# ═══════════════════════════════════════════════════════════
# 单实例检查（Windows）
# ═══════════════════════════════════════════════════════════
def _check_single_instance():
    if platform.system() != "Windows":
        return True
    try:
        import ctypes
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, APP_NAME)
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return False
    except Exception:
        pass
    return True


# ═══════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════
def main():
    if not _check_single_instance():
        app = QApplication(sys.argv)
        QMessageBox.warning(
            None, APP_NAME,
            "程序已在运行中！\n请在任务栏找到托盘图标。"
        )
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    # 检查系统托盘可用性
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_NAME, "系统不支持托盘图标，部分功能可能受限。")

    cfg    = Config()
    window = MainWindow(cfg)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
