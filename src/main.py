import sys
import json
import socket
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QGroupBox, QDoubleSpinBox, QMessageBox, QTabWidget, QFormLayout)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, QThread, Signal, Slot, QTimer
from tile_downloader import download_tiles

class UdpListenerThread(QThread):
    telemetry_received = Signal(float, float, float) # lat, lng, heading

    def __init__(self, port=5017, parent=None):
        super().__init__(parent)
        self.port = port
        self.running = True

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', self.port))
        sock.settimeout(1.0)
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                if data:
                    parsed = json.loads(data.decode('utf-8'))
                    if 'latitude' in parsed and 'longitude' in parsed and 'heading_degree' in parsed:
                        self.telemetry_received.emit(float(parsed['latitude']), float(parsed['longitude']), float(parsed['heading_degree']))
            except socket.timeout:
                continue
            except Exception as e:
                print(f"UDP Error: {e}")
                
        sock.close()

    def stop(self):
        self.running = False
        self.wait()

class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Delivery Dashboard")
        self.resize(1024, 768)
        
        # Apply dark mode theme
        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; color: #ffffff; }
            QWidget { background-color: #2b2b2b; color: #ffffff; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
            QTabWidget::pane { border: 1px solid #444; background: #333; border-radius: 4px; }
            QTabBar::tab { background: #2b2b2b; border: 1px solid #444; padding: 10px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #3c3f41; border-bottom-color: #3c3f41; }
            QLineEdit, QDoubleSpinBox { background: #3c3f41; border: 1px solid #555; padding: 8px; border-radius: 4px; color: #fff; }
            QLineEdit:focus, QDoubleSpinBox:focus { border: 1px solid #0d47a1; }
            QPushButton { background-color: #0d47a1; color: white; border: none; padding: 10px 16px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1565c0; }
            QPushButton:pressed { background-color: #0b3c88; }
            QPushButton:disabled { background-color: #555; color: #aaa; }
            QLabel { color: #eee; }
        """)

        # Main widget and layouts
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Left panel controls
        self.left_panel = QWidget()
        self.left_panel.setFixedWidth(380)
        left_layout = QVBoxLayout()
        self.left_panel.setLayout(left_layout)
        
        self.tabs = QTabWidget()
        left_layout.addWidget(self.tabs)
        
        # 1. Map Downloader Tab
        self.init_downloader_tab()
        
        # 2. Waypoints Tab
        self.init_waypoints_tab()
        
        # 3. Telemetry Info Tab
        self.init_telemetry_tab()

        # Right panel - Map
        self.setup_map_view()
        main_layout.addWidget(self.left_panel)
        main_layout.addWidget(self.web_view, stretch=1)

        # Initialize UDP listener for backend script
        self.udp_thread = UdpListenerThread(port=5017)
        self.udp_thread.telemetry_received.connect(self.update_telemetry)
        self.udp_thread.start()
        
        # Simulator timer
        self.sim_timer = QTimer()
        self.sim_timer.timeout.connect(self.simulate_movement)
        self.sim_lat = 0
        self.sim_lng = 0
        self.sim_heading = 0

    def init_downloader_tab(self):
        tab = QWidget()
        layout = QFormLayout()
        layout.setSpacing(15)
        
        # Using QLineEdit instead of SpinBox for easy pasting
        self.center_lat_input = QLineEdit()
        self.center_lat_input.setPlaceholderText("e.g. 40.7128")
        
        self.center_lng_input = QLineEdit()
        self.center_lng_input.setPlaceholderText("e.g. -74.0060")
        
        self.radius_input = QDoubleSpinBox()
        self.radius_input.setRange(0.1, 100)
        self.radius_input.setValue(2.0)
        self.radius_input.setSuffix(" km")
        
        self.download_btn = QPushButton("Download Offline Map")
        self.download_btn.clicked.connect(self.download_map)
        
        layout.addRow("Center Lat:", self.center_lat_input)
        layout.addRow("Center Lng:", self.center_lng_input)
        layout.addRow("Radius:", self.radius_input)
        layout.addRow(self.download_btn)
        
        self.progress_lbl = QLabel("")
        layout.addRow(self.progress_lbl)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Map Config")

    def init_waypoints_tab(self):
        tab = QWidget()
        layout = QFormLayout()
        layout.setSpacing(15)
        
        self.wp_lat_input = QLineEdit()
        self.wp_lat_input.setPlaceholderText("e.g. 40.7135")
        
        self.wp_lng_input = QLineEdit()
        self.wp_lng_input.setPlaceholderText("e.g. -74.0075")
        
        self.add_wp_btn = QPushButton("Add Waypoint")
        self.add_wp_btn.clicked.connect(self.add_waypoint)
        
        self.clear_wp_btn = QPushButton("Clear Waypoints")
        self.clear_wp_btn.setStyleSheet("""
            QPushButton { background-color: #ab0000; }
            QPushButton:hover { background-color: #d32f2f; }
            QPushButton:pressed { background-color: #7f0000; }
        """)
        self.clear_wp_btn.clicked.connect(self.clear_waypoints)
        
        layout.addRow("WP Lat:", self.wp_lat_input)
        layout.addRow("WP Lng:", self.wp_lng_input)
        layout.addRow(self.add_wp_btn)
        layout.addRow(self.clear_wp_btn)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Waypoints")

    def init_telemetry_tab(self):
        tab = QWidget()
        layout = QFormLayout()
        layout.setSpacing(15)
        
        self.lbl_curr_lat = QLabel("---")
        self.lbl_curr_lng = QLabel("---")
        self.lbl_curr_hdg = QLabel("---")
        
        layout.addRow("Current Lat:", self.lbl_curr_lat)
        layout.addRow("Current Lng:", self.lbl_curr_lng)
        layout.addRow("Heading:", self.lbl_curr_hdg)
        
        info_lbl = QLabel("Listening on UDP port 5017")
        info_lbl.setStyleSheet("color: #81c784; font-weight: bold;")
        layout.addRow(info_lbl)
        
        # Simulator trigger
        self.sim_btn = QPushButton("Start/Stop Simulator")
        self.sim_btn.setStyleSheet("""
            QPushButton { background-color: #f57c00; }
            QPushButton:hover { background-color: #ff9800; }
            QPushButton:pressed { background-color: #e65100; }
        """)
        self.sim_btn.clicked.connect(self.toggle_simulator)
        layout.addRow(self.sim_btn)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Telemetry")

    def setup_map_view(self):
        self.web_view = QWebEngineView()
        # Load local HTML file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        map_html_path = os.path.join(base_dir, "map.html")
        self.web_view.setUrl(QUrl.fromLocalFile(map_html_path))

    def _get_float_val(self, line_edit, default=0.0):
        text = line_edit.text().replace(',', '').strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return None

    @Slot()
    def download_map(self):
        lat = self._get_float_val(self.center_lat_input)
        lng = self._get_float_val(self.center_lng_input)
        rad = self.radius_input.value()
        
        if lat is None or lng is None or (lat == 0 and lng == 0):
            QMessageBox.warning(self, "Invalid location", "Please enter valid numeric coordinates.")
            return
            
        self.download_btn.setEnabled(False)
        self.progress_lbl.setText("Calculating tiles...")
        QApplication.processEvents()
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tiles_dir = os.path.join(base_dir, "tiles")
        
        def update_progress(downloaded, total):
            percent = (downloaded / total) * 100 if total > 0 else 0
            self.progress_lbl.setText(f"Downloading... {downloaded}/{total} tiles ({percent:.1f}%)")
            QApplication.processEvents()
        
        try:
            download_tiles(lat, lng, rad, zoom_levels=[14, 15, 16, 17, 18, 19, 20, 21, 22], output_dir=tiles_dir, progress_callback=update_progress)
            self.progress_lbl.setText("Download Complete!")
            # Reload map in case tiles were updated
            self.web_view.reload()
            # Set map center to downloaded area
            self.web_view.page().runJavaScript(f"setMapCenter({lat}, {lng}, 15);")
        except Exception as e:
            self.progress_lbl.setText(f"Error: {e}")
            
        self.download_btn.setEnabled(True)

    @Slot()
    def add_waypoint(self):
        lat = self._get_float_val(self.wp_lat_input)
        lng = self._get_float_val(self.wp_lng_input)
        if lat is None or lng is None:
            QMessageBox.warning(self, "Invalid location", "Please enter valid numeric WP coordinates.")
            return
            
        js = f"addWaypoint({lat}, {lng});"
        self.web_view.page().runJavaScript(js)

    @Slot()
    def clear_waypoints(self):
        self.web_view.page().runJavaScript("clearWaypoints();")

    @Slot(float, float, float)
    def update_telemetry(self, lat, lng, heading):
        self.lbl_curr_lat.setText(f"{lat:.6f}")
        self.lbl_curr_lng.setText(f"{lng:.6f}")
        self.lbl_curr_hdg.setText(f"{heading:.2f} deg")
        
        # Call JS function
        js = f"updateLocationAndHeading({lat}, {lng}, {heading});"
        self.web_view.page().runJavaScript(js)
        
        # update inputs for ease of use
        if not self.center_lat_input.text():
            self.center_lat_input.setText(f"{lat:.6f}")
        if not self.center_lng_input.text():
            self.center_lng_input.setText(f"{lng:.6f}")

    def toggle_simulator(self):
        if self.sim_timer.isActive():
            self.sim_timer.stop()
        else:
            lat = self._get_float_val(self.center_lat_input, 40.7128)
            lng = self._get_float_val(self.center_lng_input, -74.0060)
            self.sim_lat = lat if lat is not None else 40.7128 # default NY if unset
            self.sim_lng = lng if lng is not None else -74.0060
            self.sim_heading = 0
            self.sim_timer.start(500) # 2 Hz

    def simulate_movement(self):
        # move a bit north east
        self.sim_lat += 0.0001
        self.sim_lng += 0.0001
        self.sim_heading = (self.sim_heading + 5) % 360
        self.update_telemetry(self.sim_lat, self.sim_lng, self.sim_heading)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'left_panel'):
            if self.width() < 700:
                self.left_panel.hide()
            else:
                self.left_panel.show()

    def closeEvent(self, event):
        self.udp_thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Enable WebEngine logging for debugging
    # os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-logging --v=1"
    
    window = Dashboard()
    window.show()
    sys.exit(app.exec())
