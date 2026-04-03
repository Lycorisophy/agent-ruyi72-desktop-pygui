#!/usr/bin/env python3
"""Image Understanding Skill for OpenClaw"""

def main():
    """图片理解技能说明"""
    print("""
🖼️ Image Understanding Skill
    
这个技能使用 OpenClaw 内置的 images_understand 工具来分析图片。

使用方法：
1. 用户提供图片路径（如：C:\\Users\\LySoY\\Pictures\\photo.jpg）
2. AI 使用 images_understand 工具分析图片内容
3. 返回图片的详细描述

支持的格式：jpg, jpeg, png, gif, bmp, webp
大小限制：10MB

触发词：
- "看看这张图"
- "分析图片"
- "这张照片"
- "图片里"
- "识别图片"
""")

if __name__ == '__main__':
    main()
