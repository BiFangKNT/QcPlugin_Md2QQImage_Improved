import json
import requests
from urllib.parse import urlparse
from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
import pkg.platform.types as platform_types
import re
import os


@register(name="Md2QQImage_Improved",
          description="优化 bot 发送的消息，将图片链接转换为实际图片，并且添加防盗链检测及格式检测功能", version="1.3",
          author="BiFangKNT")
class BotMessageOptimizerPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        super().__init__(host)
        # 匹配图片 URL 的正则表达式，支持 Markdown 和普通 URL
        self.config = self.load_config()
        self.url_pattern = re.compile(r'!\[.*?\]\((?P<img_url>https?://[^\s\)]+)\)|\[.*?\]\((?P<link_url>https?://[^\s\)]+)\)|(?P<plain_url>https?://[^\s\)]+)')

    @handler(NormalMessageResponded)
    async def optimize_message(self, ctx: EventContext):

        original_message = ctx.event.response_text
        # 尝试处理消息中的图片链接，并返回处理后的消息
        optimized_message = self.convert_message(original_message)

        # 如果有修改，则将处理后的消息返回
        if optimized_message:
            ctx.add_return('reply', optimized_message)

    def load_config(self):
        """加载配置文件"""
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(plugin_dir, 'config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}  # 默认返回空配置

    def convert_message(self, message):
        parts = []  # 存储消息的各部分
        last_end = 0  # 上次匹配结束的位置
        first_image_processed = False  # 标记是否已处理第一个图片

        for match in self.url_pattern.finditer(message):
            start, end = match.span()
            # 添加匹配到 URL 前的文本部分
            if start > last_end:
                parts.append(platform_types.Plain(message[last_end:start]))

            # 提取 URL（无论是 Markdown 还是普通 URL）
            image_url = match.group(1) if match.group(1) else match.group(0)

            # 只对第一个URL进行图片检测和转换
            if not first_image_processed:
                if self.has_image_suffix(image_url):
                    domain = self.get_domain(image_url)
                    if domain in self.config:
                        site_name = self.config[domain]
                        parts.append(platform_types.Plain(f"检测到 {site_name} 网站有防盗链机制，请安装`QChatGPT_AntiHotlinkImageFetcher`插件后，使用“{site_name}：id”的格式获取图片。\n"))
                        first_image_processed = True
                        last_end = end
                        continue

                if self.is_image_url(image_url):
                    parts.append(platform_types.Image(url=image_url))
                    first_image_processed = True
                    last_end = end
                    continue

            # 对其他URL只进行格式转换
            if match.group('img_url') or match.group('link_url'):
                url = match.group('img_url') or match.group('link_url')
                markdown_prefix = match.group(0)[:match.group(0).index(url)]
                parts.append(platform_types.Plain(f"{markdown_prefix}{url} )"))
            else:
                parts.append(platform_types.Plain(match.group('plain_url')))

            last_end = end

        # 添加最后一段未处理的文本
        if last_end < len(message):
            parts.append(platform_types.Plain(message[last_end:]))

        # 返回拼接后的消息，如果没有修改则返回原消息
        return parts if parts else message

    def get_domain(self, url):
        """提取 URL 的一级域名。"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        # 分割域名部分，去除子域名，只保留主域名部分（如 "i.pximg.net" -> "pximg"）
        domain_parts = domain.split('.')
        if len(domain_parts) > 2:
            return domain_parts[-2]  # 只返回主域名部分 "pximg"
        return domain_parts[0]

    def has_image_suffix(self, url):
        """根据 URL 后缀判断是否为图片链接，常见的图片后缀如 .jpg, .png 等。"""
        image_suffixes = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        return any(url.lower().endswith(suffix) for suffix in image_suffixes)

    def is_image_url(self, url):
        """通过 HTTP 请求检测 URL 是否为图片链接，仅在未检测到防盗链的情况下调用。"""
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
