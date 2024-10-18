import json
from urllib.parse import urlparse

def get_domain(url):
    """提取 URL 的一级域名。"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc

    # 分割域名部分，去除子域名，只保留主域名部分（如 "i.pximg.net" -> "pximg"）
    domain_parts = domain.split('.')
    if len(domain_parts) > 2:
        return domain_parts[-2]  # 只返回主域名部分 "pximg"
    return domain_parts[0]

def check_anti_hotlinking(url, config):
    """检查 URL 是否在防盗链配置中，并返回相应的提示信息。"""
    domain = get_domain(url)
    if domain in config:
        site_name = config[domain]
        return f"检测到 {site_name} 网站有防盗链机制，请使用“{site_name}：id”的格式获取图片。"
    else:
        return "未检测到防盗链限制，URL 可以直接使用。"

# 加载配置文件
def load_config(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("配置文件未找到，请检查路径。")
        return {}

# 测试函数
def test():
    # 示例配置文件路径
    config_path = 'config.json'
    config = load_config(config_path)

    # 测试 URL 列表
    test_urls = [
        "https://i.pximg.net/img-original/img/2024/03/22/18/48/40/117148036_p0.jpg"
    ]

    # 逐个测试 URL
    for url in test_urls:
        print(f"测试 URL: {url}")
        result = check_anti_hotlinking(url, config)
        print(f"检测结果: {result}")
        print("-" * 40)

if __name__ == "__main__":
    test()
