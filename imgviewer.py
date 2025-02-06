#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QWheelEvent
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QScrollArea,
    QVBoxLayout,
    QLabel,
    QFileDialog,
    QMessageBox,
    QInputDialog,
)


class ImageViewer(QMainWindow):
    def __init__(self, folder=None):
        super().__init__()

        self.setWindowTitle("无缝滚动图片浏览器")
        self.resize(800, 600)
        self.showMaximized()

        # 初始化数据
        self.image_files = []       # 所有图片文件路径列表
        self.current_index = 0      # 当前加载的最上面一张图片在 image_files 中的索引
        self.max_loaded_images = 5  # 同时保留在界面上的最大图片数量
        self.loaded_images = []     # 已加载的图片对应的 QLabel 列表

        # 设置滚动区域及其内部容器（采用垂直布局）
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.setCentralWidget(self.scroll_area)

        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setSpacing(0)  # 图片之间无间隙
        self.scroll_area.setWidget(self.container)

        # 获取图片文件夹路径
        if folder is None:
            folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹", os.getcwd())
            if not folder:
                QMessageBox.critical(self, "错误", "未选择文件夹，程序退出。")
                sys.exit(1)
        self.folder = folder

        # 加载图片列表并预加载初始图片
        self.load_image_list()
        self.preload_images()

    def load_image_list(self):
        """扫描文件夹中的图片文件，并按照文件名排序"""
        valid_ext = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
        self.image_files = [
            os.path.join(self.folder, f)
            for f in os.listdir(self.folder)
            if os.path.splitext(f)[1].lower() in valid_ext
        ]
        self.image_files.sort()
        if not self.image_files:
            QMessageBox.critical(self, "错误", f"在文件夹 {self.folder} 中没有找到图片文件。")
            sys.exit(1)

    def preload_images(self):
        """预加载从当前索引开始的若干张图片"""
        for i in range(self.max_loaded_images):
            idx = self.current_index + i
            if idx < len(self.image_files):
                self.add_image(idx, append=True)

    def add_image(self, idx, append=True):
        """
        加载指定索引的图片，并添加到布局中。
        :param idx: 图片在 self.image_files 中的索引
        :param append: True 表示添加到布局底部，
                    False 表示插入到布局顶部（并相应调整滚动条以保持连续）。
        """
        # 避免重复加载同一图片
        if idx in [lbl.property("index") for lbl in self.loaded_images]:
            return

        image_path = self.image_files[idx]
        orig_pixmap = QPixmap(image_path)
        if orig_pixmap.isNull():
            return

        # 获取当前滚动区域宽度；若为 0，则使用窗口宽度作为备选
        viewport_width = self.scroll_area.viewport().width()
        if viewport_width <= 0:
            viewport_width = self.width()
        scale_factor = viewport_width / orig_pixmap.width()
        new_width = viewport_width
        new_height = int(orig_pixmap.height() * scale_factor)
        scaled_pixmap = orig_pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        label = QLabel()
        label.setPixmap(scaled_pixmap)
        label.setProperty("index", idx)             # 记录图片的索引
        label.setProperty("pixmap_orig", orig_pixmap) # 保存原始图片，用于重缩放

        scroll_bar = self.scroll_area.verticalScrollBar()

        if append:
            # Check if we are at (or near) the bottom.
            was_at_bottom = (scroll_bar.value() >= scroll_bar.maximum() - 50)
            # Record the current scroll value if we are at bottom.
            if was_at_bottom:
                old_scroll_value = scroll_bar.value()
            self.layout.addWidget(label)
            self.loaded_images.append(label)
            # Clean up extra images from the top.
            removed_total = self.cleanup_images("top")
            # If we were at the bottom, adjust the scroll bar value.
            if was_at_bottom:
                # Removal from the top shifts the content upward by removed_total.
                # To keep the same visual content, subtract that value from the old scroll value.
                scroll_bar.setValue(old_scroll_value - removed_total)
        else:
            # For inserting at the top (scrolling up), the existing logic adjusts the scroll bar.
            # 记录当前滚动条位置
            old_value = scroll_bar.value()
            self.layout.insertWidget(0, label)
            self.loaded_images.insert(0, label)
            # 调整滚动条位置以保持视觉连续
            new_height = label.sizeHint().height()
            scroll_bar.setValue(old_value + new_height)
            # 清理多余图片（这里移除底部图片）
            self.cleanup_images("bottom")




    def cleanup_images(self, remove_direction):
        """
        清理超出范围的图片，确保最多保留 max_loaded_images 张。
        当从顶部移除图片时，返回移除的总高度，以便调整滚动条。
        :param remove_direction: 'top' 表示从列表顶部移除，
                                'bottom' 表示从列表底部移除。
        :return: total_removed_height (int)
        """
        total_removed = 0
        while len(self.loaded_images) > self.max_loaded_images:
            if remove_direction == "top":
                removed = self.loaded_images.pop(0)
            elif remove_direction == "bottom":
                removed = self.loaded_images.pop(-1)
            else:
                removed = self.loaded_images.pop(0)
            # Use sizeHint() as a good approximation of the widget’s height.
            removed_height = removed.sizeHint().height()
            total_removed += removed_height
            self.layout.removeWidget(removed)
            removed.deleteLater()
        if self.loaded_images:
            self.current_index = self.loaded_images[0].property("index")
        else:
            self.current_index = 0
        return total_removed



    def wheelEvent(self, event: QWheelEvent):
        """重载鼠标滚轮事件，延迟检查加载新图片"""
        super().wheelEvent(event)
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self.check_load_images)

    def check_load_images(self):
        """
        检查滚动条的位置：
        - 如果接近底部，则加载下一张图片（追加到底部）；
        - 如果接近顶部，则加载上一张图片（插入到布局顶部）。
        每次只加载一张，避免循环卡死
        """
        scroll_bar = self.scroll_area.verticalScrollBar()
        value = scroll_bar.value()
        maximum = scroll_bar.maximum()

        # 检查底部
        if value >= maximum - 50 and maximum > 0:
            if self.loaded_images:
                next_idx = self.loaded_images[-1].property("index") + 1
                if next_idx < len(self.image_files):
                    self.add_image(next_idx, append=True)
            elif self.image_files:
                self.add_image(0, append=True)

        # 检查顶部
        elif value <= 50:
            if self.loaded_images:
                prev_idx = self.loaded_images[0].property("index") - 1
                if prev_idx >= 0:
                    self.add_image(prev_idx, append=False)
            elif self.image_files:
                last_idx = len(self.image_files) - 1
                self.add_image(last_idx, append=False)

    def resizeEvent(self, event):
        """
        重载窗口尺寸变化事件，重新计算所有已加载图片的缩放比例，
        使其根据当前 viewport 宽度自动缩放。
        """
        if not hasattr(self, "scroll_area"):
            return super().resizeEvent(event)
        viewport_width = self.scroll_area.viewport().width()
        if viewport_width <= 0:
            viewport_width = self.width()
        for label in self.loaded_images:
            orig_pixmap = label.property("pixmap_orig")
            if not isinstance(orig_pixmap, QPixmap) or orig_pixmap.isNull():
                continue
            scale_factor = viewport_width / orig_pixmap.width()
            new_width = viewport_width
            new_height = int(orig_pixmap.height() * scale_factor)
            scaled_pixmap = orig_pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(scaled_pixmap)
            label.resize(scaled_pixmap.size())
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        """
        重载键盘按键事件：
        - 按下 'g' 键时弹出对话框，输入想要跳转的页码。
        - 按下 'o' 键时弹出文件夹选择对话框，重新加载其他文件夹中的图片。
        - 按下 'F' 键时切换全屏模式。
        """
        if event.key() == Qt.Key_G:
            page, ok = QInputDialog.getInt(
                self,
                "跳转页面",
                "请输入跳转页码（1-{}）：".format(len(self.image_files)),
                value=self.current_index + 1,
                min=1,
                max=len(self.image_files),
            )
            if ok:
                self.jump_to_page(page)
            return
        elif event.key() == Qt.Key_O:
            self.reload_folder()
            return
        elif event.key() == Qt.Key_F:
            # Toggle fullscreen mode
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return

        super().keyPressEvent(event)


    def jump_to_page(self, page):
        """
        执行页面跳转：
        清空当前加载的图片列表，并从指定页码处重新加载图片。
        """
        target_index = page - 1
        if target_index < 0 or target_index >= len(self.image_files):
            QMessageBox.warning(self, "跳转失败", "输入的页码无效！")
            return

        # 清空当前已加载的图片
        for label in self.loaded_images:
            self.layout.removeWidget(label)
            label.deleteLater()
        self.loaded_images.clear()

        # 更新当前索引，并重新预加载图片
        self.current_index = target_index
        self.preload_images()

        # 将滚动条置顶
        self.scroll_area.verticalScrollBar().setValue(0)

    def reload_folder(self):
        """重新加载文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择新的图片文件夹", os.getcwd())
        if not folder:
            return

        self.folder = folder

        # 清空当前已加载的图片
        for label in self.loaded_images:
            self.layout.removeWidget(label)
            label.deleteLater()
        self.loaded_images.clear()

        # 重新加载图片列表和预加载图片
        self.load_image_list()
        self.current_index = 0
        self.preload_images()
        self.scroll_area.verticalScrollBar().setValue(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec_())
