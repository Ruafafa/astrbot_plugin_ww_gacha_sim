"""
渲染器模块
负责实现抽卡结果的可视化渲染
"""
import os
import logging
from PIL import Image, ImageDraw, ImageFont
from typing import List
from ..item_data.item_manager import Item
from .ui_resources_manager import UIResourceManager

# 配置日志
logger = logging.getLogger(__name__)



class GachaRenderer:
    """抽卡结果渲染器"""
    
    def __init__(self, ui_resource_manager: UIResourceManager = UIResourceManager()):
        self.ui_resource_manager = ui_resource_manager 
        # 确保字体目录存在
        self.font_path = self._get_font_path()
        # 渲染参数
        self.card_width = 430
        self.card_height = 560
        # 独立的横向和纵向间距属性
        self.h_gap = -50  # 水平间距 (列与列之间的间距)
        self.v_gap = 30  # 垂直间距 (行与行之间的间距)
        
    
    def _get_font_path(self) -> str:
        """获取字体路径"""
        # 尝试多个可能的字体路径
        font_paths = [
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/msyh.ttc",   # 微软雅黑
            "C:/Windows/Fonts/simsun.ttc", # 宋体
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                return path
        
        # 如果找不到中文字体，返回None（后续会使用默认字体）
        return None
    
    def _get_font(self, size: int):
        """获取字体对象"""
        try:
            if self.font_path:
                return ImageFont.truetype(self.font_path, size)
            else:
                # 如果没有中文字体，使用默认字体
                return ImageFont.load_default()
        except:
            return ImageFont.load_default()
    
    def _create_single_card(self, item: Item) -> Image.Image:
        """
        优化后的抽卡卡片渲染：基于底部基准的布局方案
        """
        # --- 1. 基础参数定义 ---
        W, H = self.card_width, self.card_height
        rarity = item.rarity
        item_name = item.name
        
        # 定义布局配置 (基于底部的定位，使用距离底部的高度)
        LAYOUT = {
            "portrait": {"width_ratio": 0.77, "bottom_offset_ratio": 0.08},  # 立绘占宽100%，底部距离为卡片高度的40%
            "info":     {"width_ratio": 1.0,  "bottom_offset_ratio": -0.05},  # 信息层占满宽，底部距离为卡片高度的15%
            "border":   {"scale": 1.2},                                      # 边框稍微溢出，使用更大的缩放值
            "icon":     {"size_ratio": 0.11, "left_offset_ratio": 0.10, "bottom_offset_ratio": 0.07}  # 图标大小为卡片高度的15%，左侧偏移5%，底部偏移10%
        }

        # 创建透明底板画布，直接使用原始卡片尺寸，不预留额外空间
        card = Image.new('RGBA', (W, H), (0, 0, 0, 0))

        # --- 辅助函数：按比例缩放并返回位置 ---
        def get_scaled_layer(img, target_w, target_h, cover=False):
            img = img.convert('RGBA')
            iw, ih = img.size
            # 计算缩放比例 (fit or cover)
            ratio = max(target_w/iw, target_h/ih) if cover else min(target_w/iw, target_h/ih)
            new_size = (int(iw * ratio), int(ih * ratio))
            return img.resize(new_size, Image.Resampling.LANCZOS)

        # --- 图层 2: 背景层 (Background) ---
        bg_sprite_name = f"bg_star_{rarity}.png"
        bg_img = self.ui_resource_manager._extract_sprite_from_atlas(bg_sprite_name, remove_transparent_border=False)
        if bg_img:
            # 背景通常铺满原始卡片区域
            bg_layer = get_scaled_layer(bg_img, W, H, cover=True)
            # 直接放置在画布上，不需要偏移
            card.paste(bg_layer, (0, 0), bg_layer)
        else:
            # 后备方案
            bg_path = self.ui_resource_manager.get_background_for_quality(rarity)
            bg_layer = Image.open(bg_path).convert('RGBA').resize((W, H))
            # 直接放置在画布上，不需要偏移
            card.paste(bg_layer, (0, 0))

        # --- 图层 3: 立绘层 (Portrait) ---
        try:
            portrait_path = self.ui_resource_manager.get_resource_path_from_item_name(item_name)
            if os.path.exists(portrait_path):
                portrait_raw = Image.open(portrait_path)
                # 按比例计算立绘目标尺寸
                p_target_w = W * LAYOUT["portrait"]["width_ratio"]
                p_target_h = H  # 给立绘预留的最大高度比例
                portrait_layer = get_scaled_layer(portrait_raw, p_target_w, p_target_h)
                
                # 从底部开始计算位置，直接使用原始卡片尺寸
                px = (W - portrait_layer.width) // 2
                # 计算从画布底部到元素底部的距离
                element_bottom_y = H - int(H * LAYOUT["portrait"]["bottom_offset_ratio"])  # 元素底部的Y坐标
                py = element_bottom_y - portrait_layer.height  # 元素顶部的Y坐标
                card.paste(portrait_layer, (px, py), portrait_layer)
        except Exception as e:
            logger.warning(f"立绘加载失败: {e}")

        # --- 图层 3.5: 半调图案层 (Halftone Pattern Layer) --- 信息层之上，图标层之下
        try:
            # 加载半调图案
            bandiao_img = self.ui_resource_manager.get_halftone_pattern()
            if bandiao_img:
                # 调整半调图案大小以适应卡片
                scaled_bandiao = bandiao_img.resize((W, H), Image.Resampling.LANCZOS)
                
                # 设置透明度为61.8%
                alpha = scaled_bandiao.split()[3]  # 获取alpha通道
                alpha = alpha.point(lambda x: int(x * 0.618))  # 设置透明度为61.8%
                scaled_bandiao.putalpha(alpha)  # 应用新的alpha通道
                
                # 将半调图案向下移动，偏移量为卡片高度的10%
                offset_y = int(H * 0.049)  # 向下移动卡片高度的10%
                # 将半调图案绘制到卡片上，向下偏移一定距离
                card.paste(scaled_bandiao, (0, offset_y), scaled_bandiao)
            else:
                logger.warning("警告: 半调图案不存在，无法绘制半调图案")
        except Exception as e:
            logger.warning(f"半调图案加载失败: {e}")

        # --- 图层 4: 信息展示层 (Info/Show Layer) ---
        show_sprite_name = f"show_star_{rarity}.png"
        show_img = self.ui_resource_manager._extract_sprite_from_atlas(show_sprite_name, remove_transparent_border=False)  # 不再移除透明边界以保持一致的定位基准
        if show_img:
            info_w = W * LAYOUT["info"]["width_ratio"] + 4
            # 使用固定的高度比例来确保所有星级的信息展示层位置一致
            target_info_height = 2 * H
            info_layer = get_scaled_layer(show_img, info_w, int(target_info_height))
            
            ix = (W - info_layer.width) // 2
            # 从底部开始计算信息层位置，使用配置中的bottom_offset_ratio
            element_bottom_y = H - int(H * LAYOUT["info"]["bottom_offset_ratio"])  # 元素底部的Y坐标，基于配置的底部偏移比例
            iy = element_bottom_y - info_layer.height  # 元素顶部的Y坐标
            card.paste(info_layer, (ix, iy), info_layer)

        # --- 图层 5: 图标层 (Icon Layer) --- 信息层上方，位于左侧开头
        at = item.affiliated_type.title()

        try:
            # 尝试加载图标
            icon_path_str = self.ui_resource_manager.get_icon_path(at)
            if icon_path_str:
                icon_img = Image.open(icon_path_str).convert('RGBA')
            else:
                # 图标不存在，跳过绘制
                logger.warning(f"警告: 图标 {at} 不存在，无法绘制图标")
                icon_img = None
            
            if icon_img:
                # 计算图标大小和位置
                icon_size = int(H * LAYOUT["icon"]["size_ratio"])
                scaled_icon = icon_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                
                # 调整图标亮度，将亮度调暗
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Brightness(scaled_icon)
                dimmed_icon = enhancer.enhance(0.9)  # 将亮度调整为原始的70%
                
                # 计算位置:
                icon_x = int(W * LAYOUT["icon"]["left_offset_ratio"])
                icon_bottom_y = H - int(H * LAYOUT["icon"]["bottom_offset_ratio"])
                icon_y = icon_bottom_y - dimmed_icon.height
                
                # 绘制图标到卡片上
                card.paste(dimmed_icon, (icon_x, icon_y), dimmed_icon)
        except Exception as e:
            logger.warning(f"图标加载失败: {e}")

        # 移除文字渲染层
        return card

    
    def render_single_pull(self, item: Item) -> Image.Image:
        """渲染单次抽卡结果"""
        card = self._create_single_card(item)
        
        # --- 添加警告文字 --- 模拟抽卡仅供娱乐，素材版权属于库洛
        draw = ImageDraw.Draw(card)
        warning_text = "模拟抽卡仅供娱乐，素材版权属于库洛"
        
        # 获取字体，使用合适的大小
        font = self._get_font(12)  # 单个卡片使用较小的字体
        
        # 计算文字大小和位置（使用textbbox替代textsize）
        bbox = draw.textbbox((0, 0), warning_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        image_width, image_height = card.size
        text_x = (image_width - text_width) // 2
        text_y = image_height - text_height - 10  # 距离底部10像素
        
        # 绘制文字，使用半透明白色
        draw.text((text_x, text_y), warning_text, font=font, fill=(255, 255, 255, 200))
        
        # --- 使用T_LuckdrawBg.png作为单抽背景，进行精确裁剪优化 --- 
        bg_path_str = self.ui_resource_manager.get_background_path()
        if bg_path_str:
            # 加载背景图片
            bg_image = Image.open(bg_path_str).convert('RGBA')
            bg_width, bg_height = bg_image.size
            
            # --- 精确裁剪背景 --- 
            # 计算裁剪区域：从背景中心截取1000x800的区域，比例协调且视觉效果好
            crop_width = 1000
            crop_height = 800
            
            # 计算裁剪起始坐标（从中心开始裁剪）
            crop_left = (bg_width - crop_width) // 2
            crop_top = (bg_height - crop_height) // 2
            crop_right = crop_left + crop_width
            crop_bottom = crop_top + crop_height
            
            # 执行裁剪
            cropped_bg = bg_image.crop((crop_left, crop_top, crop_right, crop_bottom))
            
            # 创建最终图像，使用裁剪后的背景作为基础
            full_image = cropped_bg.copy()
            
            # 确保full_image是RGBA模式
            if full_image.mode != 'RGBA':
                full_image = full_image.convert('RGBA')
            
            # 计算卡片位置，使其在裁剪后的背景上居中
            card_x = (crop_width - card.width) // 2
            card_y = (crop_height - card.height) // 2
            
            # 将卡片粘贴到裁剪后的背景上
            full_image.paste(card, (card_x, card_y), card)
            
            return full_image
        else:
            # 如果背景图片不存在，使用原来的单卡片渲染
            return card
    
    
    def render_ten_pulls(self, results: List[Item]) -> Image.Image:
        """渲染十连抽卡结果"""  
        # 按星级和类型排序：星级高的在前，星级相同的角色在前
        def sort_key(item):
            # 星级高的在前（降序），角色优先于武器（角色=0，武器=1）
            # 将稀有度转换为数值进行比较
            rarity_value = {
                '5star': 5,
                '4star': 4,
                '3star': 3
            }.get(item.rarity, 0)
            return (-rarity_value, 0 if item.type == 'character' else 1)

        # 排序结果
        sorted_results = sorted(results, key=sort_key)
        
        # 计算布局
        cards_per_row = 5
        rows = (len(sorted_results) + cards_per_row - 1) // cards_per_row
        
        # 计算整体图像大小
        total_width = cards_per_row * self.card_width + (cards_per_row + 1) * self.h_gap
        total_height = rows * self.card_height + (rows + 1) * self.v_gap
        
        # 尝试加载背景图片
        bg_path_str = self.ui_resource_manager.get_background_path()
        if bg_path_str:
            # 加载背景图片
            bg_image = Image.open(bg_path_str).convert('RGBA')
            bg_width, bg_height = bg_image.size
            
            # 使用背景图片作为基础图像，保持原始尺寸
            full_image = bg_image.copy()
            
            # 计算卡片布局的起始位置，使其在背景上居中
            cards_total_width = cards_per_row * self.card_width + (cards_per_row - 1) * self.h_gap
            cards_total_height = rows * self.card_height + (rows - 1) * self.v_gap
            
            start_x = (bg_width - cards_total_width) // 2
            start_y = (bg_height - cards_total_height) // 2
        else:
            # 如果背景图片不存在，使用原来的深灰色背景
            full_image = Image.new('RGBA', (total_width, total_height), (50, 50, 50, 255))
            start_x = self.h_gap
            start_y = self.v_gap
        
        # 确保full_image是RGBA模式以正确处理透明度
        if full_image.mode != 'RGBA':
            full_image = full_image.convert('RGBA')
        
        # 渲染每张卡片
        for idx, item in enumerate(sorted_results):
            card = self._create_single_card(item)
            
            # 计算位置
            row = idx // cards_per_row
            col = idx % cards_per_row
            
            x = start_x + col * (self.card_width + self.h_gap)
            y = start_y + row * (self.card_height + self.v_gap)
            
            # 使用透明度混合粘贴卡片，确保透明通道信息完整保留
            if card.mode == 'RGBA':
                full_image.paste(card, (x, y), card)
            else:
                full_image.paste(card, (x, y))
        
        # --- 添加警告文字 --- 模拟抽卡仅供娱乐，素材版权属于库洛
        draw = ImageDraw.Draw(full_image)
        warning_text = "模拟抽卡仅供娱乐，素材版权属于库洛"
        
        # 获取字体，使用合适的大小
        font = self._get_font(24)
        
        # 计算文字大小和位置（使用textbbox替代textsize）
        bbox = draw.textbbox((0, 0), warning_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        image_width, image_height = full_image.size
        text_x = (image_width - text_width) // 2
        text_y = image_height - text_height - 50  # 距离底部20像素
        
        # 绘制文字，使用半透明白色
        draw.text((text_x, text_y), warning_text, font=font, fill=(255, 255, 255, 200))

        return full_image