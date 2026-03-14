"""
财经新闻爬取模块
参考 https://github.com/cxyo/xw 项目
"""
import asyncio
import hashlib
import aiohttp
import json
import logging
import re
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict

logger = logging.getLogger(__name__)

# 新闻源配置
NEWS_SOURCES = {
    "eastmoney": {
        "name": "东方财富网",
        "url": "https://finance.eastmoney.com/a/cjkx.html",
        "list_selector": "li.list-item",
        "title_selector": "a",
        "link_selector": "a",
        "time_selector": "span.time",
    },
    "sina": {
        "name": "新浪财经",
        "url": "https://finance.sina.com.cn/",
        "list_selector": ".news-item",
        "title_selector": "a",
        "link_selector": "a",
    },
    "cls": {
        "name": "财联社",
        "url": "https://www.cls.cn/telegraph",
        "list_selector": ".telegraph-item",
        "title_selector": "h3",
        "link_selector": "a",
    }
}


class NewsFetcher:
    """新闻爬取器"""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def fetch_url(self, session: aiohttp.ClientSession, url: str) -> str:
        """获取页面内容"""
        try:
            async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                return await response.text(errors="ignore")
        except Exception as e:
            logger.warning("Error fetching %s: %s", url, e)
            return ""

    def parse_eastmoney(self, html: str) -> List[Dict]:
        """解析东方财富网新闻"""
        news_list = []
        soup = BeautifulSoup(html, "lxml")

        # 东方财富网的快讯在 script 标签的 JSON 数据中
        for script in soup.find_all("script"):
            script_text = script.string
            if script_text and "liveData" in script_text:
                try:
                    # 提取JSON数据
                    start = script_text.find("liveData:")
                    if start > 0:
                        end = script_text.find("}", start + 200) + 1
                        # 简化处理：直接解析页面结构
                except:
                    pass

        # 备用方案：解析新闻列表
        for item in soup.select("li")[:30]:
            title_elem = item.select_one("a")
            if title_elem and title_elem.get("href"):
                title = title_elem.get_text(strip=True)
                if len(title) > 10 and any(keyword in title for keyword in ("股市", "A股", "央行", "板块")):
                    news_list.append({
                        "title": title,
                        "source": "东方财富网",
                        "url": "https://finance.eastmoney.com" + title_elem.get("href", ""),
                        "time": datetime.now().strftime("%H:%M")
                    })
                    if len(news_list) >= 20:
                        break

        return news_list

    def parse_sina(self, html: str) -> List[Dict]:
        """解析新浪财经新闻"""
        news_list = []
        soup = BeautifulSoup(html, "lxml")

        for item in soup.select(".blk_hdline_01, .news-item")[:20]:
            title_elem = item.select_one("a")
            if title_elem:
                title = title_elem.get_text(strip=True)
                if len(title) > 10:
                    news_list.append({
                        "title": title,
                        "source": "新浪财经",
                        "url": title_elem.get("href", ""),
                        "time": datetime.now().strftime("%H:%M")
                    })

        return news_list

    def parse_cls(self, html: str) -> List[Dict]:
        """解析财联社电报（优先读取 Next.js 内嵌数据）"""
        next_data_match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html,
            re.DOTALL
        )
        if next_data_match:
            try:
                next_data = json.loads(next_data_match.group(1))
                telegraph_items = (
                    next_data.get("props", {})
                    .get("initialState", {})
                    .get("telegraph", {})
                    .get("telegraphList", [])
                )
                parsed_items = []
                for item in telegraph_items[:30]:
                    title = self._clean_cls_text(item.get("title") or item.get("content", ""))
                    if len(title) < 10:
                        continue

                    detail_url = item.get("share_url") or item.get("url") or ""
                    if detail_url and detail_url.startswith("/"):
                        detail_url = f"https://www.cls.cn{detail_url}"

                    parsed_items.append({
                        "title": title,
                        "source": "财联社",
                        "url": detail_url,
                        "time": self._format_cls_time(item.get("ctime") or item.get("created_at"))
                    })
                if parsed_items:
                    return parsed_items
            except Exception as e:
                logger.warning("CLS next data parse error: %s", e)

        # 解析财联社电报
        news_list = []
        soup = BeautifulSoup(html, "lxml")

        for item in soup.select(".telegraph-list .item")[:20]:
            title_elem = item.select_one(".text")
            time_elem = item.select_one(".time")

            if title_elem:
                title = title_elem.get_text(strip=True)
                time_str = time_elem.get_text(strip=True) if time_elem else ""

                if len(title) > 10:
                    news_list.append({
                        "title": title,
                        "source": "财联社",
                        "url": "",
                        "time": time_str or datetime.now().strftime("%H:%M")
                    })

        return news_list

    def _clean_cls_text(self, text: str) -> str:
        """清理财联社正文中的 HTML 标记"""
        return BeautifulSoup(text or "", "lxml").get_text(" ", strip=True)

    def _format_cls_time(self, raw_time) -> str:
        """兼容财联社不同时间字段格式"""
        if not raw_time:
            return datetime.now().strftime("%H:%M")

        raw_time = str(raw_time).strip()
        if raw_time.isdigit():
            timestamp = int(raw_time)
            if timestamp > 10**12:
                timestamp = timestamp / 1000
            try:
                return datetime.fromtimestamp(timestamp).strftime("%H:%M")
            except (OverflowError, ValueError):
                return datetime.now().strftime("%H:%M")

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(raw_time, fmt).strftime("%H:%M")
            except ValueError:
                continue

        return raw_time[:5] if len(raw_time) >= 5 else datetime.now().strftime("%H:%M")

    async def _fetch_source(self, session: aiohttp.ClientSession, source_key: str) -> List[Dict]:
        """获取单个新闻源"""
        source = NEWS_SOURCES[source_key]
        try:
            html = await self.fetch_url(session, source["url"])
            if not html:
                return []
            parse_fn = getattr(self, f"parse_{source_key}")
            return parse_fn(html)
        except Exception as e:
            logger.warning("%s fetch error: %s", source_key, e)
            return []

    async def fetch_all_news(self) -> List[Dict]:
        """从所有源并发获取新闻"""
        all_news = []

        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                self._fetch_source(session, "cls"),
                self._fetch_source(session, "eastmoney"),
                self._fetch_source(session, "sina"),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, list):
                    all_news.extend(r)
                elif isinstance(r, Exception):
                    logger.warning("Source fetch raised: %s", r)

        if not all_news:
            raise RuntimeError("所有新闻源均未返回有效内容")

        # 去重（按标题前20字符）
        seen_titles: set = set()
        unique_news = []
        for news in all_news:
            title_key = news["title"][:20]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_news.append(news)

        # 添加分类标签和稳定 ID
        for news in unique_news:
            news["category"] = self._categorize_news(news["title"])
            stable_hash = hashlib.md5(
                f"{news['source']}:{news['title']}".encode()
            ).hexdigest()[:8]
            news["id"] = f"{news['source']}_{stable_hash}"

        return unique_news[:50]  # 返回最新50条

    def _categorize_news(self, title: str) -> str:
        """根据标题给新闻分类"""
        keywords = {
            "宏观": ["央行", "降准", "加息", "GDP", "通胀", "政策", "国务院"],
            "A股": ["A股", "上证", "深证", "创业板", "指数", "大盘", "股市"],
            "美股": ["美股", "纳斯达克", "标普", "道指", "美联储", "华尔街"],
            "行业": ["新能源", "芯片", "半导体", "医药", "白酒", "房地产", "银行"],
            "个股": ["涨停", "跌停", "公告", "重组", "并购", "业绩"],
        }

        for category, kw_list in keywords.items():
            if any(kw in title for kw in kw_list):
                return category

        return "财经"

    async def fetch_mock_news(self) -> List[Dict]:
        """模拟新闻数据（用于测试）"""
        return [
            {
                "id": "mock_1",
                "title": "央行宣布下调存款准备金率0.25个百分点，释放长期资金约5000亿元",
                "source": "东方财富网",
                "url": "",
                "time": "10:30",
                "category": "宏观"
            },
            {
                "id": "mock_2",
                "title": "A股三大指数集体收涨，创业板指涨超2%，新能源板块爆发",
                "source": "财联社",
                "url": "",
                "time": "15:00",
                "category": "A股"
            },
            {
                "id": "mock_3",
                "title": "美联储暗示可能在下季度暂停加息，美股科技股大涨",
                "source": "新浪财经",
                "url": "",
                "time": "09:45",
                "category": "美股"
            },
            {
                "id": "mock_4",
                "title": "半导体板块持续走强，多家公司业绩预增超预期",
                "source": "东方财富网",
                "url": "",
                "time": "14:20",
                "category": "行业"
            },
            {
                "id": "mock_5",
                "title": "白酒板块震荡调整，高端白酒龙头股领跌",
                "source": "财联社",
                "url": "",
                "time": "13:50",
                "category": "行业"
            },
            {
                "id": "mock_6",
                "title": "国家发改委：将出台新一轮促消费政策，重点支持新能源汽车",
                "source": "新浪财经",
                "url": "",
                "time": "11:00",
                "category": "宏观"
            },
            {
                "id": "mock_7",
                "title": "北向资金净流入超50亿元，连续5日加仓A股",
                "source": "财联社",
                "url": "",
                "time": "15:30",
                "category": "A股"
            },
            {
                "id": "mock_8",
                "title": "人工智能概念股集体拉升，算力板块领涨",
                "source": "东方财富网",
                "url": "",
                "time": "10:15",
                "category": "行业"
            },
            {
                "id": "mock_9",
                "title": "国际油价大幅波动，布伦特原油跌破80美元关口",
                "source": "新浪财经",
                "url": "",
                "time": "08:30",
                "category": "宏观"
            },
            {
                "id": "mock_10",
                "title": "多家券商发布研报：看好A股后市，建议关注低估值蓝筹",
                "source": "财联社",
                "url": "",
                "time": "16:00",
                "category": "A股"
            }
        ]


# 全局实例
fetcher = NewsFetcher()
