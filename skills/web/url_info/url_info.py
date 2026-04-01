#!/usr/bin/env python3
"""
URL 信息技能脚本

获取 URL 对应网页的元信息
"""
import json
import re
import sys
from urllib.parse import urlparse


def extract_info_from_html(html: str, url: str) -> dict:
    """从 HTML 中提取信息"""
    info = {
        "title": "",
        "description": "",
        "keywords": "",
        "author": "",
        "og_title": "",
        "og_description": "",
    }
    
    # 标题
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    if title_match:
        info["title"] = title_match.group(1).strip()
    
    # Meta 描述
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I
    )
    if desc_match:
        info["description"] = desc_match.group(1).strip()
    else:
        # 尝试另一种顺序
        desc_match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
            html, re.I
        )
        if desc_match:
            info["description"] = desc_match.group(1).strip()
    
    # Meta 关键词
    keywords_match = re.search(
        r'<meta[^>]+name=["\']keywords["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I
    )
    if keywords_match:
        info["keywords"] = keywords_match.group(1).strip()
    
    # 作者
    author_match = re.search(
        r'<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I
    )
    if author_match:
        info["author"] = author_match.group(1).strip()
    
    # Open Graph
    og_title_match = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I
    )
    if og_title_match:
        info["og_title"] = og_title_match.group(1).strip()
    
    og_desc_match = re.search(
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I
    )
    if og_desc_match:
        info["og_description"] = og_desc_match.group(1).strip()
    
    return info


def main():
    params = json.loads(sys.stdin.read())
    
    url = params.get("url")
    
    if not url:
        result = {"success": False, "error": "缺少 url 参数"}
        print(json.dumps(result))
        return
    
    # 解析 URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        result = {"success": False, "error": f"无效的 URL: {url}"}
        print(json.dumps(result))
        return
    
    try:
        import httpx
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        
        info = extract_info_from_html(response.text, url)
        
        # 格式化输出
        lines = [f"=== URL 信息 ==="]
        lines.append(f"URL: {url}")
        lines.append(f"状态码: {response.status_code}")
        lines.append(f"内容类型: {response.headers.get('content-type', 'unknown')}")
        lines.append("")
        
        if info["title"]:
            lines.append(f"标题: {info['title']}")
        if info["description"]:
            lines.append(f"描述: {info['description']}")
        if info["keywords"]:
            lines.append(f"关键词: {info['keywords']}")
        if info["author"]:
            lines.append(f"作者: {info['author']}")
        
        result = {
            "success": True,
            "output": "\n".join(lines),
            "metadata": {
                "url": url,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                **info
            }
        }
        
    except ImportError:
        result = {
            "success": False,
            "error": "需要安装 httpx: pip install httpx"
        }
    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
    
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
