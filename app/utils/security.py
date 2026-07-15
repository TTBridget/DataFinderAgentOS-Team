"""
security.py - 安全工具函数
提供输入转换、URL 校验、SSRF 防护等通用安全能力
"""
import ipaddress
import os
import re
import socket
import urllib.parse
from typing import Optional


# 允许的 LLM 提供商域名白名单（根据实际部署扩展）
LLM_HOST_ALLOWLIST = {
    "api.openai.com",
    "api.groq.com",
    "api.anthropic.com",
    "api.deepseek.com",
    "api.moonshot.cn",
    "api.qwen.aliyun.com",
    "api.baichuan-ai.com",
    "aigc-api.aitoolcore.com",
    "apihub.agnes-ai.com",
    "api.spark-api.com",
    "api.minimax.chat",
    "api.cohere.com",
    "api.ai21.com",
    "api.together.xyz",
    "api.perplexity.ai",
    "openrouter.ai",
    "api.fireworks.ai",
    "api.siliconflow.cn",
    "api.openai-proxy.org",
    "api.chatanywhere.tech",
    "api.chatanywhere.com.cn",
    "apikey.gpt-12450.com",
    "api.gptapi.us",
    "api.mistral.ai",
    "api.openai.azure.com",
}


def safe_int(value, default=0):
    """安全地将值转换为整数，失败时返回默认值"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    """安全地将值转换为浮点数，失败时返回默认值"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def is_private_ip(host: str) -> bool:
    """判断主机名解析后的 IP 是否属于私有/内部地址"""
    try:
        # 先尝试直接作为 IP 地址处理
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
    except ValueError:
        pass

    try:
        # 解析域名
        resolved = socket.getaddrinfo(host, None)
        seen_ips = set()
        for item in resolved:
            ip_str = item[4][0]
            if ip_str in seen_ips:
                continue
            seen_ips.add(ip_str)
            addr = ipaddress.ip_address(ip_str)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return True
        return False
    except Exception:
        # 无法解析时保守地视为内部地址
        return True


def validate_http_url(url: str, allow_empty: bool = False, allowlist: Optional[set] = None, allow_private: bool = False) -> bool:
    """
    校验 URL 是否安全（用于防止 SSRF）
    - 仅允许 http/https 协议
    - 默认禁止私有/内部 IP 地址（allow_private=True 时放行）
    - 如果提供 allowlist，则目标主机必须在白名单内
    """
    if not url:
        return allow_empty

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    host = parsed.hostname
    if not host:
        return False

    # 禁止用户名密码片段
    if parsed.username is not None or parsed.password is not None:
        return False

    # 检查 IP 类型
    if not allow_private and is_private_ip(host):
        return False

    # 白名单检查
    if allowlist:
        host_lower = host.lower()
        if host_lower not in allowlist:
            # 也支持子域匹配：*.openai.com
            allowed = any(
                host_lower == allowed_host or
                (allowed_host.startswith("*.") and host_lower.endswith(allowed_host[1:]))
                for allowed_host in allowlist
            )
            if not allowed:
                return False

    return True


def validate_llm_base_url(base_url: str) -> bool:
    """校验 LLM base_url 是否安全。DEBUG 模式下允许本地/内网地址，方便接入 Ollama/vLLM 等本地模型。"""
    debug = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
    return validate_http_url(
        base_url,
        allowlist=None if debug else LLM_HOST_ALLOWLIST,
        allow_private=debug
    )


def validate_employee_api_url(api_url: str) -> bool:
    """
    校验数字员工 API URL 是否安全。
    允许 URL 中包含 {message} / {query} 占位符，校验时先替换为空字符串再检查 base URL。
    """
    if not api_url:
        return True
    # 去掉占位符，得到可解析的 URL 骨架
    normalized = api_url.replace("{message}", "").replace("{query}", "")
    # 去掉占位符后可能产生连续的斜杠或末尾无路径，直接校验原始 URL 中除占位符外的主机部分
    return validate_http_url(api_url.replace("{message}", "placeholder").replace("{query}", "placeholder"))


def normalize_int_param(handler, name: str, default: int = 0):
    """从 handler 参数中安全读取整数"""
    value = handler.get_argument(name, None)
    if value is None:
        return default
    return safe_int(value, default)


def normalize_body_int(handler, name: str, default: int = 0):
    """从 handler body 参数中安全读取整数"""
    value = handler.get_body_argument(name, None)
    if value is None:
        return default
    return safe_int(value, default)
