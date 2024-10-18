import json
import requests
from urllib.parse import urlparse
from pkg.plugin.models import *
from pkg.plugin.host import EventContext, PluginHost
import re
from mirai import Image, Plain
import os


@register(name="Md2QQImage_Improved",
          description="优化 bot 发送的消息，将图片链接转换为实际图片，并且添加防盗链检测及格式检测功能", version="1.2",
          author="BiFangKNT")
class BotMessageOptimizerPlugin(Plugin):

    def __init__(self, plugin_host: PluginHost):
        super().__init__(plugin_host)
        # 匹配图片 URL 的正则表达式，支持 Markdown 和普通 URL
        self.url_pattern = re.compile(r'!\[.*?\]\((https?://\S+)\)|https?://\S+')

        # 输出当前工作目录，帮助确认 config.json 的路径
        debug_info = f"当前工作目录: {os.getcwd()}\n"
        debug_info += f"config.json 文件路径: {os.path.abspath('config.json')}\n"

        # 尝试加载防盗链配置文件
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
                debug_info += f"配置文件加载成功: {self.config}\n"  # 调试信息：配置内容
        except FileNotFoundError:
            self.config = {}
            debug_info += "配置文件未找到\n"  # 如果文件不存在
        except json.JSONDecodeError as e:
            self.config = {}
            debug_info += f"配置文件解析错误: {e}\n"  # JSON解析错误信息
        except Exception as e:
            self.config = {}
            debug_info += f"其他错误: {e}\n"  # 捕获其他异常

        self.debug_info = debug_info  # 存储调试信息供后续使用

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
        debug_info = ""  # 用于存储调试信息

        # 添加调试信息，显示收到的消息
        debug_info += f"原始消息: {message}\n"

        for match in self.url_pattern.finditer(message):
            start, end = match.span()
            # 添加匹配到 URL 前的文本部分
            if start > last_end:
                parts.append(Plain(message[last_end:start]))

            # 提取 URL（无论是 Markdown 还是普通 URL）
            image_url = match.group(1) if match.group(1) else match.group(0)
            debug_info += f"提取的 URL: {image_url}\n"

            # 检查 URL 是否为常见的图片后缀
            if self.has_image_suffix(image_url):
                debug_info += "URL 包含图片后缀\n"
                # 进入防盗链检测
                domain = self.get_domain(image_url)
                debug_info += f"提取的域名: {domain}\n"

                if domain in self.config:
                    # 如果域名在配置中，则输出相应的提示信息
                    site_name = self.config[domain]  # 获取配置的值
                    debug_info += f"匹配到防盗链配置，站点名称: {site_name}\n"
                    parts.append(Plain(f"检测到 {site_name} 网站有防盗链机制，请使用“{site_name}：id”的格式获取图片。\n"))
                    last_end = end  # 跳过该图片的处理
                    continue
                else:
                    debug_info += f"加载的防盗链配置: {self.config}\n"
                    debug_info += "未在防盗链配置中找到该域名\n"
            else:
                debug_info += "URL 不包含图片后缀，跳过防盗链检测\n"

            # 如果没有检测到防盗链限制，或者图片后缀不符合，继续进行 HTTP 检测
            if self.is_image_url(image_url):
                debug_info += "URL 通过 HTTP 检测是有效的图片链接\n"
                parts.append(Image(url=image_url))
            else:
                # 如果图片检测失败，输出提示语并保留原始文本
                debug_info += "链接无法访问，返回原始消息部分\n"
                parts.append(Plain("链接无法访问，请检查 URL 是否正确。\n"))
                parts.append(Plain(match.group(0)))

            last_end = end

        # 添加最后一段未处理的文本
        if last_end < len(message):
            parts.append(Plain(message[last_end:]))

        # 在消息末尾添加调试信息
        parts.append(Plain(f"调试信息:\n{debug_info}"))

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
