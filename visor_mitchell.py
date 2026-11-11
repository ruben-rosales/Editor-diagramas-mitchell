import sys
import os
import json
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
                             QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, 
                             QFrame, QLabel, QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath, QPen, QColor, QKeySequence, QShortcut, QIcon
from PyQt6.QtCore import Qt, QSize, QPointF

class DiagramViewer(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setMouseTracking(True)
        
        self.zoom_factor = 1.15
        self.mode = "hand" 
        
        self.poly_points = []
        self.current_path = None
        self.active_path_item = None
        
        self.strokes_data = [] 
        
        self.drawing_color = QColor(100, 200, 255, 120) 
        self.set_mode_hand()

    def set_mode_hand(self):
        self.finish_stroke() # Asegura cualquier trazo a medias
        self.mode = "hand"
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def set_mode_draw(self):
        self.finish_stroke()
        self.mode = "draw"
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def set_drawing_color(self, r, g, b):
        self.finish_stroke()
        self.drawing_color = QColor(r, g, b, 120)

    def finish_stroke(self):
        """ Cierra y guarda permanentemente el trazo actual en la memoria del programa """
        if self.active_path_item and len(self.poly_points) > 0:
            self.strokes_data.append({
                "item": self.active_path_item,
                "color": self.drawing_color.getRgb(),
                "points": self.poly_points.copy()
            })
        self.active_path_item = None
        self.poly_points = []

    def cancel_current_drawing(self):
        if self.active_path_item:
            self.scene.removeItem(self.active_path_item)
            self.active_path_item = None
            self.poly_points = []

    def mousePressEvent(self, event):
        if self.mode == "draw":
            scene_pos = self.mapToScene(event.pos())
            
            if event.button() == Qt.MouseButton.LeftButton:
                if not self.poly_points:
                    self.poly_points.append((scene_pos.x(), scene_pos.y()))
                    self.current_path = QPainterPath()
                    self.current_path.moveTo(scene_pos)
                    
                    pen = QPen(self.drawing_color)
                    pen.setWidth(20)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    
                    self.active_path_item = self.scene.addPath(self.current_path, pen)
                else:
                    self.poly_points.append((scene_pos.x(), scene_pos.y()))
                    self.current_path.lineTo(scene_pos)
                    self.active_path_item.setPath(self.current_path)
            
            elif event.button() == Qt.MouseButton.RightButton:
                # Clic derecho termina el trazo de manera limpia
                self.finish_stroke()
                    
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mode == "draw" and self.poly_points and self.active_path_item:
            scene_pos = self.mapToScene(event.pos())
            temp_path = QPainterPath(self.current_path)
            temp_path.lineTo(scene_pos)
            self.active_path_item.setPath(temp_path)
        else:
            super().mouseMoveEvent(event)

    def undo_last_stroke(self):
        if self.mode == "draw" and self.poly_points:
             self.cancel_current_drawing()
        elif self.strokes_data:
            last_stroke = self.strokes_data.pop()
            self.scene.removeItem(last_stroke["item"])

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self):
        self.scale(self.zoom_factor, self.zoom_factor)

    def zoom_out(self):
        self.scale(1 / self.zoom_factor, 1 / self.zoom_factor)

    def center_view(self):
        if self.scene.items():
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def render_pdf_list(self, file_paths):
        self.scene.clear()
        self.strokes_data.clear()
        self.poly_points = []
        self.active_path_item = None
        
        current_x = 0
        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue
            doc = fitz.open(file_path)
            for page in doc:
                mat = fitz.Matrix(4, 4) 
                pix = page.get_pixmap(matrix=mat)
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                qpixmap = QPixmap.fromImage(img)
                
                item = self.scene.addPixmap(qpixmap)
                item.setPos(current_x, 0)
                current_x += qpixmap.width() 

    def load_strokes(self, strokes):
        self.strokes_data.clear()
        for stroke in strokes:
            color_data = stroke["color"]
            points = stroke["points"]
            if not points: continue
            
            color = QColor(*color_data)
            pen = QPen(color)
            pen.setWidth(20)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            
            path = QPainterPath()
            path.moveTo(QPointF(points[0][0], points[0][1]))
            for pt in points[1:]:
                path.lineTo(QPointF(pt[0], pt[1]))
                
            item = self.scene.addPath(path, pen)
            
            self.strokes_data.append({
                "item": item,
                "color": color_data,
                "points": points
            })


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visor de Diagramas Automotrices - Pro")
        self.resize(1300, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        menu_frame = QFrame()
        menu_frame.setStyleSheet("""
            QFrame { background-color: #f0f0f0; border: 1px solid #cccccc; border-radius: 8px; }
            QPushButton { background-color: #ffffff; border: 1px solid #aaaaaa; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #e0e0e0; }
            QPushButton:checked { background-color: #d0e0ff; border: 1px solid #0055ff; }
            QLabel { font-weight: bold; margin-left: 5px; border: none; }
        """)
        menu_layout = QHBoxLayout(menu_frame)
        menu_layout.setContentsMargins(10, 10, 10, 10)

        self.btn_save_proj = QPushButton("💾 Guardar")
        self.btn_load_proj = QPushButton("📂 Abrir")
        
        self.btn_add = QPushButton("➕ PDFs")
        self.btn_add.setStyleSheet("background-color: #e6f7ff; border-color: #1890ff; color: #0050b3;")
        
        self.btn_toggle_list = QPushButton("👁️ Lista")
        
        self.btn_merge = QPushButton("▶️ Unir")
        self.btn_merge.setStyleSheet("background-color: #f6ffed; border-color: #52c41a; color: #135200;")

        self.lbl_tools = QLabel("| Herram:")
        self.btn_hand = QPushButton("✋")
        self.btn_draw = QPushButton("🖍️")
        self.btn_hand.setCheckable(True)
        self.btn_draw.setCheckable(True)
        self.btn_hand.setChecked(True)

        self.btn_color_blue = QPushButton("🟦")
        self.btn_color_yellow = QPushButton("🟨")
        self.btn_color_red = QPushButton("🟥")
        self.btn_color_green = QPushButton("🟩")
        
        self.btn_undo = QPushButton("↩️")
        
        self.btn_zoom_out = QPushButton("➖")
        self.btn_zoom_in = QPushButton("➕")
        self.btn_center = QPushButton("🎯")

        menu_layout.addWidget(self.btn_save_proj)
        menu_layout.addWidget(self.btn_load_proj)
        menu_layout.addSpacing(10)
        menu_layout.addWidget(self.btn_add)
        menu_layout.addWidget(self.btn_toggle_list)
        menu_layout.addWidget(self.btn_merge)
        menu_layout.addSpacing(10)
        menu_layout.addWidget(self.lbl_tools)
        menu_layout.addWidget(self.btn_hand)
        menu_layout.addWidget(self.btn_draw)
        menu_layout.addWidget(self.btn_color_blue)
        menu_layout.addWidget(self.btn_color_yellow)
        menu_layout.addWidget(self.btn_color_red)
        menu_layout.addWidget(self.btn_color_green)
        menu_layout.addWidget(self.btn_undo)
        menu_layout.addStretch() 
        menu_layout.addWidget(self.btn_zoom_out)
        menu_layout.addWidget(self.btn_zoom_in)
        menu_layout.addWidget(self.btn_center)

        # --- ARREGLO DE LA LISTA DE MINIATURAS ---
        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setViewMode(QListWidget.ViewMode.ListMode) # Modo lista estricto
        self.thumbnail_list.setFlow(QListWidget.Flow.LeftToRight)      # De izquierda a derecha
        self.thumbnail_list.setWrapping(False)                         # Evita que se bajen de renglón
        self.thumbnail_list.setIconSize(QSize(100, 100))
        self.thumbnail_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.thumbnail_list.setFixedHeight(140)                        # Altura reducida
        self.thumbnail_list.setSpacing(5)                              # Espacio reducido
        self.thumbnail_list.setStyleSheet("""
            QListWidget { background-color: #fafafa; border: 1px solid #d9d9d9; border-radius: 5px; padding: 5px; }
            QListWidget::item { background-color: white; border: 1px solid #cccccc; border-radius: 5px; padding: 2px; }
            QListWidget::item:selected { border: 2px solid #1890ff; background-color: #e6f7ff; }
        """)

        self.viewer = DiagramViewer()

        main_layout.addWidget(menu_frame)
        main_layout.addWidget(self.thumbnail_list)
        main_layout.addWidget(self.viewer)

        # Conexiones
        self.btn_save_proj.clicked.connect(self.save_project)
        self.btn_load_proj.clicked.connect(self.load_project)
        
        self.btn_add.clicked.connect(self.add_files)
        self.btn_toggle_list.clicked.connect(self.toggle_thumbnails)
        self.btn_merge.clicked.connect(self.generate_canvas)
        
        self.btn_center.clicked.connect(self.viewer.center_view)
        self.btn_zoom_in.clicked.connect(self.viewer.zoom_in)
        self.btn_zoom_out.clicked.connect(self.viewer.zoom_out)
        
        self.btn_hand.clicked.connect(self.activate_hand)
        self.btn_draw.clicked.connect(self.activate_draw)
        self.btn_undo.clicked.connect(self.viewer.undo_last_stroke)
        
        shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        shortcut_undo.activated.connect(self.viewer.undo_last_stroke)
        
        self.btn_color_blue.clicked.connect(lambda: self.viewer.set_drawing_color(100, 200, 255))
        self.btn_color_yellow.clicked.connect(lambda: self.viewer.set_drawing_color(255, 255, 100))
        self.btn_color_red.clicked.connect(lambda: self.viewer.set_drawing_color(255, 100, 100))
        self.btn_color_green.clicked.connect(lambda: self.viewer.set_drawing_color(100, 255, 100))

    def activate_hand(self):
        self.btn_hand.setChecked(True)
        self.btn_draw.setChecked(False)
        self.viewer.set_mode_hand()

    def activate_draw(self):
        self.btn_draw.setChecked(True)
        self.btn_hand.setChecked(False)
        self.viewer.set_mode_draw()

    def toggle_thumbnails(self):
        if self.thumbnail_list.isHidden():
            self.thumbnail_list.show()
        else:
            self.thumbnail_list.hide()

    def add_files(self, paths=None):
        if not paths:
            paths, _ = QFileDialog.getOpenFileNames(self, "Agregar PDFs", "", "Archivos PDF (*.pdf)")
            
        if paths:
            if self.thumbnail_list.isHidden():
                self.toggle_thumbnails()
                
            for path in paths:
                if not os.path.exists(path): continue
                doc = fitz.open(path)
                page = doc[0] 
                mat = fitz.Matrix(0.2, 0.2)
                pix = page.get_pixmap(matrix=mat)
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                icon = QIcon(QPixmap.fromImage(img))
                
                file_name = os.path.basename(path)
                item = QListWidgetItem(icon, file_name)
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setToolTip(file_name)
                
                self.thumbnail_list.addItem(item)

    def generate_canvas(self):
        ordered_paths = []
        for i in range(self.thumbnail_list.count()):
            item = self.thumbnail_list.item(i)
            ordered_paths.append(item.data(Qt.ItemDataRole.UserRole))
            
        if ordered_paths:
            self.viewer.render_pdf_list(ordered_paths)
            self.viewer.center_view()
            if not self.thumbnail_list.isHidden():
                self.toggle_thumbnails()

    def save_project(self):
        self.viewer.finish_stroke() # <-- AQUÍ ESTÁ EL SEGURO PARA NO PERDER LA LÍNEA
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar Proyecto", "", "JSON Files (*.json)")
        if not file_path: return
        
        ordered_paths = []
        for i in range(self.thumbnail_list.count()):
            item = self.thumbnail_list.item(i)
            ordered_paths.append(item.data(Qt.ItemDataRole.UserRole))
            
        clean_strokes = []
        for stroke in self.viewer.strokes_data:
            clean_strokes.append({
                "color": stroke["color"],
                "points": stroke["points"]
            })
            
        data = {
            "pdfs": ordered_paths,
            "strokes": clean_strokes
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        QMessageBox.information(self, "Éxito", "Proyecto guardado correctamente.")

    def load_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir Proyecto", "", "JSON Files (*.json)")
        if not file_path: return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.thumbnail_list.clear()
        self.add_files(data.get("pdfs", []))
        self.generate_canvas()
        self.viewer.load_strokes(data.get("strokes", []))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())