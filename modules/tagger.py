import os
import re
import json
from pathlib import Path
from typing import List
from collections import Counter
from datetime import datetime

try:
    import jieba
    jieba.setLogLevel(20)
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    print("[⚠️] jieba 未安装，标签提取功能受限")

ROOT_DIR = "WeChatArticles"

STOPWORDS = {
    '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
    '自己', '这', '那', '他', '她', '它', '们', '这个', '那个', '什么', '怎么',
    '可以', '可能', '应该', '因为', '所以', '但是', '如果', '虽然', '还是',
    '已', '已经', '正在', '将', '将要', '被', '把', '让', '给', '对', '于',
    '从', '向', '往', '比', '更', '最', '非常', '特别', '真', '真的',
    '吗', '呢', '吧', '啊', '呀', '哦', '嗯', '啦', '哇', '哈',
    '做', '想', '知道', '觉得', '认为', '发现', '感觉', '开始', '进行', '完成',
    '时候', '地方', '样子', '方式', '方法', '东西', '事情', '问题', '情况',
    '一些', '一点', '一下', '一定', '一样', '一起', '一直', '一方面', '另一方面',
    '然后', '之后', '以前', '以后', '现在', '目前', '今天', '昨天', '明天',
    '我们', '你们', '他们', '大家', '自己', '别人',
    '个', '些', '种', '次', '件', '条', '把', '点', '方面',
    '大', '小', '多', '少', '新', '老', '高', '低', '长', '短',
    '第一', '第二', '第三', '首先', '其次', '最后', '总之',
    '比如', '例如', '包括', '其中', '除了', '以及', '并且', '或者',
    '而', '而且', '并且', '只是', '不过', '只是',
    '文章', '内容', '本文', '本', '该', '此',
    '使用', '利用', '通过', '根据', '按照', '基于',
    '需要', '必需', '必须', '需要', '应当', '需要',
    '能够', '得以', '从而', '以', '用于', '用作',
    '关于', '对于', '针对', '有关', '如下',
    '如何', '怎样', '怎么样', '为何', '为什么',
    '多少', '几次', '各种', '各样', '每个',
    '主要', '重要', '关键', '核心', '基本', '根本',
    '一种', '这样', '那样', '怎样',
}

class TagExtractor:
    def __init__(
        self,
        max_tags: int = 5
    ):
        self.max_tags = max_tags
        
        if JIEBA_AVAILABLE:
            for word in ['公众号', '微信', '视频', '音频', '图片']:
                jieba.add_word(word)
    
    def extract_from_text(self, text: str, title: str = '') -> List[str]:
        if not JIEBA_AVAILABLE:
            return self._simple_extract(text, title)
        
        words = []
        
        words.extend(jieba.cut(title))
        
        text_words = jieba.cut(text)
        words.extend(text_words)
        
        filtered = []
        for word in words:
            word = word.strip()
            if len(word) >= 2 and word not in STOPWORDS and not word.isdigit():
                if not re.match(r'^[\d\W]+$', word):
                    filtered.append(word)
        
        counter = Counter(filtered)
        top_words = [word for word, count in counter.most_common(self.max_tags * 2)]
        
        unique_words = []
        for word in top_words:
            is_substring = False
            for existing in unique_words:
                if word in existing and len(existing) > len(word):
                    is_substring = True
                    break
            if not is_substring:
                unique_words.append(word)
                if len(unique_words) >= self.max_tags:
                    break
        
        return unique_words[:self.max_tags]
    
    def _simple_extract(self, text: str, title: str = '') -> List[str]:
        all_text = title + ' ' + text
        
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', all_text)
        
        filtered = [w for w in words if w not in STOPWORDS and len(w) >= 2]
        
        counter = Counter(filtered)
        top_words = [word for word, count in counter.most_common(self.max_tags)]
        
        return top_words[:self.max_tags]
    
    def extract_from_markdown(self, md_path: Path) -> List[str]:
        if not md_path.exists() or not md_path.is_file():
            return []
        
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
        
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)
        
        content = re.sub(r'#+ ', '', content)
        
        content = re.sub(r'[*_`~]', '', content)
        
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else ''
        
        text = re.sub(r'[#*_`~\[\]()]+', ' ', content)
        text = ' '.join(text.split())
        
        return self.extract_from_text(text, title)
    
    def extract_tags_for_account(self, account_name: str) -> dict:
        def normalize(s):
            return ''.join(s.split())

        account_dir = Path(ROOT_DIR) / account_name
        
        if not account_dir.exists():
            print(f"[❌] 未找到公众号目录: {account_dir}")
            return {}
        
        json_file = account_dir / "data.json"
        if not json_file.exists():
            print(f"[❌] 未找到JSON文件: {json_file}")
            return {}
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        articles = data.get('articles', [])
        if not articles:
            return {}
        
        existing_folders = {}
        for folder in account_dir.iterdir():
            if not folder.is_dir():
                continue
            for f in folder.iterdir():
                if f.is_file() and f.suffix == '.md' and f.stat().st_size >= 500:
                    title_from_file = f.stem
                    existing_folders[normalize(title_from_file)] = f
                    break
        
        title_to_tags = {}
        
        for article in articles:
            title = article.get('title', '')
            if not title:
                continue
            
            norm_title = normalize(title)
            
            md_file = existing_folders.get(norm_title)
            if not md_file:
                md_file = article.get('local_path')
                if md_file:
                    md_file = Path(md_file)
                    if not md_file.exists():
                        md_file = None
            
            if not md_file:
                for folder in account_dir.iterdir():
                    if not folder.is_dir():
                        continue
                    if normalize(folder.name).find(norm_title[:20]) >= 0:
                        md_files = [f for f in folder.iterdir() if f.is_file() and f.suffix == '.md' and f.stat().st_size >= 500]
                        if md_files:
                            md_file = md_files[0]
                            break
            
            if md_file:
                print(f"[🏷️] 提取标签: {title[:30]}...")
                tags = self.extract_from_markdown(md_file)
                title_to_tags[title] = tags
                
                for a in articles:
                    if a.get('title') == title:
                        a['tags'] = tags
            else:
                tags = self.extract_from_text(title)
                title_to_tags[title] = tags
                
                for a in articles:
                    if a.get('title') == title:
                        a['tags'] = tags
        
        data['articles'] = articles
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[💾] 标签已更新到: {json_file}")
        
        return title_to_tags
    
    def extract_tags_single(self, article_dir: Path, title: str = '') -> List[str]:
        md_files = [f for f in article_dir.iterdir() if f.is_file() and f.suffix == '.md']
        
        if md_files:
            return self.extract_from_markdown(md_files[0])
        else:
            return self.extract_from_text(title)


def main():
    account_name = input("请输入公众号名称: ").strip()
    if not account_name:
        return
    
    extractor = TagExtractor()
    title_to_tags = extractor.extract_tags_for_account(account_name)
    
    print(f"\n{'='*50}")
    print(f"[📊] 标签提取完成，共处理 {len(title_to_tags)} 篇文章")
    
    for title, tags in list(title_to_tags.items())[:5]:
        print(f"\n{title[:30]}...")
        print(f"  标签: {', '.join(tags)}")


if __name__ == "__main__":
    main()
