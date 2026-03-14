"""
财经新闻爬取模块
参考 https://github.com/cxyo/xw 项目
"""
import asyncio
import difflib
import hashlib
import aiohttp
import json
import logging
import re
from datetime import datetime
from typing import Dict, List

from bs4 import BeautifulSoup

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
    },
    "yicai": {
        "name": "第一财经",
        "url": "https://www.yicai.com/news/",
        "list_selector": ".m-newslist li",
        "title_selector": "h2 a, .title a",
        "link_selector": "a",
    },
    "stcn": {
        "name": "证券时报",
        "url": "https://www.stcn.com/",
        "list_selector": "a[href*='/article/detail/']",
        "title_selector": "a",
        "link_selector": "a",
    },
    "cnstock": {
        "name": "上海证券报",
        "url": "https://www.cnstock.com/",
        "list_selector": "a[href*='Detail/'], a[href*='topicDetail/']",
        "title_selector": "a",
        "link_selector": "a",
    },
}


class NewsFetcher:
    """新闻爬取器"""

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        }

    async def fetch_url(self, session: aiohttp.ClientSession, url: str) -> str:
        """获取页面内容"""
        try:
            async with session.get(
                url,
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                return await response.text(errors="ignore")
        except Exception as e:
            logger.warning("Error fetching %s: %s", url, e)
            return ""

    def parse_eastmoney(self, html: str) -> List[Dict]:
        """解析东方财富网新闻"""
        news_list = []
        soup = BeautifulSoup(html, "lxml")

        for script in soup.find_all("script"):
            script_text = script.string
            if script_text and "liveData" in script_text:
                try:
                    start = script_text.find("liveData:")
                    if start > 0:
                        _ = script_text.find("}", start + 200) + 1
                except Exception:
                    pass

        for item in soup.select("li")[:80]:
            title_elem = item.select_one("a")
            if title_elem and title_elem.get("href"):
                title = title_elem.get_text(strip=True)
                if len(title) > 10 and any(keyword in title for keyword in ("股市", "A股", "央行", "板块")):
                    news_list.append({
                        "title": title,
                        "source": "东方财富网",
                        "url": "https://finance.eastmoney.com" + title_elem.get("href", ""),
                        "time": datetime.now().strftime("%H:%M"),
                    })
                    if len(news_list) >= 40:
                        break

        return news_list

    def parse_sina(self, html: str) -> List[Dict]:
        """解析新浪财经新闻"""
        news_list = []
        soup = BeautifulSoup(html, "lxml")

        for item in soup.select(".blk_hdline_01, .news-item")[:60]:
            title_elem = item.select_one("a")
            if title_elem:
                title = title_elem.get_text(strip=True)
                if len(title) > 10:
                    news_list.append({
                        "title": title,
                        "source": "新浪财经",
                        "url": title_elem.get("href", ""),
                        "time": datetime.now().strftime("%H:%M"),
                    })

        return news_list

    def parse_yicai(self, html: str) -> List[Dict]:
        """解析第一财经新闻"""
        news_list = []
        soup = BeautifulSoup(html, "lxml")
        seen_titles = set()

        selectors = [
            ".m-newslist li a[href*='/news/']",
            ".f-list li a[href*='/news/']",
            "article a[href*='/news/']",
            "a[href*='/news/']",
        ]
        anchors = []
        for selector in selectors:
            anchors = soup.select(selector)
            if anchors:
                break

        for anchor in anchors:
            title = anchor.get_text(" ", strip=True)
            href = anchor.get("href", "").strip()
            title = re.sub(r"\s+\d+\s+(分钟前|小时前|天前)$", "", title)
            title = re.sub(r"\s+0\s+\d+(分钟前|小时前|天前)$", "", title)
            if len(title) <= 10 or not href:
                continue
            if title in seen_titles:
                continue

            if href.startswith("/"):
                href = f"https://www.yicai.com{href}"

            seen_titles.add(title)
            news_list.append({
                "title": title,
                "source": "第一财经",
                "url": href,
                "time": datetime.now().strftime("%H:%M"),
            })
            if len(news_list) >= 40:
                break

        return news_list

    def parse_cls(self, html: str) -> List[Dict]:
        """解析财联社电报（优先读取 Next.js 内嵌数据）"""
        next_data_match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
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
                for item in telegraph_items[:80]:
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
                        "time": self._format_cls_time(item.get("ctime") or item.get("created_at")),
                    })
                if parsed_items:
                    return parsed_items
            except Exception as e:
                logger.warning("CLS next data parse error: %s", e)

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
                        "time": time_str or datetime.now().strftime("%H:%M"),
                    })

        return news_list

    def parse_stcn(self, html: str) -> List[Dict]:
        """解析证券时报首页新闻"""
        news_list = []
        soup = BeautifulSoup(html, "lxml")
        seen_titles = set()

        for anchor in soup.select("a[href*='/article/detail/'], a[href*='/topic/detail/']"):
            title = anchor.get_text(" ", strip=True)
            href = anchor.get("href", "").strip()
            if len(title) <= 12 or not href or title in seen_titles:
                continue
            if href.startswith("/"):
                href = f"https://www.stcn.com{href}"
            seen_titles.add(title)
            news_list.append({
                "title": title,
                "source": "证券时报",
                "url": href,
                "time": datetime.now().strftime("%H:%M"),
            })
            if len(news_list) >= 35:
                break

        return news_list

    def parse_cnstock(self, html: str) -> List[Dict]:
        """解析上海证券报首页新闻"""
        news_list = []
        soup = BeautifulSoup(html, "lxml")
        seen_titles = set()

        for anchor in soup.select("a[href*='Detail/'], a[href*='topicDetail/'], a[href*='commonDetail/']"):
            title = anchor.get_text(" ", strip=True)
            href = anchor.get("href", "").strip()
            if len(title) <= 12 or not href or title in seen_titles:
                continue
            if href.startswith("/"):
                href = f"https://www.cnstock.com{href}"
            seen_titles.add(title)
            news_list.append({
                "title": title,
                "source": "上海证券报",
                "url": href,
                "time": datetime.now().strftime("%H:%M"),
            })
            if len(news_list) >= 35:
                break

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
                logger.warning("%s 未返回内容", source["name"])
                return []
            parse_fn = getattr(self, f"parse_{source_key}")
            parsed = parse_fn(html)
            logger.info("新闻源 %s 抓取成功，获取 %s 条", source["name"], len(parsed))
            return parsed
        except Exception as e:
            logger.warning("%s fetch error: %s", source_key, e)
            return []

    async def fetch_all_news(self) -> List[Dict]:
        """从所有源并发获取新闻"""
        all_news: List[Dict] = []

        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                self._fetch_source(session, "cls"),
                self._fetch_source(session, "eastmoney"),
                self._fetch_source(session, "sina"),
                self._fetch_source(session, "yicai"),
                self._fetch_source(session, "stcn"),
                self._fetch_source(session, "cnstock"),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
                elif isinstance(result, Exception):
                    logger.warning("Source fetch raised: %s", result)

        if not all_news:
            raise RuntimeError("所有新闻源均未返回有效内容")

        logger.info("新闻去重前共 %s 条", len(all_news))
        unique_news = self._deduplicate_news(all_news)
        logger.info("新闻去重后剩余 %s 条", len(unique_news))

        for news in unique_news:
            news["category"] = self._categorize_news(news["title"])
            news["hot_score"] = self._score_news(news["title"], news["category"], news["source"])
            stable_hash = hashlib.md5(f"{news['source']}:{news['title']}".encode()).hexdigest()[:8]
            news["id"] = f"{news['source']}_{stable_hash}"

        unique_news.sort(key=lambda item: item.get("hot_score", 0), reverse=True)
        return unique_news[:100]

    @staticmethod
    def _normalize_title(title: str) -> str:
        """标准化标题：去除空白、标点，转小写，便于相似度比较"""
        return re.sub(r"[\s\W]", "", title).lower()

    def _deduplicate_news(self, news_list: List[Dict]) -> List[Dict]:
        """基于标题相似度进行去重。"""
        min_substring_length = 8
        similarity_threshold = 0.75

        unique_news: List[Dict] = []
        seen_normalized: List[str] = []

        for news in news_list:
            norm = self._normalize_title(news["title"])
            if not norm:
                continue

            is_dup = False
            for seen in seen_normalized:
                if norm == seen:
                    is_dup = True
                    break

                shorter, longer = (norm, seen) if len(norm) <= len(seen) else (seen, norm)
                if len(shorter) >= min_substring_length and shorter in longer:
                    is_dup = True
                    break

                ratio = difflib.SequenceMatcher(None, norm, seen).ratio()
                if ratio >= similarity_threshold:
                    is_dup = True
                    break

            if not is_dup:
                unique_news.append(news)
                seen_normalized.append(norm)

        return unique_news

    def _categorize_news(self, title: str) -> str:
        """根据标题给新闻分类"""
        title = title or ""
        keywords = {
            "宏观": [
                "央行", "降准", "降息", "加息", "逆回购", "MLF", "LPR", "GDP", "CPI", "PPI",
                "PMI", "社融", "财政", "货币政策", "财政政策", "国务院", "发改委", "商务部",
                "出口", "进口", "关税", "汇率", "人民币", "美元", "黄金", "原油", "国债",
                "美联储", "非农", "就业", "通胀", "经济", "增长", "政策"
            ],
            "A股": [
                "A股", "沪指", "深成指", "创业板", "科创板", "北交所", "上证", "深证", "两市",
                "北向资金", "龙虎榜", "量化", "涨停潮", "题材股", "沪深", "大盘", "股市"
            ],
            "美股": [
                "美股", "纳斯达克", "纳指", "标普", "道指", "华尔街", "美债", "英伟达", "特斯拉",
                "苹果", "微软", "亚马逊", "谷歌", "Meta", "OpenAI"
            ],
            "行业": [
                "新能源", "光伏", "储能", "风电", "算力", "AI", "人工智能", "芯片", "半导体", "医药",
                "创新药", "白酒", "房地产", "银行", "券商", "保险", "消费", "军工", "机器人",
                "锂电", "稀土", "煤炭", "钢铁", "有色", "航运", "港口", "制造业", "汽车", "电商"
            ],
            "个股": [
                "涨停", "跌停", "公告", "重组", "并购", "业绩", "预增", "预亏", "回购", "减持",
                "增持", "停牌", "复牌", "分红", "年报", "季报", "股份", "有限公司", "集团"
            ],
        }

        for category, kw_list in keywords.items():
            if any(kw in title for kw in kw_list):
                return category

        return "财经"

    def _score_news(self, title: str, category: str, source: str) -> int:
        """给新闻打热点/洞察优先级分，便于前端筛热点。"""
        score = 10
        title = title or ""

        source_bonus = {
            "财联社": 8,
            "第一财经": 6,
            "证券时报": 6,
            "上海证券报": 6,
            "东方财富网": 4,
            "新浪财经": 3,
        }
        category_bonus = {
            "宏观": 14,
            "A股": 10,
            "美股": 10,
            "行业": 8,
            "个股": 6,
            "财经": 5,
        }
        score += source_bonus.get(source, 0)
        score += category_bonus.get(category, 0)

        high_signal_keywords = [
            "突发", "重磅", "首次", "明确", "落地", "加码", "叫停", "新高", "大涨", "大跌",
            "政策", "规划", "补贴", "关税", "降准", "降息", "美联储", "财报", "超预期", "爆发",
            "并购", "回购", "订单", "价格", "涨价", "业绩", "风险", "改革", "方案"
        ]
        for kw in high_signal_keywords:
            if kw in title:
                score += 4

        if len(title) >= 22:
            score += 2
        return score

    async def fetch_mock_news(self) -> List[Dict]:
        """模拟新闻数据（用于测试）"""
        return [
            {
                "id": "mock_1",
                "title": "央行宣布下调存款准备金率0.25个百分点，释放长期资金约5000亿元",
                "source": "东方财富网",
                "url": "",
                "time": "10:30",
                "category": "宏观",
            },
            {
                "id": "mock_2",
                "title": "A股三大指数集体收涨，创业板指涨超2%，新能源板块爆发",
                "source": "财联社",
                "url": "",
                "time": "15:00",
                "category": "A股",
            },
            {
                "id": "mock_3",
                "title": "美联储暗示可能在下季度暂停加息，美股科技股大涨",
                "source": "新浪财经",
                "url": "",
                "time": "09:45",
                "category": "美股",
            },
            {
                "id": "mock_4",
                "title": "半导体板块持续走强，多家公司业绩预增超预期",
                "source": "东方财富网",
                "url": "",
                "time": "14:20",
                "category": "行业",
            },
            {
                "id": "mock_5",
                "title": "白酒板块震荡调整，高端白酒龙头股领跌",
                "source": "财联社",
                "url": "",
                "time": "13:50",
                "category": "行业",
            },
            {
                "id": "mock_6",
                "title": "国家发改委：将出台新一轮促消费政策，重点支持新能源汽车",
                "source": "新浪财经",
                "url": "",
                "time": "11:00",
                "category": "宏观",
            },
            {
                "id": "mock_7",
                "title": "北向资金净流入超50亿元，连续5日加仓A股",
                "source": "财联社",
                "url": "",
                "time": "15:30",
                "category": "A股",
            },
            {
                "id": "mock_8",
                "title": "人工智能概念股集体拉升，算力板块领涨",
                "source": "东方财富网",
                "url": "",
                "time": "10:15",
                "category": "行业",
            },
            {
                "id": "mock_9",
                "title": "国际油价大幅波动，布伦特原油跌破80美元关口",
                "source": "新浪财经",
                "url": "",
                "time": "08:30",
                "category": "宏观",
            },
            {
                "id": "mock_10",
                "title": "多家券商发布研报：看好A股后市，建议关注低估值蓝筹",
                "source": "财联社",
                "url": "",
                "time": "16:00",
                "category": "A股",
            },
        ]


fetcher = NewsFetcher()
