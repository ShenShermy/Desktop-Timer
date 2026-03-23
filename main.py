#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os, json, platform, math
from datetime import date

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDialog, QSpinBox, QComboBox,
    QTextEdit, QGroupBox, QSystemTrayIcon, QMenu, QAction,
    QMessageBox, QFrame, QProgressBar, QScrollArea,
    QGraphicsDropShadowEffect, QSizePolicy, QSpacerItem,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QEvent
from PyQt5.QtGui import QIcon, QFont, QPixmap, QPainter, QColor, QBrush, QPen

APP_NAME    = "\u4f11\u606f\u63d0\u9192\u52a9\u624b"
VERSION     = "1.1.0"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".break_reminder.json")
UNITS     = ["\u79d2", "\u5206\u949f", "\u5c0f\u65f6"]
UNIT_SECS = [1, 60, 3600]
DEFAULT_CONFIG = {
    "work_value": 60, "work_unit": 1,
    "break_value": 15, "break_unit": 1,
    "reminder_text": "\u8be5\u4f11\u606f\u4e00\u4e0b\u4e86\uff01\U0001f440\u653e\u677e\u773c\u775b\uff0c\u8d77\u6765\u63d0\u809b\uff01",
    "stats_date": "", "stats_count": 0,
}
C = {
    "bg": "#1a1d2e", "card": "#252840", "accent": "#6c63ff",
    "accent2": "#a78bfa", "ok": "#4ade80", "warn": "#fb923c",
    "text": "#e2e8f0", "sub": "#94a3b8", "border": "#334155",
    "scroll": "#3a3f5c",
}

def to_secs(v, u): return v * UNIT_SECS[u]
def fmt_time(s):
    s = max(0, int(s))
    h, r = divmod(s, 3600); m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def make_icon(color, size=64):
    px = QPixmap(size, size); px.fill(Qt.transparent)
    p = QPainter(px); p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
    p.drawEllipse(4, 4, size-8, size-8)
    cx = cy = size//2
    pen = QPen(Qt.white, max(2, size//16)); pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(cx, cy, cx+int(12*math.sin(math.radians(30))), cy-int(12*math.cos(math.radians(30))))
    p.drawLine(cx, cy, cx+10, cy)
    p.end(); return QIcon(px)

def play_sound():
    if platform.system() == "Windows":
        try:
            import winsound; winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except: pass

class Config:
    def __init__(self):
        self.data = DEFAULT_CONFIG.copy(); self._load()
    def _load(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH,"r",encoding="utf-8") as f:
                    self.data.update(json.load(f))
        except: pass
    def save(self):
        try:
            with open(CONFIG_PATH,"w",encoding="utf-8") as f:
                json.dump(self.data,f,ensure_ascii=False,indent=2)
        except: pass
    def __getitem__(self,k): return self.data[k]
    def __setitem__(self,k,v): self.data[k]=v
    @property
    def work_secs(self): return to_secs(self.data["work_value"], self.data["work_unit"])
    @property
    def break_secs(self): return to_secs(self.data["break_value"], self.data["break_unit"])
    def today_count(self):
        today = str(date.today())
        if self.data["stats_date"] != today:
            self.data["stats_date"] = today; self.data["stats_count"] = 0
        return self.data["stats_count"]
    def add_break(self):
        self.today_count(); self.data["stats_count"] += 1; self.save()

class ReminderDialog(QDialog):
    dismissed = pyqtSignal()
    def __init__(self, text, duration, parent=None):
        super().__init__(parent, Qt.WindowStaysOnTopHint|Qt.FramelessWindowHint|Qt.Dialog)
        self.duration = duration; self.remaining = duration; self._drag_pos = None
        self._setup_ui(text); self._start_timer(); self._center(); play_sound()
    def _setup_ui(self, text):
        self.setMinimumSize(440, 300); self.resize(460, 320)
        self.setAttribute(Qt.WA_TranslucentBackground)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        card = QFrame(self); card.setObjectName("RCard")
        card.setStyleSheet("""
            #RCard{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #6c63ff,stop:1 #a855f7);border-radius:20px;}
            QLabel{color:white;background:transparent;}
            QPushButton{background:rgba(255,255,255,.18);color:white;border:2px solid rgba(255,255,255,.35);border-radius:10px;padding:8px 22px;font-size:14px;font-weight:bold;}
            QPushButton:hover{background:rgba(255,255,255,.32);}
            QProgressBar{background:rgba(255,255,255,.20);border-radius:5px;border:none;}
            QProgressBar::chunk{background:rgba(255,255,255,.80);border-radius:5px;}
        """)
        shadow = QGraphicsDropShadowEffect(); shadow.setBlurRadius(40)
        shadow.setOffset(0,8); shadow.setColor(QColor(0,0,0,120)); card.setGraphicsEffect(shadow)
        vbox = QVBoxLayout(card); vbox.setContentsMargins(36,30,36,28); vbox.setSpacing(10)
        t = QLabel("\U0001f514  \u4f11\u606f\u65f6\u95f4\u5230\uff01")
        t.setFont(QFont("Microsoft YaHei",18,QFont.Bold)); t.setAlignment(Qt.AlignCenter); vbox.addWidget(t)
        msg = QLabel(text); msg.setFont(QFont("Microsoft YaHei",12))
        msg.setAlignment(Qt.AlignCenter); msg.setWordWrap(True); vbox.addWidget(msg)
        vbox.addSpacing(4)
        self.lbl_count = QLabel()
        self.lbl_count.setFont(QFont("Consolas",32,QFont.Bold))
        self.lbl_count.setAlignment(Qt.AlignCenter); vbox.addWidget(self.lbl_count)
        self.bar = QProgressBar(); self.bar.setRange(0,self.duration); self.bar.setValue(self.duration)
        self.bar.setTextVisible(False); self.bar.setFixedHeight(10); vbox.addWidget(self.bar)
        vbox.addSpacing(4)
        row = QHBoxLayout()
        b1 = QPushButton("\u23ed  \u8df3\u8fc7\u672c\u6b21"); b2 = QPushButton("\u2705  \u63d0\u524d\u7ed3\u675f")
        b1.clicked.connect(self._dismiss); b2.clicked.connect(self._dismiss)
        row.addWidget(b1); row.addWidget(b2); vbox.addLayout(row)
        outer.addWidget(card); self._refresh()
    def _start_timer(self):
        self._t = QTimer(self); self._t.timeout.connect(self._tick); self._t.start(1000)
    def _tick(self):
        self.remaining -= 1; self._refresh()
        if self.remaining <= 0: self._dismiss()
    def _refresh(self):
        self.lbl_count.setText(fmt_time(self.remaining)); self.bar.setValue(self.remaining)
    def _dismiss(self):
        self._t.stop(); self.dismissed.emit(); self.close()
    def _center(self):
        sg = QApplication.primaryScreen().geometry()
        self.move((sg.width()-self.width())//2, (sg.height()-self.height())//2)
    def mousePressEvent(self, e):
        if e.button()==Qt.LeftButton:
            self._drag_pos = e.globalPos()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if e.buttons()==Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos()-self._drag_pos)

class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent); self.cfg = cfg
        self.setWindowTitle("\u2699  \u8bbe\u7f6e")
        self.setMinimumSize(380,360); self.resize(420,380)
        self.setStyleSheet(DIALOG_CSS); self._build()
    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(24,24,24,20); root.setSpacing(14)
        wg = QGroupBox("\u23f1  \u5de5\u4f5c\u95f4\u9694"); wl = QHBoxLayout(wg)
        self.w_val = QSpinBox(); self.w_val.setRange(1,9999); self.w_val.setValue(self.cfg["work_value"])
        self.w_unit = QComboBox(); self.w_unit.addItems(UNITS); self.w_unit.setCurrentIndex(self.cfg["work_unit"])
        wl.addWidget(QLabel("\u6bcf\u9694")); wl.addWidget(self.w_val); wl.addWidget(self.w_unit)
        wl.addWidget(QLabel("\u63d0\u9192\u4e00\u6b21")); wl.addStretch(); root.addWidget(wg)
        bg = QGroupBox("\U0001f60c  \u4f11\u606f\u65f6\u957f"); bl = QHBoxLayout(bg)
        self.b_val = QSpinBox(); self.b_val.setRange(1,9999); self.b_val.setValue(self.cfg["break_value"])
        self.b_unit = QComboBox(); self.b_unit.addItems(UNITS); self.b_unit.setCurrentIndex(self.cfg["break_unit"])
        bl.addWidget(QLabel("\u4f11\u606f")); bl.addWidget(self.b_val); bl.addWidget(self.b_unit)
        bl.addStretch(); root.addWidget(bg)
        tg = QGroupBox("\U0001f4dd  \u63d0\u9192\u6587\u672c"); tl = QVBoxLayout(tg)
        self.txt = QTextEdit(); self.txt.setPlainText(self.cfg["reminder_text"]); self.txt.setMinimumHeight(80)
        tl.addWidget(self.txt); root.addWidget(tg)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet(f"color:{C['border']};"); root.addWidget(sep)
        btns = QHBoxLayout()
        ok = QPushButton("  \u4fdd\u5b58"); ok.setObjectName("AccentBtn")
        can = QPushButton("\u53d6\u6d88")
        ok.clicked.connect(self._save); can.clicked.connect(self.reject)
        btns.addStretch(); btns.addWidget(can); btns.addWidget(ok); root.addLayout(btns)
    def _save(self):
        self.cfg["work_value"]=self.w_val.value(); self.cfg["work_unit"]=self.w_unit.currentIndex()
        self.cfg["break_value"]=self.b_val.value(); self.cfg["break_unit"]=self.b_unit.currentIndex()
        self.cfg["reminder_text"]=self.txt.toPlainText().strip() or "\u8be5\u4f11\u606f\u4e86\uff01"
        self.cfg.save(); self.accept()

class MainWindow(QMainWindow):
    S_STOPPED="stopped"; S_WORKING="working"; S_REMINDING="reminding"; S_PAUSED="paused"
    def __init__(self, cfg):
        super().__init__(); self.cfg=cfg; self.state=self.S_STOPPED
        self.remaining=0; self._reminder=None
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(360,480); self.resize(420,580)
        self.setStyleSheet(MAIN_CSS)
        self._build_ui(); self._build_tray()
        self._ticker=QTimer(self); self._ticker.timeout.connect(self._tick)
    def _build_ui(self):
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea{{background:{C['bg']};border:none;}}
            QScrollBar:vertical{{background:{C['card']};width:8px;border-radius:4px;margin:0;}}
            QScrollBar::handle:vertical{{background:{C['scroll']};border-radius:4px;min-height:30px;}}
            QScrollBar::handle:vertical:hover{{background:{C['accent']};}}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
        """)
        content=QWidget(); content.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        scroll.setWidget(content); self.setCentralWidget(scroll)
        root=QVBoxLayout(content); root.setContentsMargins(28,22,28,22); root.setSpacing(12)
        # header
        hdr=QHBoxLayout()
        lbl_title=QLabel(f"\u23f0  {APP_NAME}"); lbl_title.setObjectName("AppTitle")
        lbl_title.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        self.lbl_state=QLabel("\u5c31\u7eea"); self.lbl_state.setObjectName("StateTag")
        hdr.addWidget(lbl_title,1); hdr.addWidget(self.lbl_state); root.addLayout(hdr)
        # timer card
        card=QFrame(); card.setObjectName("TimerCard")
        card.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        cl=QVBoxLayout(card); cl.setContentsMargins(24,20,24,20); cl.setSpacing(8)
        self.lbl_phase=QLabel("\u51c6\u5907\u5f00\u59cb"); self.lbl_phase.setObjectName("PhaseLabel")
        self.lbl_phase.setAlignment(Qt.AlignCenter); cl.addWidget(self.lbl_phase)
        self.lbl_time=QLabel("--:--"); self.lbl_time.setObjectName("BigTimer")
        self.lbl_time.setAlignment(Qt.AlignCenter)
        self.lbl_time.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        cl.addWidget(self.lbl_time)
        self.progress=QProgressBar(); self.progress.setObjectName("MainProgress")
        self.progress.setTextVisible(False); self.progress.setFixedHeight(8); self.progress.setValue(0)
        cl.addWidget(self.progress); root.addWidget(card)
        # stat card
        sc=QFrame(); sc.setObjectName("StatCard")
        sc.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        sl=QHBoxLayout(sc); sl.setContentsMargins(20,14,20,14)
        self.lbl_stats=QLabel(); self.lbl_stats.setObjectName("StatsLabel")
        self.lbl_stats.setAlignment(Qt.AlignCenter)
        self.lbl_stats.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        sl.addWidget(self.lbl_stats); self._refresh_stats(); root.addWidget(sc)
        # config preview card
        cc=QFrame(); cc.setObjectName("CfgCard")
        cc.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        cv=QVBoxLayout(cc); cv.setContentsMargins(20,14,20,14); cv.setSpacing(6)
        ct=QLabel("\U0001f4cb  \u5f53\u524d\u8bbe\u7f6e"); ct.setObjectName("CfgTitle"); cv.addWidget(ct)
        self.lbl_cfg=QLabel(); self.lbl_cfg.setObjectName("CfgDetail")
        self.lbl_cfg.setWordWrap(True)
        self.lbl_cfg.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        cv.addWidget(self.lbl_cfg); self._refresh_cfg(); root.addWidget(cc)
        # spacer
        root.addItem(QSpacerItem(0,10,QSizePolicy.Minimum,QSizePolicy.Expanding))
        # primary btn
        self.btn_start=QPushButton("\u25b6  \u5f00\u59cb"); self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.btn_start.setMinimumHeight(50); self.btn_start.clicked.connect(self._on_start_pause)
        root.addWidget(self.btn_start)
        # secondary btns
        br=QHBoxLayout(); br.setSpacing(10)
        self.btn_settings=QPushButton("\u2699  \u8bbe\u7f6e"); self.btn_settings.setObjectName("SecondaryBtn")
        self.btn_settings.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.btn_settings.setMinimumHeight(42); self.btn_settings.clicked.connect(self._open_settings)
        btn_exit=QPushButton("\u2715  \u9000\u51fa"); btn_exit.setObjectName("DangerBtn")
        btn_exit.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        btn_exit.setMinimumHeight(42); btn_exit.clicked.connect(self._quit)
        br.addWidget(self.btn_settings,1); br.addWidget(btn_exit,1); root.addLayout(br)
        hint=QLabel("\u5f00\u59cb\u540e\u53ef\u6700\u5c0f\u5316\u5230\u7cfb\u7edf\u6258\u76d8\uff0c\u53cc\u51fb\u56fe\u6807\u5524\u56de")
        hint.setObjectName("HintLabel"); hint.setAlignment(Qt.AlignCenter); hint.setWordWrap(True)
        root.addWidget(hint)
    def _refresh_cfg(self):
        wv=self.cfg["work_value"]; wu=UNITS[self.cfg["work_unit"]]
        bv=self.cfg["break_value"]; bu=UNITS[self.cfg["break_unit"]]
        txt=self.cfg["reminder_text"].replace("\n"," ")[:40]
        self.lbl_cfg.setText(f"\u5de5\u4f5c\u95f4\u9694\uff1a\u6bcf {wv} {wu}\u63d0\u9192\u4e00\u6b21\n\u4f11\u606f\u65f6\u957f\uff1a{bv} {bu}\n\u63d0\u9192\u6587\u672c\uff1a{txt}...")
    def _build_tray(self):
        self._tray=QSystemTrayIcon(self); self._tray.setIcon(make_icon(C["accent"]))
        self._tray.setToolTip(APP_NAME); menu=QMenu(); menu.setStyleSheet(TRAY_CSS)
        act_show=QAction("\U0001f4cb  \u663e\u793a\u4e3b\u7a97\u53e3",self)
        self._act_pause=QAction("\u23f8  \u6682\u505c\u8ba1\u65f6",self)
        act_quit=QAction("\u2715  \u9000\u51fa\u7a0b\u5e8f",self)
        act_show.triggered.connect(self._restore)
        self._act_pause.triggered.connect(self._on_start_pause)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_show); menu.addAction(self._act_pause); menu.addSeparator(); menu.addAction(act_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(lambda r: self._restore() if r==QSystemTrayIcon.DoubleClick else None)
        self._tray.show()
    def _tick(self):
        self.remaining-=1; self._refresh_display()
        if self.remaining<=0:
            if self.state==self.S_WORKING: self._enter_reminding()
            elif self.state==self.S_REMINDING: self._enter_working()
    def _enter_working(self):
        self.state=self.S_WORKING; self.remaining=self.cfg.work_secs; self._ticker.start(1000)
        if self._reminder: self._reminder.close(); self._reminder=None
        self._tray.setIcon(make_icon(C["ok"])); self._tray.setToolTip(f"{APP_NAME} \u00b7 \u5de5\u4f5c\u4e2d")
        self._act_pause.setText("\u23f8  \u6682\u505c\u8ba1\u65f6"); self._update_state_ui()
    def _enter_reminding(self):
        self.cfg.add_break(); self._refresh_stats()
        self.state=self.S_REMINDING; self.remaining=self.cfg.break_secs; self._ticker.stop()
        self._tray.setIcon(make_icon(C["warn"])); self._tray.setToolTip(f"{APP_NAME} \u00b7 \u4f11\u606f\u4e2d")
        self._tray.showMessage(APP_NAME,self.cfg["reminder_text"][:60],QSystemTrayIcon.Information,3000)
        self._reminder=ReminderDialog(self.cfg["reminder_text"],self.cfg.break_secs)
        self._reminder.dismissed.connect(self._enter_working)
        self._reminder.show(); self._reminder.activateWindow(); self._reminder.raise_()
        self._update_state_ui()
    def _on_start_pause(self):
        if self.state==self.S_STOPPED:
            self._enter_working(); self.btn_start.setText("\u23f8  \u6682\u505c"); self.btn_settings.setEnabled(False); self._refresh_cfg()
        elif self.state==self.S_WORKING:
            self.state=self.S_PAUSED; self._ticker.stop(); self.btn_start.setText("\u25b6  \u7ee7\u7eed")
            self._tray.setIcon(make_icon(C["sub"])); self._act_pause.setText("\u25b6  \u7ee7\u7eed\u8ba1\u65f6"); self._update_state_ui()
        elif self.state==self.S_PAUSED:
            self.state=self.S_WORKING; self._ticker.start(1000); self.btn_start.setText("\u23f8  \u6682\u505c")
            self._tray.setIcon(make_icon(C["ok"])); self._act_pause.setText("\u23f8  \u6682\u505c\u8ba1\u65f6"); self._update_state_ui()
    def _refresh_display(self):
        self.lbl_time.setText(fmt_time(self.remaining))
        total=self.cfg.work_secs if self.state in (self.S_WORKING,self.S_PAUSED) else self.cfg.break_secs
        if total>0:
            self.progress.setRange(0,100); self.progress.setValue(int(self.remaining/total*100))
    def _update_state_ui(self):
        d={self.S_STOPPED:("\u5c31\u7eea","\u51c6\u5907\u5f00\u59cb",C["accent"]),
           self.S_WORKING:("\u5de5\u4f5c\u4e2d","\u8ddd\u4e0b\u6b21\u4f11\u606f",C["ok"]),
           self.S_REMINDING:("\u4f11\u606f\u4e2d","\u4f11\u606f\u5269\u4f59",C["warn"]),
           self.S_PAUSED:("\u5df2\u6682\u505c","\u8ddd\u4e0b\u6b21\u4f11\u606f\uff08\u6682\u505c\uff09",C["sub"])}
        tag,phase,color=d.get(self.state,("","",C["accent"]))
        self.lbl_state.setText(tag)
        self.lbl_state.setStyleSheet(f"background:{color}22;color:{color};border:1px solid {color}66;border-radius:6px;padding:2px 10px;font-size:12px;font-weight:bold;")
        self.lbl_phase.setText(phase); self._refresh_display()
    def _refresh_stats(self):
        self.lbl_stats.setText(f"\U0001f3c6  \u4eca\u65e5\u5df2\u5b8c\u6210\u4f11\u606f\uff1a{self.cfg.today_count()} \u6b21")
    def _open_settings(self):
        dlg=SettingsDialog(self.cfg,self)
        if dlg.exec_()==QDialog.Accepted: self._refresh_cfg()
    def closeEvent(self, e):
        if self.state==self.S_STOPPED: e.accept(); return
        box=QMessageBox(self); box.setWindowTitle(APP_NAME)
        box.setText("\u4f60\u60f3\u505a\u4ec0\u4e48\uff1f"); box.setStyleSheet(DIALOG_CSS)
        btn_tray=box.addButton("\u6700\u5c0f\u5316\u5230\u6258\u76d8",QMessageBox.ActionRole)
        btn_quit=box.addButton("\u9000\u51fa\u7a0b\u5e8f",QMessageBox.DestructiveRole)
        box.addButton("\u53d6\u6d88",QMessageBox.RejectRole); box.exec_()
        clicked=box.clickedButton()
        if clicked==btn_tray: e.ignore(); self.hide()
        elif clicked==btn_quit: e.accept(); self._do_quit()
        else: e.ignore()
    def changeEvent(self, e):
        if e.type()==QEvent.WindowStateChange:
            if self.isMinimized() and self.state!=self.S_STOPPED: self.hide()
        super().changeEvent(e)
    def _restore(self): self.showNormal(); self.activateWindow(); self.raise_()
    def _quit(self): self._do_quit()
    def _do_quit(self): self._ticker.stop(); self.cfg.save(); self._tray.hide(); QApplication.quit()

MAIN_CSS = f"""
QMainWindow,QWidget{{background:{C['bg']};color:{C['text']};font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif;font-size:14px;}}
#AppTitle{{font-size:18px;font-weight:bold;color:{C['text']};}}
#StateTag{{font-size:12px;}}
#TimerCard{{background:{C['card']};border:1px solid {C['border']};border-radius:14px;}}
#PhaseLabel{{font-size:13px;color:{C['sub']};}}
#BigTimer{{font-size:52px;font-weight:bold;color:{C['text']};font-family:"Consolas","Courier New",monospace;letter-spacing:2px;padding:6px 0;}}
#MainProgress{{background:{C['bg']};border-radius:4px;border:none;}}
#MainProgress::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {C['accent']},stop:1 {C['accent2']});border-radius:4px;}}
#StatCard{{background:{C['card']};border:1px solid {C['border']};border-radius:14px;}}
#StatsLabel{{font-size:14px;color:{C['text']};}}
#CfgCard{{background:{C['card']};border:1px solid {C['border']};border-radius:14px;}}
#CfgTitle{{font-size:13px;font-weight:bold;color:{C['sub']};}}
#CfgDetail{{font-size:13px;color:{C['text']};line-height:1.6;}}
#PrimaryBtn{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {C['accent']},stop:1 {C['accent2']});color:white;border:none;border-radius:12px;font-size:16px;font-weight:bold;padding:12px;}}
#PrimaryBtn:hover{{background:{C['accent2']};}}
#SecondaryBtn{{background:{C['card']};color:{C['text']};border:1px solid {C['border']};border-radius:10px;font-size:14px;padding:10px;}}
#SecondaryBtn:hover{{background:{C['accent']}33;border-color:{C['accent']};}}
#SecondaryBtn:disabled{{color:{C['border']};}}
#DangerBtn{{background:{C['card']};color:{C['text']};border:1px solid {C['border']};border-radius:10px;font-size:14px;padding:10px;}}
#DangerBtn:hover{{background:#ef444433;border-color:#ef4444;color:#ef4444;}}
#HintLabel{{font-size:11px;color:{C['border']};margin-top:2px;}}
"""

DIALOG_CSS = f"""
QDialog,QWidget{{background:{C['bg']};color:{C['text']};font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif;font-size:14px;}}
QGroupBox{{border:1px solid {C['border']};border-radius:8px;margin-top:8px;padding-top:8px;color:{C['sub']};font-size:13px;}}
QGroupBox::title{{subcontrol-origin:margin;subcontrol-position:top left;padding:0 6px;}}
QSpinBox,QComboBox,QTextEdit{{background:{C['card']};border:1px solid {C['border']};border-radius:6px;padding:4px 8px;color:{C['text']};selection-background-color:{C['accent']};}}
QComboBox::drop-down{{border:none;}}
QComboBox QAbstractItemView{{background:{C['card']};border:1px solid {C['border']};selection-background-color:{C['accent']};}}
QPushButton{{background:{C['card']};color:{C['text']};border:1px solid {C['border']};border-radius:8px;padding:8px 20px;font-size:14px;}}
QPushButton:hover{{background:{C['border']};}}
#AccentBtn{{background:{C['accent']};color:white;border:none;font-weight:bold;}}
#AccentBtn:hover{{background:{C['accent2']};}}
"""

TRAY_CSS = f"""
QMenu{{background:{C['card']};color:{C['text']};border:1px solid {C['border']};border-radius:8px;padding:4px;}}
QMenu::item{{padding:7px 20px 7px 12px;border-radius:6px;}}
QMenu::item:selected{{background:{C['accent']}44;}}
QMenu::separator{{height:1px;background:{C['border']};margin:4px 8px;}}
"""

def _single_instance():
    if platform.system()!="Windows": return True
    try:
        import ctypes; ctypes.windll.kernel32.CreateMutexW(None,False,APP_NAME)
        return ctypes.windll.kernel32.GetLastError()!=183
    except: return True

def main():
    if hasattr(Qt,"AA_EnableHighDpiScaling"): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling,True)
    if hasattr(Qt,"AA_UseHighDpiPixmaps"): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,True)
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setQuitOnLastWindowClosed(False)
    if not _single_instance():
        QMessageBox.warning(None,APP_NAME,"\u7a0b\u5e8f\u5df2\u5728\u8fd0\u884c\u4e2d\uff01\n\u8bf7\u5728\u4efb\u52a1\u680f\u627e\u5230\u6258\u76d8\u56fe\u6807\u3002"); sys.exit(0)
    cfg=Config(); window=MainWindow(cfg); window.show(); sys.exit(app.exec_())

if __name__=="__main__":
    main()
