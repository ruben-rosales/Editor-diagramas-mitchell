import sys
import os
import json
import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
                             QFileDialog, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, 
                             QFrame, QLabel, QListWidget, QListWidgetItem, QAbstractItemView, 
                             QMessageBox, QInputDialog, QCheckBox)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath, QPen, QColor, QKeySequence, QShortcut, QIcon, QFont
from PyQt6.QtCore import Qt, QSize, QPointF, QRectF

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
        self.texts_data = [] # NUEVO: Guardar textos
        
        self.drawing_color = QColor(100, 200, 255, 120) 
        
        # Paneo con botón central
        self.middle_panning = False
        self.last_pan_pos = None

        self.set_mode_hand()

    def set_mode_hand(self):
        self.finish_stroke()
        self.mode = "hand"
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def set_mode_draw(self):
        self.finish_stroke()
        self.mode = "draw"
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def set_mode_eraser(self):
        self.finish_stroke()
        self.mode = "eraser"
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def set_mode_text(self):
        self.finish_stroke()
        self.mode = "text"
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def set_drawing_color(self, r, g, b):
        self.finish_stroke()
        self.drawing_color = QColor(r, g, b, 120)

    def finish_stroke(self):
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

    def erase_item_at(self, pos):
        item = self.itemAt(pos)
        if item:
            self.scene.removeItem(item)
            # Limpiar de las listas de guardado
            self.strokes_data = [s for s in self.strokes_data if s["item"] != item]
            self.texts_data = [t for t in self.texts_data if t["item"] != item]

    def mousePressEvent(self, event):
        # NUEVO: Paneo con clic central en cualquier modo
        if event.button() == Qt.MouseButton.MiddleButton:
            self.middle_panning = True
            self.last_pan_pos = event.pos()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        scene_pos = self.mapToScene(event.pos())

        if self.mode == "draw":
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
                self.finish_stroke()
                
        elif self.mode == "eraser" and event.button() == Qt.MouseButton.LeftButton:
            self.erase_item_at(event.pos())
            
        elif self.mode == "text" and event.button() == Qt.MouseButton.LeftButton:
            text, ok = QInputDialog.getText(self, "Anotación", "Escribe tu nota:")
            if ok and text.strip():
                # Color sólido para el texto (sin transparencia 120)
                solid_color = QColor(self.drawing_color.red(), self.drawing_color.green(), self.drawing_color.blue())
                text_item = self.scene.addText(text)
                text_item.setDefaultTextColor(solid_color)
                font = QFont("Arial", 40, QFont.Weight.Bold)
                text_item.setFont(font)
                text_item.setPos(scene_pos)
                
                self.texts_data.append({
                    "item": text_item,
                    "color": solid_color.getRgb(),
                    "text": text,
                    "pos": (scene_pos.x(), scene_pos.y())
                })
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # NUEVO: Paneo con clic central
        if self.middle_panning and self.last_pan_pos:
            delta = self.last_pan_pos - event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + delta.y())
            self.last_pan_pos = event.pos()
            return

        if self.mode == "draw" and self.poly_points and self.active_path_item:
            scene_pos = self.mapToScene(event.pos())
            temp_path = QPainterPath(self.current_path)
            temp_path.lineTo(scene_pos)
            self.active_path_item.setPath(temp_path)
            
        elif self.mode == "eraser" and event.buttons() & Qt.MouseButton.LeftButton:
            self.erase_item_at(event.pos())
            
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.middle_panning = False
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            return
        super().mouseReleaseEvent(event)

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

    def render_pdf_list(self, file_paths, crop=False):
        self.scene.clear()
        self.strokes_data.clear()
        self.texts_data.clear()
        self.poly_points = []
        self.active_path_item = None
        
        current_x = 0
        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue
            doc = fitz.open(file_path)
            for page in doc:
                mat = fitz.Matrix(4, 4)
                
                # NUEVO: Sistema de recorte de márgenes
                if crop:
                    rect = page.rect
                    margin_x = rect.width * 0.04  # 4% recorte horizontal
                    margin_y = rect.height * 0.04 # 4% recorte vertical
                    clip_rect = fitz.Rect(rect.x0 + margin_x, rect.y0 + margin_y, 
                                          rect.x1 - margin_x, rect.y1 - margin_y)
                    pix = page.get_pixmap(matrix=mat, clip=clip_rect)
                else:
                    pix = page.get_pixmap(matrix=mat)
                    
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                qpixmap = QPixmap.fromImage(img)
                
                item = self.scene.addPixmap(qpixmap)
                item.setPos(current_x, 0)
                current_x += qpixmap.width() 

    def load_project_data(self, strokes, texts):
        self.strokes_data.clear()
        self.texts_data.clear()
        
        # Cargar trazos
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
            self.strokes_data.append({"item": item, "color": color_data, "points": points})

        # Cargar Textos
        for t_data in texts:
            solid_color = QColor(*t_data["color"])
            text_item = self.scene.addText(t_data["text"])
            text_item.setDefaultTextColor(solid_color)
            font = QFont("Arial", 40, QFont.Weight.Bold)
            text_item.setFont(font)
            text_item.setPos(t_data["pos"][0], t_data["pos"][1])
            
            self.texts_data.append({
                "item": text_item,
                "color": t_data["color"],
                "text": t_data["text"],
                "pos": t_data["pos"]
            })

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visor de Diagramas Automotrices - Fase 5")
        self.resize(1350, 900)

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
            QCheckBox { font-weight: bold; }
        """)
        menu_layout = QHBoxLayout(menu_frame)
        menu_layout.setContentsMargins(10, 10, 10, 10)

        # Archivos
        self.btn_save_proj = QPushButton("💾 Guardar")
        self.btn_load_proj = QPushButton("📂 Abrir")
        self.btn_export = QPushButton("🖼️ Exportar IMG") # NUEVO: Exportar
        self.btn_export.setStyleSheet("background-color: #fffb8f; border-color: #d4b106;")
        
        self.btn_add = QPushButton("➕ PDFs")
        self.btn_add.setStyleSheet("background-color: #e6f7ff; border-color: #1890ff; color: #0050b3;")
        
        self.btn_toggle_list = QPushButton("👁️ Lista")
        
        self.chk_crop = QCheckBox("✂️ Recortar bordes") # NUEVO: Casilla de recorte
        self.chk_crop.setChecked(False)
        
        self.btn_merge = QPushButton("▶️ Unir")
        self.btn_merge.setStyleSheet("background-color: #f6ffed; border-color: #52c41a; color: #135200;")

        # Herramientas
        self.lbl_tools = QLabel("| Herram:")
        self.btn_hand = QPushButton("✋")
        self.btn_draw = QPushButton("🖍️")
        self.btn_eraser = QPushButton("🧽") # NUEVO: Borrador
        self.btn_text = QPushButton("📝")   # NUEVO: Texto
        
        self.btn_hand.setCheckable(True)
        self.btn_draw.setCheckable(True)
        self.btn_eraser.setCheckable(True)
        self.btn_text.setCheckable(True)
        self.btn_hand.setChecked(True)

        self.btn_color_blue = QPushButton("🟦")
        self.btn_color_yellow = QPushButton("🟨")
        self.btn_color_red = QPushButton("🟥")
        self.btn_color_green = QPushButton("🟩")
        
        self.btn_undo = QPushButton("↩️")
        self.btn_zoom_out = QPushButton("➖")
        self.btn_zoom_in = QPushButton("➕")
        self.btn_center = QPushButton("🎯")

        # Añadir al layout
        menu_layout.addWidget(self.btn_save_proj)
        menu_layout.addWidget(self.btn_load_proj)
        menu_layout.addWidget(self.btn_export)
        menu_layout.addSpacing(10)
        menu_layout.addWidget(self.btn_add)
        menu_layout.addWidget(self.btn_toggle_list)
        menu_layout.addWidget(self.chk_crop)
        menu_layout.addWidget(self.btn_merge)
        menu_layout.addSpacing(10)
        menu_layout.addWidget(self.lbl_tools)
        menu_layout.addWidget(self.btn_hand)
        menu_layout.addWidget(self.btn_draw)
        menu_layout.addWidget(self.btn_eraser)
        menu_layout.addWidget(self.btn_text)
        menu_layout.addWidget(self.btn_color_blue)
        menu_layout.addWidget(self.btn_color_yellow)
        menu_layout.addWidget(self.btn_color_red)
        menu_layout.addWidget(self.btn_color_green)
        menu_layout.addWidget(self.btn_undo)
        menu_layout.addStretch() 
        menu_layout.addWidget(self.btn_zoom_out)
        menu_layout.addWidget(self.btn_zoom_in)
        menu_layout.addWidget(self.btn_center)

        # Lista de miniaturas
        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setViewMode(QListWidget.ViewMode.ListMode)
        self.thumbnail_list.setFlow(QListWidget.Flow.LeftToRight)
        self.thumbnail_list.setWrapping(False)
        self.thumbnail_list.setIconSize(QSize(100, 100))
        self.thumbnail_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.thumbnail_list.setFixedHeight(140)
        self.thumbnail_list.setSpacing(5)
        self.thumbnail_list.setStyleSheet("""
            QListWidget { background-color: #fafafa; border: 1px solid #d9d9d9; border-radius: 5px; padding: 5px; }
            QListWidget::item { background-color: white; border: 1px solid #cccccc; border-radius: 5px; padding: 2px; }
            QListWidget::item:selected { border: 2px solid #1890ff; background-color: #e6f7ff; }
        """)

        self.viewer = DiagramViewer()

        main_layout.addWidget(menu_frame)
        main_layout.addWidget(self.thumbnail_list)
        main_layout.addWidget(self.viewer)

        # Conexiones principales
        self.btn_save_proj.clicked.connect(self.save_project)
        self.btn_load_proj.clicked.connect(self.load_project)
        self.btn_export.clicked.connect(self.export_image)
        
        self.btn_add.clicked.connect(self.add_files)
        self.btn_toggle_list.clicked.connect(self.toggle_thumbnails)
        self.btn_merge.clicked.connect(self.generate_canvas)
        
        self.btn_center.clicked.connect(self.viewer.center_view)
        self.btn_zoom_in.clicked.connect(self.viewer.zoom_in)
        self.btn_zoom_out.clicked.connect(self.viewer.zoom_out)
        
        self.btn_hand.clicked.connect(self.activate_hand)
        self.btn_draw.clicked.connect(self.activate_draw)
        self.btn_eraser.clicked.connect(self.activate_eraser)
        self.btn_text.clicked.connect(self.activate_text)
        
        self.btn_undo.clicked.connect(self.viewer.undo_last_stroke)
        shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        shortcut_undo.activated.connect(self.viewer.undo_last_stroke)
        
        self.btn_color_blue.clicked.connect(lambda: self.viewer.set_drawing_color(100, 200, 255))
        self.btn_color_yellow.clicked.connect(lambda: self.viewer.set_drawing_color(255, 255, 100))
        self.btn_color_red.clicked.connect(lambda: self.viewer.set_drawing_color(255, 100, 100))
        self.btn_color_green.clicked.connect(lambda: self.viewer.set_drawing_color(100, 255, 100))

    def activate_hand(self):
        self.reset_tool_buttons()
        self.btn_hand.setChecked(True)
        self.viewer.set_mode_hand()

    def activate_draw(self):
        self.reset_tool_buttons()
        self.btn_draw.setChecked(True)
        self.viewer.set_mode_draw()
        
    def activate_eraser(self):
        self.reset_tool_buttons()
        self.btn_eraser.setChecked(True)
        self.viewer.set_mode_eraser()
        
    def activate_text(self):
        self.reset_tool_buttons()
        self.btn_text.setChecked(True)
        self.viewer.set_mode_text()
        
    def reset_tool_buttons(self):
        self.btn_hand.setChecked(False)
        self.btn_draw.setChecked(False)
        self.btn_eraser.setChecked(False)
        self.btn_text.setChecked(False)

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
            # Pasar si el recorte está activado
            do_crop = self.chk_crop.isChecked()
            self.viewer.render_pdf_list(ordered_paths, crop=do_crop)
            self.viewer.center_view()
            if not self.thumbnail_list.isHidden():
                self.toggle_thumbnails()

    def save_project(self):
        self.viewer.finish_stroke() 
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar Proyecto", "", "JSON Files (*.json)")
        if not file_path: return
        
        ordered_paths = []
        for i in range(self.thumbnail_list.count()):
            item = self.thumbnail_list.item(i)
            ordered_paths.append(item.data(Qt.ItemDataRole.UserRole))
            
        clean_strokes = [{"color": s["color"], "points": s["points"]} for s in self.viewer.strokes_data]
        clean_texts = [{"color": t["color"], "text": t["text"], "pos": t["pos"]} for t in self.viewer.texts_data]
            
        data = {
            "pdfs": ordered_paths,
            "strokes": clean_strokes,
            "texts": clean_texts,
            "crop_enabled": self.chk_crop.isChecked()
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        QMessageBox.information(self, "Éxito", "Proyecto guardado correctamente.")

    def load_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir Proyecto", "", "JSON Files (*.json)")
        if not file_path: return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.chk_crop.setChecked(data.get("crop_enabled", False))
        self.thumbnail_list.clear()
        self.add_files(data.get("pdfs", []))
        self.generate_canvas()
        self.viewer.load_project_data(data.get("strokes", []), data.get("texts", []))

    # NUEVO: Exportar a PNG
    def export_image(self):
        self.viewer.finish_stroke()
        if not self.viewer.scene.items():
            QMessageBox.warning(self, "Atención", "El lienzo está vacío.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Exportar Imagen", "", "PNG Image (*.png);;JPEG Image (*.jpg)")
        if not file_path: return

        # Obtener el tamaño total de todo lo que hay en escena
        rect = self.viewer.scene.itemsBoundingRect()
        
        # Crear imagen en blanco
        image = QImage(rect.size().toSize(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        
        # Pintar la escena en la imagen
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.viewer.scene.render(painter, target=QRectF(image.rect()), source=rect)
        painter.end()
        
        image.save(file_path)
        QMessageBox.information(self, "Éxito", "Diagrama exportado correctamente.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())