import json
import requests
from urllib.parse import urlparse
from pkg.plugin.models import *
from pkg.plugin.host import EventContext, PluginHost
import re
from mirai import Image, Plain

@register(name="Md2QQImage_Improved", description="优化 bot 发送的消息，将图片链接转换为实际图片，并且添加防盗链检测及格式检测功能", version="1.2", author="BiFangKNT")
class BotMessageOptimizerPlugin(Plugin):

    def __init__(self, plugin_host: PluginHost):
        super().__init__(plugin_host)
        # 匹配图片 URL 的正则表达式，支持 Markdown 和普通 URL
        self.url_pattern = re.compile(r'!\[.*?\]\((https?://\S+)\)|https?://\S+')
        # 尝试加载防盗链配置文件
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {}

    @on(NormalMessageResponded)
    def optimize_message(self, event: EventContext, **kwargs):
        original_message = kwargs['response_text']
        # 尝试处理消息中的图片链接，并返回处理后的消息
        optimized_message = self.convert_message(original_message)

        # 如果有修改，则将处理后的消息返回
        if optimized_message:
            event.add_return('reply', optimized_message)

    def convert_message(self, message):
        parts = []  # 存储消息的各部分
        last_end = 0  # 上次匹配结束的位置

        for match in self.url_pattern.finditer(message):
            start, end = match.span()
            # 添加匹配到 URL 前的文本部分
            if start > last_end:
                parts.append(Plain(message[last_end:start]))

            # 提取 URL（无论是 Markdown 还是普通 URL）
            image_url = match.group(1) if match.group(1) else match.group(0)

            # 检查 URL 是否在配置文件中
            domain = self.get_domain(image_url)
            if domain in self.config:
                # 如果检测到防盗链机制，提示用户使用指定格式，并跳过图片处理
                site_name = next(key for key, val in self.config.items() if val['domain'] == domain)
                parts.append(Plain(f"检测到网站有防盗链机制，请使用“{site_name}：id”的格式获取图片\n"))
                last_end = end  # 跳过该图片的处理
                continue

            # 没有防盗链限制，则执行图片检测
            if self.is_image_url(image_url):
                parts.append(Image(url=image_url))
            else:
                # 如果图片检测失败，保留原始文本
                parts.append(Plain(match.group(0)))

            last_end = end

        # 添加最后一段未处理的文本
        if last_end < len(message):
            parts.append(Plain(message[last_end:]))

        # 返回拼接后的消息，如果没有修改则返回原消息
        return parts if parts else message

    def get_domain(self, url):
        """提取 URL 的一级域名。"""
        parsed_url = urlparse(url)
        return parsed_url.netloc

    def is_image_url(self, url):
        """尝试检测 URL 是否为图片链接，如果返回 403 或 405，改用 GET 请求。"""
        try:
            # 首先使用 HEAD 请求
            response = requests.head(url, timeout=5)
            if response.status_code in [405, 403]:  # 如果返回 405 或 403，改用 GET 请求
                response = requests.get(url, timeout=5)
            
            content_type = response.headers.get('Content-Type', '').lower()
            return content_type.startswith('image/')
        except requests.RequestException:
            return False  # 如果请求失败，则认为不是图片链接

    def __del__(self):
        pass  # 插件销毁时的清理操作
