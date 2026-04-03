#!/usr/bin/env python3
"""热点新闻"""
import argparse
import json
import subprocess
import sys
import urllib.request
import urllib.parse


def get_bing_news(keyword=""):
    """使用Bing搜索获取新闻"""
    try:
        if keyword:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(keyword + ' 新闻')}"
        else:
            url = "https://www.bing.com/news"
        
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")
        
        # 简单提取标题
        import re
        titles = re.findall(r'<a[^>]+class="news_title"[^>]*>([^<]+)</a>', html)
        if not titles:
            titles = re.findall(r'<a[^>]+href="https://www\.bing\.com/news[^"]*"[^>]*>([^<]+)</a>', html)
        
        return [{"title": t.strip()[:50], "source": "Bing"} for t in titles[:10] if t.strip()]
    except Exception as e:
        return [{"title": f"获取失败: {str(e)[:30]}", "source": "错误"}]


def get_default_news():
    """默认新闻（内置）"""
    return [
        {"title": "今日热搜（需要网络连接）", "source": "提示"},
        {"title": "可以使用 --search 参数搜索", "source": "帮助"},
        {"title": "例如: python news.py --search 科技", "source": "示例"}
    ]


def format_output(news, title):
    lines = [f"===== {title} ====="]
    for i, item in enumerate(news[:10]):
        lines.append(f"{i+1}. {item.get('title', '')}")
        if item.get('source'):
            lines[-1] += f" ({item['source']})"
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="热点新闻")
    parser.add_argument("--hot", action="store_true", help="今日热点")
    parser.add_argument("--tech", action="store_true", help="科技新闻")
    parser.add_argument("--search", help="搜索新闻")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    news = []

    if args.search:
        news = get_bing_news(args.search)
        title = f"搜索: {args.search}"
    elif args.tech:
        news = get_bing_news("科技")
        title = "科技新闻"
    elif args.hot:
        news = get_bing_news()
        title = "今日热点"
    else:
        news = get_default_news()
        title = "新闻"

    if args.json:
        print(json.dumps({"news": news, "title": title}, indent=2, ensure_ascii=False))
    else:
        if news:
            print(format_output(news, title))
        else:
            print("获取新闻失败")

    return 0


if __name__ == "__main__":
    sys.exit(main())
