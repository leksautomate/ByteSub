# ByteSub - Fast Whisper Translator Pro

import os
import json
import ffmpeg
import yt_dlp
import re
from faster_whisper import WhisperModel
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout,
    QProgressBar, QMessageBox, QTextEdit, QComboBox, QCheckBox, QLineEdit, QSpacerItem, QSizePolicy, QSplashScreen
)
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor, QPixmap
from PyQt6.QtCore import Qt, QSettings, QMimeData, QTimer

MODEL_SIZE = "medium"
SUPPORTED_LANGUAGES = {"English": "en"}
SETTINGS_PATH = "settings.ini"

class ByteSubApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setWindowTitle("ByteSub - AI Subtitle & Transcript Generator")
        self.setFixedSize(800, 650)
        self.setWindowIcon(QIcon("app_logo.png"))

        self.settings = QSettings(SETTINGS_PATH, QSettings.Format.IniFormat)
        self.output_folder = self.settings.value("output_folder", os.getcwd())
        self.theme = self.settings.value("theme", "light")
        self.keep_tiktok = self.settings.value("keep_tiktok", "false") == "true"

        self.model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        self.selected_language = "en"

        self.input_files = []
        self.tiktok_url = ""

        self.initUI()
        self.apply_theme()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self.title = QLabel("🎧 ByteSub")
        self.title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        layout.addItem(QSpacerItem(10, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste TikTok video URL or leave empty")
        layout.addWidget(self.url_input)

        file_buttons = QHBoxLayout()
        self.pick_files_btn = QPushButton("📂 Add Media Files")
        self.pick_files_btn.clicked.connect(self.select_files)
        self.pick_folder_btn = QPushButton("📁 Add Folder")
        self.pick_folder_btn.clicked.connect(self.select_folder)
        file_buttons.addWidget(self.pick_files_btn)
        file_buttons.addWidget(self.pick_folder_btn)
        layout.addLayout(file_buttons)

        self.transcribe_btn = QPushButton("🚀 Transcribe Now")
        self.transcribe_btn.setStyleSheet("padding: 10px; font-weight: bold;")
        self.transcribe_btn.clicked.connect(self.transcribe_handler)
        layout.addWidget(self.transcribe_btn)

        self.output_button = QPushButton("📁 Set Output Folder")
        self.output_button.clicked.connect(self.set_output_folder)
        layout.addWidget(self.output_button)

        options_layout = QHBoxLayout()
        self.theme_toggle = QPushButton("🌓 Toggle Theme")
        self.theme_toggle.clicked.connect(self.toggle_theme)
        self.keep_check = QCheckBox("Keep TikTok video after processing")
        self.keep_check.setChecked(self.keep_tiktok)
        options_layout.addWidget(self.theme_toggle)
        options_layout.addWidget(self.keep_check)
        layout.addLayout(options_layout)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.preview = QTextEdit()
        self.preview.setFont(QFont("Courier New", 10))
        self.preview.setStyleSheet("border: 1px solid #ccc; padding: 5px;")
        layout.addWidget(self.preview)

        self.status = QLabel("Ready.")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        # About section
        about_layout = QHBoxLayout()
        self.about_btn = QPushButton("ℹ️ About")
        self.about_btn.clicked.connect(self.show_about)
        about_layout.addWidget(self.about_btn)
        layout.addLayout(about_layout)

        self.setLayout(layout)

    def apply_theme(self):
        dark = self.theme == "dark"
        p = self.palette()
        if dark:
            p.setColor(QPalette.ColorRole.Window, QColor("#2b2b2b"))
            p.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
        else:
            # Blue theme for light mode based on provided design
            p.setColor(QPalette.ColorRole.Window, QColor("#003366"))  # Deep blue background
            p.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))  # White text
        self.setPalette(p)

    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self.apply_theme()

    def set_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder
            self.settings.setValue("output_folder", folder)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.input_files.extend([u.toLocalFile() for u in event.mimeData().urls()])
        self.status.setText(f"{len(self.input_files)} file(s) ready to transcribe")

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose Media Files", "", "Media Files (*.mp4 *.mp3 *.wav *.mkv *.mov)")
        self.input_files.extend(files)
        self.status.setText(f"{len(self.input_files)} file(s) ready to transcribe")

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Folder")
        if folder:
            media_files = [os.path.join(folder, f) for f in os.listdir(folder)
                           if f.lower().endswith(('.mp4', '.mp3', '.wav', '.mkv', '.mov'))]
            self.input_files.extend(media_files)
            self.status.setText(f"{len(self.input_files)} file(s) ready to transcribe")

    def transcribe_handler(self):
        url = self.url_input.text().strip()
        if url:
            self.download_tiktok(url)
        elif self.input_files:
            self.process_files(self.input_files)
        else:
            QMessageBox.warning(self, "No Input", "Please paste a TikTok URL or add media files.")

    def download_tiktok(self, url):
        output_file = "tiktok_video.mp4"
        try:
            self.status.setText("Downloading TikTok video...")
            with yt_dlp.YoutubeDL({"outtmpl": output_file}) as ydl:
                ydl.download([url])
            self.process_files([output_file])
            if not self.keep_check.isChecked():
                os.remove(output_file)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
        self.url_input.clear()

    def process_files(self, files):
        self.progress.setMaximum(len(files))
        for idx, path in enumerate(files):
            try:
                self.status.setText(f"Processing: {os.path.basename(path)}")
                base = os.path.splitext(os.path.basename(path))[0]
                audio = f"temp_{base}.wav"
                ffmpeg.input(path).output(audio, ac=1, ar='16000').overwrite_output().run(quiet=True)

                segments, _ = self.model.transcribe(audio, task="translate", language="en", beam_size=5)
                os.remove(audio)

                transcript = " ".join([s.text.strip() for s in segments])
                filename = "_".join(re.findall(r"\w+", transcript)[:3]) or "output"

                srt_path = QFileDialog.getSaveFileName(self, "Save SRT File", os.path.join(self.output_folder, f"{filename}.srt"), "SRT Files (*.srt)")[0]
                txt_path = QFileDialog.getSaveFileName(self, "Save Text File", os.path.join(self.output_folder, f"{filename}.txt"), "Text Files (*.txt)")[0]

                with open(srt_path, "w", encoding="utf-8") as srt:
                    for i, seg in enumerate(segments, 1):
                        srt.write(f"{i}\n{self.fmt(seg.start)} --> {self.fmt(seg.end)}\n{seg.text.strip()}\n\n")

                with open(txt_path, "w", encoding="utf-8") as txt:
                    txt.write(transcript)

                self.preview.setText(f"{transcript}\n\n-- Subtitles Preview --\n\n" + "\n".join([seg.text.strip() for seg in segments]))
                self.progress.setValue(idx + 1)
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

        self.status.setText("✅ Done. All files processed.")
        self.settings.setValue("theme", self.theme)
        self.settings.setValue("keep_tiktok", "true" if self.keep_check.isChecked() else "false")
        self.input_files.clear()

    def show_about(self):
        about_text = """
        <h2>ByteSub - AI Subtitle & Transcript Generator</h2>
        <p><b>Developed by:</b> Leksautomate</p>
        <br>
        <p><b>Follow us on social media:</b></p>
        <p>🎥 YouTube: <a href="https://youtube.com/@leksautomate">@leksautomate</a></p>
        <p>🐦 Twitter: <a href="https://twitter.com/leksautomate">@leksautomate</a></p>
        <p>📱 TikTok: <a href="https://tiktok.com/@leksautomate">@leksautomate</a></p>
        <p>📧 Email: <a href="mailto:leksautomate@gmail.com">leksautomate@gmail.com</a></p>
        <br>
        <p>This application uses AI-powered speech recognition to generate accurate subtitles and transcripts from your media files.</p>
        """
        
        msg = QMessageBox()
        msg.setWindowTitle("About ByteSub")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(about_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def fmt(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

if __name__ == "__main__":
    app = QApplication([])
    splash = QSplashScreen(QPixmap("splash.png"))
    splash.showMessage("ByteSub is launching...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.white)
    splash.show()
    QTimer.singleShot(1500, splash.close)
    window = ByteSubApp()
    QTimer.singleShot(1600, window.show)
    app.exec()
