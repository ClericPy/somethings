#! ../.venv/Scripts/python.exe
import threading

import pystray
from PIL import Image, ImageDraw, ImageFont


# 托盘图标类
class TrayIcon:
    def __init__(self, number=0):
        self.number = number
        self.icon = None
        # 使用更大的字体，并尝试加粗
        try:
            # 尝试加载一个更大的字体，并加粗
            self.font = ImageFont.truetype("", 24)  # 24号字体，加粗
        except IOError:
            # 如果失败，使用默认字体
            self.font = ImageFont.load_default()

    # 创建带数字的图标
    def create_image(self, number=None):
        if number is not None:
            self.number = number
        # 只允许显示0-9
        if self.number < 0:
            self.number = 0
        elif self.number > 9:
            self.number = 9
        # 图标大小
        size = (64, 64)  # 增大图标尺寸
        # 背景颜色
        bgcolor = (0, 128, 255)
        # 创建蓝色背景图像
        image = Image.new("RGB", size, bgcolor)
        draw = ImageDraw.Draw(image)
        # 数字颜色
        textcolor = (255, 255, 255)
        # 尝试更大更粗字体
        try:
            font = ImageFont.truetype("arialbd.ttf", 50)  # 40号字体，加粗
        except IOError:
            font = self.font
        text = str(self.number)
        # 获取文本的边界框
        bbox = draw.textbbox((0, 0), text, font=font)
        textwidth = bbox[2] - bbox[0]
        textheight = bbox[3] - bbox[1]
        # 计算文本位置（居中）
        x = (size[0] - textwidth) / 2
        y = (size[1] - textheight) / 2
        # 先画黑色粗描边，再画白色数字
        for dx in [-2, -1, 0, 1, 2]:
            for dy in [-2, -1, 0, 1, 2]:
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
        draw.text((x, y), text, font=font, fill=textcolor)
        return image

    # 更新图标
    def update_icon(self, number=None):
        if number is not None:
            self.number = number
        if self.icon:
            self.icon.icon = self.create_image()

    # 退出程序
    def exit_program(self):
        if self.icon:
            self.icon.stop()

    # 点击图标时的回调
    def on_click(self, icon, item):
        print("123")

    # 创建托盘图标
    def create_tray_icon(self):
        # 创建初始图标
        image = self.create_image()
        # 创建菜单，添加打印123项
        menu = pystray.Menu(
            pystray.MenuItem("打印123", self.on_click, default=True),
            pystray.MenuItem("退出", self.exit_program),
        )
        # 创建托盘图标，添加点击回调
        self.icon = pystray.Icon("test_icon", image, "托盘图标", menu)
        # self.on_click =
        # 运行托盘图标
        self.icon.run()


# 主程序
if __name__ == "__main__":
    # 创建托盘图标实例
    tray_icon = TrayIcon(number=0)
    tray_icon.create_tray_icon()
    tray_icon.exit_program()
