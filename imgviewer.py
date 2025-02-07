#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import cv2
import numpy as np
from PyQt5.QtGui import QImage

import os
import sys
from PyQt5.QtCore import Qt, QSettings, QRect
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

        # Initialize data
        self.image_files = []       # List of all image file paths
        self.current_index = 0      # Index of the top-most loaded image in image_files
        self.max_loaded_images = 5  # Maximum number of images kept in the view at one time
        self.loaded_images = []     # List of QLabel widgets for loaded images

        # Create QSettings to store resume positions. (You can change organization/app names as needed.)
        self.settings = QSettings("MyCompany", "ImageViewer")

        # Set up the scroll area and container widget
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.setCentralWidget(self.scroll_area)

        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setSpacing(0)  # No gap between images
        self.scroll_area.setWidget(self.container)

        # Get image folder path
        if folder is None:
            folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹", os.getcwd())
            if not folder:
                QMessageBox.critical(self, "错误", "未选择文件夹，程序退出。")
                sys.exit(1)
        self.folder = folder

        # If a resume breakpoint exists for this folder, load it.
        # The key used is "resume/<folder path>"
        saved_index = self.settings.value("resume/" + self.folder, None, type=int)
        if saved_index is not None:
            self.current_index = saved_index
        else:
            self.current_index = 0

        # Load the image list and preload initial images.
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
        # Avoid duplicate loading.
        if idx in [lbl.property("index") for lbl in self.loaded_images]:
            return

        image_path = self.image_files[idx]
        orig_pixmap = QPixmap(image_path)
        if orig_pixmap.isNull():
            return

        # Convert to QImage.
        orig_image = orig_pixmap.toImage()
        # Optionally, first crop the outer white border (if you already have a function for that).
        cropped_image = self.crop_white_border(orig_image)
        # Now remove the internal white gap.
        processed_image = remove_internal_white_gap(cropped_image, threshold=240, white_ratio=0.98, min_gap_height=100)
        orig_pixmap = QPixmap.fromImage(processed_image)

        # Scale to fit the viewport.
        viewport_width = self.scroll_area.viewport().width()
        if viewport_width <= 0:
            viewport_width = self.width()
        scale_factor = viewport_width / orig_pixmap.width()
        new_width = viewport_width
        new_height = int(orig_pixmap.height() * scale_factor)
        scaled_pixmap = orig_pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        label = QLabel()
        label.setPixmap(scaled_pixmap)
        label.setProperty("index", idx)
        label.setProperty("pixmap_orig", orig_pixmap)

        scroll_bar = self.scroll_area.verticalScrollBar()
        if append:
            was_at_bottom = (scroll_bar.value() >= scroll_bar.maximum() - 50)
            if was_at_bottom:
                old_scroll_value = scroll_bar.value()
            self.layout.addWidget(label)
            self.loaded_images.append(label)
            removed_total = self.cleanup_images("top")
            if was_at_bottom:
                scroll_bar.setValue(old_scroll_value - removed_total)
        else:
            old_value = scroll_bar.value()
            self.layout.insertWidget(0, label)
            self.loaded_images.insert(0, label)
            new_height = label.sizeHint().height()
            scroll_bar.setValue(old_value + new_height)
            self.cleanup_images("bottom")



    def crop_white_border(self, image, threshold=240):
        """
        根据阈值裁剪掉图像周围的纯白边框（或近白边框）。
        :param image: QImage 对象
        :param threshold: 判定白色的阈值（0~255），默认240
        :return: 裁剪后的 QImage 对象
        """
        width = image.width()
        height = image.height()
        left, top = 0, 0
        right, bottom = width - 1, height - 1

        # 找到顶部边界
        found_top = False
        for y in range(height):
            for x in range(width):
                color = image.pixelColor(x, y)
                if color.red() < threshold or color.green() < threshold or color.blue() < threshold:
                    top = y
                    found_top = True
                    break
            if found_top:
                break

        # 如果整个图像都是白色，则返回原图
        if not found_top:
            return image

        # 找到底部边界
        found_bottom = False
        for y in range(height - 1, -1, -1):
            for x in range(width):
                color = image.pixelColor(x, y)
                if color.red() < threshold or color.green() < threshold or color.blue() < threshold:
                    bottom = y
                    found_bottom = True
                    break
            if found_bottom:
                break

        # 找到左侧边界
        found_left = False
        for x in range(width):
            for y in range(top, bottom + 1):
                color = image.pixelColor(x, y)
                if color.red() < threshold or color.green() < threshold or color.blue() < threshold:
                    left = x
                    found_left = True
                    break
            if found_left:
                break

        # 找到右侧边界
        found_right = False
        for x in range(width - 1, -1, -1):
            for y in range(top, bottom + 1):
                color = image.pixelColor(x, y)
                if color.red() < threshold or color.green() < threshold or color.blue() < threshold:
                    right = x
                    found_right = True
                    break
            if found_right:
                break

        # 定义裁剪区域并返回裁剪后的图像
        rect = QRect(left, top, right - left + 1, bottom - top + 1)
        return image.copy(rect)

    def cleanup_images(self, remove_direction):
        """
        清理超出范围的图片，确保最多保留 max_loaded_images 张。
        当从顶部移除图片时，返回移除的总高度以便调整滚动条。
        :param remove_direction: 'top' 表示从列表顶部移除，
                                'bottom' 表示从列表底部移除。
        :return: total_removed_height (int) when removing from the top,
                0 otherwise.
        """
        total_removed = 0
        while len(self.loaded_images) > self.max_loaded_images:
            if remove_direction == "top":
                removed = self.loaded_images.pop(0)
            elif remove_direction == "bottom":
                removed = self.loaded_images.pop(-1)
            else:
                removed = self.loaded_images.pop(0)
            removed_height = removed.sizeHint().height()
            total_removed += removed_height
            self.layout.removeWidget(removed)
            removed.deleteLater()

        # Update current_index to be that of the topmost loaded image
        if self.loaded_images:
            self.current_index = self.loaded_images[0].property("index")
        else:
            self.current_index = 0

        # Save the current breakpoint (i.e. the top image index) for the current folder.
        self.settings.setValue("resume/" + self.folder, self.current_index)
        
        return total_removed  # Return value useful if cleanup was called after inserting at the top.

    def wheelEvent(self, event: QWheelEvent):
        """重载鼠标滚轮事件，延迟检查加载新图片"""
        super().wheelEvent(event)
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self.check_load_images)

    def check_load_images(self):
        """检查滚动条的位置，根据视口高度动态调整触发阈值"""
        scroll_bar = self.scroll_area.verticalScrollBar()
        value = scroll_bar.value()
        maximum = scroll_bar.maximum()
        viewport_height = self.scroll_area.viewport().height()

        # 动态计算触发阈值（视口高度的1/3）
        threshold = max(50, viewport_height // 3)  # 至少保留50px的触发区域

        # 检查底部（当距离底部小于阈值时加载）
        if maximum > 0 and value >= maximum - threshold:
            if self.loaded_images:
                next_idx = self.loaded_images[-1].property("index") + 1
                if next_idx < len(self.image_files):
                    self.add_image(next_idx, append=True)

        # 检查顶部（当距离顶部小于阈值时加载）
        elif value <= threshold:
            if self.loaded_images:
                prev_idx = self.loaded_images[0].property("index") - 1
                if prev_idx >= 0:
                    self.add_image(prev_idx, append=False)

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
        - 按下 'R' 键时重置断点（resume breakpoint）。
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
            # Toggle fullscreen mode.
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return
        elif event.key() == Qt.Key_R:
            # Reset the saved resume position for this folder.
            self.settings.remove("resume/" + self.folder)
            self.current_index = 0  # Optionally reset the current index.
            QMessageBox.information(self, "断点重置", "断点已重置，下次打开将从头开始。")
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

        # Attempt to load a resume breakpoint for the new folder.
        saved_index = self.settings.value("resume/" + self.folder, None, type=int)
        if saved_index is not None:
            self.current_index = saved_index
        else:
            self.current_index = 0

        # 清空当前已加载的图片
        for label in self.loaded_images:
            self.layout.removeWidget(label)
            label.deleteLater()
        self.loaded_images.clear()

        # 重新加载图片列表和预加载图片
        self.load_image_list()
        self.preload_images()
        self.scroll_area.verticalScrollBar().setValue(0)

def qimage_to_cv(qimage):
    """Convert a QImage into an OpenCV (BGR) image."""
    qimage = qimage.convertToFormat(QImage.Format_RGBA8888)
    width = qimage.width()
    height = qimage.height()
    ptr = qimage.bits()
    ptr.setsize(qimage.byteCount())
    arr = np.array(ptr).reshape(height, width, 4)
    # Convert RGBA to BGR
    return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)

def cv_to_qimage(cv_img):
    """Convert an OpenCV (BGR) image to QImage."""
    height, width, channel = cv_img.shape
    bytesPerLine = 3 * width
    # Convert BGR to RGB
    rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    return QImage(rgb_image.data, width, height, bytesPerLine, QImage.Format_RGB888).copy()

def collapse_white_gaps(qimage, threshold=240, white_ratio=0.98):
    """
    Remove internal white rows and columns.
    
    Parameters:
      - qimage: QImage instance.
      - threshold: Minimum channel value to consider a pixel “white.”
      - white_ratio: If the fraction of white pixels in a row/column is >= white_ratio,
                     that row/column is removed.
                     
    Returns:
      A new QImage with the white rows/columns removed.
    """
    # Convert to OpenCV image.
    cv_img = qimage_to_cv(qimage)
    h, w, _ = cv_img.shape

    # Create a mask: 1 for white-ish pixels, 0 for others.
    # A pixel is white-ish if all its channels are >= threshold.
    white_mask = np.all(cv_img >= threshold, axis=2).astype(np.uint8)

    # For each row, compute the fraction of white pixels.
    white_fraction_rows = white_mask.mean(axis=1)  # shape (h,)
    rows_to_keep = np.where(white_fraction_rows < white_ratio)[0]

    # For each column, compute the fraction of white pixels (using only kept rows).
    if len(rows_to_keep) == 0:
        # If all rows are white, return the original image.
        return qimage
    white_fraction_cols = white_mask[rows_to_keep, :].mean(axis=0)  # shape (w,)
    cols_to_keep = np.where(white_fraction_cols < white_ratio)[0]

    # If no rows or columns are kept, return the original.
    if len(rows_to_keep) == 0 or len(cols_to_keep) == 0:
        return qimage

    # Collapse the image by keeping only the selected rows and columns.
    collapsed_img = cv_img[rows_to_keep[0]:rows_to_keep[-1]+1, cols_to_keep[0]:cols_to_keep[-1]+1]
    return cv_to_qimage(collapsed_img)

def remove_internal_white_gap(qimage, threshold=240, white_ratio=0.98, min_gap_height=5):
    """
    Remove an internal white gap from the image.
    
    This function looks for a contiguous block of rows (that does not touch the top or bottom)
    where almost every pixel is white (or near white). Such rows are dropped, so that the 
    upper and lower content areas are stitched together.
    
    :param qimage: QImage instance.
    :param threshold: Minimum channel value to consider a pixel "white". (0-255, default 240)
    :param white_ratio: If a row's fraction of white pixels is >= this value, it is considered white.
    :param min_gap_height: Only remove a contiguous white block if it has at least this many rows.
    :return: A new QImage with the internal white gap removed.
    """
    # Convert QImage to an OpenCV image (BGR)
    cv_img = qimage_to_cv(qimage)
    h, w, _ = cv_img.shape

    # Create a boolean mask: True if a pixel is white (all channels >= threshold)
    white_mask = np.all(cv_img >= threshold, axis=2)
    # Compute the fraction of white pixels in each row.
    row_white_fraction = np.mean(white_mask, axis=1)  # shape: (h,)
    # Identify rows that are almost entirely white.
    white_rows = row_white_fraction >= white_ratio

    # Determine which rows to keep.
    indices_to_keep = []
    i = 0
    while i < h:
        if white_rows[i]:
            # Find the contiguous block of white rows.
            j = i
            while j < h and white_rows[j]:
                j += 1
            block_height = j - i
            # Remove the block only if it is strictly internal (i > 0 and j < h)
            # and if the block is thick enough.
            if i > 0 and j < h and block_height >= min_gap_height:
                # Skip these rows (i.e. do not add them to indices_to_keep)
                pass
            else:
                # Otherwise, keep these rows.
                indices_to_keep.extend(range(i, j))
            i = j
        else:
            indices_to_keep.append(i)
            i += 1

    # If no rows are kept, return the original image.
    if not indices_to_keep:
        return qimage

    # Create a new image from the selected rows.
    new_cv_img = cv_img[indices_to_keep, :, :]
    return cv_to_qimage(new_cv_img)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec_())
