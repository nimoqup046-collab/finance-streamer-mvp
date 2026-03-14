"""
AI内容生成模块
支持生成直播稿、公众号文章、深度长文
支持多种AI提供商：豆包、Anthropic Claude、OpenAI
"""
import logging
import re
import io
from datetime import datetime
from typing import AsyncIterator, Dict, List

from backend.config import AI_PROVIDER, AI_API_KEY, AI_API_BASE, AI_MODEL

logger = logging.getLogger(__name__)


class ContentGenerator:
    """内容生成器"""

    def __init__(self):
        self.provider = AI_PROVIDER
        self.model = AI_MODEL
        self.api_key = AI_API_KEY
        self.api_base = AI_API_BASE
        self.client = self._init_client()

    def _init_client(self):
        """根据提供商初始化异步客户端"""
        if self.provider == "anthropic":
            from anthropic import AsyncAnthropic
            return AsyncAnthropic(api_key=self.api_key)

        # 默认使用 OpenAI 兼容接口（豆包/OpenAI）
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=self.api_key, base_url=self.api_base or None)

    def _error_context(self) -> str:
        """补充 provider/model/base，方便线上排障"""
        return (
            f"provider={self.provider}, "
            f"model={self.model}, "
            f"base_url={self.api_base or 'default'}"
        )

    def _system_prompt(self) -> str:
        return (
            "你是一位专业的财经内容创作者，拥有10年财经媒体从业经验。"
            "你擅长将复杂的财经新闻转化为通俗易懂、有价值的内容。"
            "你的文字专业但不晦涩，深入但不枯燥，观点鲜明但客观理性。"
        )

    def _build_stream_script_prompt(
        self,
        news_items: List[Dict],
        duration: int = 30,
        style: str = "专业",
    ) -> str:
        """生成直播稿 prompt，供普通生成和流式生成复用。"""
        news_details = "\n".join([
            f"{i+1}. 【{n.get('category', '财经')}】{n['title']}\n   来源：{n['source']}"
            for i, n in enumerate(news_items)
        ])

        time_per_news = max(3, duration // len(news_items))
        date_str = datetime.now().strftime("%Y年%m月%d日 %A")
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now().weekday()]

        return f"""你是一位拥有10年经验的资深财经主播，正在为今晚的直播准备稿件。请根据以下新闻生成一份专业、生动、有深度的直播脚本。

【今日要闻】共{len(news_items)}条
{news_details}

【直播时长】约 {duration} 分钟
【每条新闻分配时间】约 {time_per_news} 分钟
【整体风格】{style}

【脚本要求】
1. **开场白**（150-200字）：
   - 亲切自然的问候
   - 快速进入主题，提及今日市场概况
   - 设置悬念，引发观众继续观看的兴趣

2. **主体内容**（每条新闻200-300字）：
   - 用口语化方式复述新闻要点
   - 深度分析背景、原因和影响
   - 加入数据解读和专业知识
   - 提供独特的观点和见解
   - 设计一个有价值的观众互动问题

3. **结尾总结**（150-200字）：
   - 概括今日最重要的3个要点
   - 给出明日市场的2-3个关注点
   - 感谢语和下次预告

【风格要求】
- 像真人说话，适当加入语气词
- 专业但不晦涩，深入但不枯燥
- 有个人观点，不是单纯播报
- 让观众有收获感和共鸣感

【字数要求】
- 总字数不少于1500字
- 开场白不少于150字
- 每条新闻解读不少于200字
- 结尾不少于150字

请直接输出完整的直播脚本，不要有多余的说明：

---
【开场白】
（150-200字的开场内容）

【新闻1】{news_items[0]['title'][:30]}...
（250-300字：复述+深度解读+互动提问）

【新闻2】...
...

【今日总结】
（150-200字总结）

【明日关注】
• 关注点1
• 关注点2
• 关注点3
---
"""

    async def generate_stream_script(
        self,
        news_items: List[Dict],
        duration: int = 30,
        style: str = "专业"
    ) -> str:
        """生成直播稿（目标1500-2000字）"""
        prompt = self._build_stream_script_prompt(news_items, duration=duration, style=style)

        try:
            response = await self._call_ai(prompt, max_tokens=4000)
            return self._format_stream_script(response, news_items)
        except Exception as e:
            logger.error("Generation error: %s | %s", e, self._error_context())
            return self._generate_fallback_script(news_items)

    async def stream_stream_script(
        self,
        news_items: List[Dict],
        duration: int = 30,
        style: str = "专业",
    ) -> AsyncIterator[str]:
        """流式生成直播稿文本片段。"""
        prompt = self._build_stream_script_prompt(news_items, duration=duration, style=style)

        try:
            async for chunk in self._stream_ai(prompt, max_tokens=4000):
                if chunk:
                    yield chunk
        except Exception as e:
            logger.error("Streaming generation error: %s | %s", e, self._error_context())
            fallback = self._generate_fallback_script(news_items)
            for chunk in self._chunk_text(fallback, chunk_size=160):
                yield chunk

    async def generate_ppt(
        self,
        news_items: List[Dict],
        title: str = "",
        style: str = "专业",
    ) -> bytes:
        """生成 PowerPoint 演示文稿并返回 PPTX 二进制。"""
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.util import Emu, Inches, Pt

        _ = style  # 为后续模板风格扩展预留
        prs = Presentation()
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)

        blue = RGBColor(0x1A, 0x56, 0xDB)
        dark = RGBColor(0x1F, 0x2A, 0x3C)
        white = RGBColor(0xFF, 0xFF, 0xFF)
        gray = RGBColor(0x6B, 0x72, 0x80)
        rectangle = 1

        def add_bg(slide, color):
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = color

        def add_textbox(slide, text, left, top, width, height, font_size=18, bold=False, color=None, align=PP_ALIGN.LEFT, wrap=True):
            tx_box = slide.shapes.add_textbox(left, top, width, height)
            tf = tx_box.text_frame
            tf.word_wrap = wrap
            paragraph = tf.paragraphs[0]
            paragraph.alignment = align
            run = paragraph.add_run()
            run.text = text
            run.font.size = Pt(font_size)
            run.font.bold = bold
            if color:
                run.font.color.rgb = color
            return tx_box

        layout = prs.slide_layouts[6]
        date_str = datetime.now().strftime("%Y年%m月%d日")

        slide = prs.slides.add_slide(layout)
        add_bg(slide, dark)
        cover_title = title or f"财经日报 · {date_str}"
        add_textbox(slide, cover_title, Inches(1), Inches(2.2), Inches(11.3), Inches(1.5), font_size=40, bold=True, color=white, align=PP_ALIGN.CENTER)
        add_textbox(slide, f"共 {len(news_items)} 条精选财经资讯  |  {date_str}", Inches(1), Inches(3.9), Inches(11.3), Inches(0.6), font_size=18, color=RGBColor(0xA0, 0xAE, 0xC0), align=PP_ALIGN.CENTER)

        slide = prs.slides.add_slide(layout)
        add_bg(slide, white)
        add_textbox(slide, "📋 目录", Inches(0.8), Inches(0.3), Inches(11), Inches(0.8), font_size=28, bold=True, color=blue)
        line = slide.shapes.add_shape(rectangle, Inches(0.8), Inches(1.2), Inches(11.7), Emu(30000))
        line.fill.solid()
        line.fill.fore_color.rgb = blue
        line.line.fill.background()

        rows_per_col = 5
        for idx, news in enumerate(news_items[:10]):
            col = idx // rows_per_col
            row = idx % rows_per_col
            left = Inches(0.8) + col * Inches(6.3)
            top = Inches(1.5) + row * Inches(0.9)
            snippet = f"{idx + 1}. {news['title'][:36]}{'…' if len(news['title']) > 36 else ''}"
            add_textbox(slide, snippet, left, top, Inches(5.9), Inches(0.8), font_size=13, color=dark)

        for idx, news in enumerate(news_items):
            slide = prs.slides.add_slide(layout)
            add_bg(slide, white)

            bar = slide.shapes.add_shape(rectangle, Inches(0), Inches(0), Inches(0.3), Inches(7.5))
            bar.fill.solid()
            bar.fill.fore_color.rgb = blue
            bar.line.fill.background()

            badge = f" {idx + 1} / {len(news_items)} · {news.get('category', '财经')} "
            add_textbox(slide, badge, Inches(0.5), Inches(0.2), Inches(5), Inches(0.5), font_size=11, color=blue, bold=True)
            add_textbox(slide, news["title"], Inches(0.5), Inches(0.8), Inches(12.2), Inches(1.6), font_size=24, bold=True, color=dark)
            meta = f"来源：{news['source']}    时间：{news.get('time', '')}"
            add_textbox(slide, meta, Inches(0.5), Inches(2.5), Inches(10), Inches(0.5), font_size=12, color=gray)
            add_textbox(slide, "💡 核心要点", Inches(0.5), Inches(3.1), Inches(3), Inches(0.45), font_size=13, bold=True, color=blue)

            bullet_top = Inches(3.6)
            for bullet in ["• 事件核心内容待解读", "• 市场影响分析待补充", "• 投资者关注点待梳理"]:
                add_textbox(slide, bullet, Inches(0.8), bullet_top, Inches(11.5), Inches(0.5), font_size=13, color=dark)
                bullet_top += Inches(0.55)

        slide = prs.slides.add_slide(layout)
        add_bg(slide, dark)
        add_textbox(slide, "📊 今日总结", Inches(1), Inches(1.5), Inches(11), Inches(1), font_size=36, bold=True, color=white, align=PP_ALIGN.CENTER)
        categories_seen = list(dict.fromkeys(n.get("category", "财经") for n in news_items))
        summary = (
            f"本次共收录 {len(news_items)} 条精选财经资讯\n"
            f"涵盖领域：{' · '.join(categories_seen)}\n"
            f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}"
        )
        add_textbox(slide, summary, Inches(1.5), Inches(3), Inches(10.3), Inches(2), font_size=16, color=RGBColor(0xA0, 0xAE, 0xC0), align=PP_ALIGN.CENTER)

        buf = io.BytesIO()
        prs.save(buf)
        return buf.getvalue()

    async def generate_article(
        self,
        news_items: List[Dict],
        title: str = ""
    ) -> Dict:
        """生成公众号文章（目标1500-2000字）"""
        # 构建新闻详情
        news_details = "\n".join([
            f"• {n['title']}（{n['source']}）"
            for n in news_items
        ])

        # 获取当日日期
        date_str = datetime.now().strftime("%Y年%m月%d日")
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][datetime.now().weekday()]

        prompt = f"""你是一位优秀的财经自媒体作者，擅长写深入浅出、观点犀利的财经文章。请根据以下新闻素材，撰写一篇高质量的微信公众号文章。

【新闻素材】共{len(news_items)}条
{news_details}

【文章要求】

**1. 标题（3个选项）**
- 标题1：数字+冲击力，如"降准了！央行突发重磅，释放5000亿资金"
- 标题2：提问式，如"今天发生了什么？这3条消息关乎你的钱包"
- 标题3：总结式，如"财经日报：政策利好频出，A股迎来新机遇"

**2. 导语（200字）**
- 快速抓住读者注意力
- 提炼今日最重要的变化
- 说明为什么值得关注
- 引发继续阅读的兴趣

**3. 正文结构**（每条新闻300-400字）
- 每条新闻作为独立小节
- 用吸引人的小标题
- 先说事实，再深入分析
- 加入专业观点和数据
- 说明对投资者的影响
- 语言通俗易懂

**4. 总结升华（200字）**
- 总结今日市场脉络
- 给投资者一条建议
- 引导关注

**5. 字数要求**
- 总字数不少于1500字
- 导语不少于200字
- 每条新闻不少于300字
- 结尾不少于150字

【输出格式】
请严格按照以下格式输出：

===标题选项===
标题1
标题2
标题3

===正文===
# 主标题

**导语**
200字导语内容...

## 小标题1
300-400字正文内容...

## 小标题2
300-400字正文内容...

---

**总结升华**
150-200字总结...

*本文仅供参考，不构成投资建议*
===
"""

        try:
            response = await self._call_ai(prompt, max_tokens=4000)
            return self._format_article(response)
        except Exception as e:
            logger.error("Article generation error: %s | %s", e, self._error_context())
            return self._generate_fallback_article(news_items)

    async def generate_deep_dive(
        self,
        news_items: List[Dict],
        focus_topic: str = ""
    ) -> str:
        """生成深度调研长文（目标2500-3500字）"""
        if not focus_topic:
            focus_topic = news_items[0]["title"]

        # 构建新闻详情
        news_details = "\n".join([
            f"• {n['title']}（{n['source']}）"
            for n in news_items[:6]
        ])

        prompt = f"""你是一位顶级证券分析师，拥有15年研究经验，曾在多家头部券商担任首席分析师。请针对以下财经事件，撰写一份专业的深度调研报告。

【核心事件】
{focus_topic}

【相关资讯】
{news_details}

【报告结构】
请按以下结构撰写，总字数不少于2500字：

---
# 深度调研报告：{focus_topic[:40]}

## 一、核心摘要（300字）
- 事件核心内容精述
- 关键数据和影响范围
- 主要结论和投资建议
- 报告逻辑框架

## 二、事件背景（400字）
- 事件起因和来龙去脉
- 相关政策背景和历史沿革
- 与历史类似事件的对比
- 事件发生的深层原因

## 三、深度分析
### 3.1 市场影响分析（500字）
- 对A股整体市场的影响（短期/中期/长期）
- 对相关板块的具体影响
- 对投资者情绪的影响
- 市场目前的定价是否充分

### 3.2 产业链分析（400字）
- 上游产业的影响和机遇
- 中游产业的调整方向
- 下游产业的需求变化
- 产业链价值重估

### 3.3 机构观点汇总（400字）
- 券商研报核心观点（至少3家）
- 公募/私募基金经理观点
- 外资机构看法
- 市场共识与分歧分析

## 四、投资逻辑（500字）
### 4.1 利好因素分析
- 政策利好
- 行业景气度
- 公司基本面
- 其他催化因素

### 4.2 利空因素分析
- 潜在风险
- 估值压力
- 竞争格局变化
- 其他不确定性

### 4.3 风险收益评估
- 预期收益空间
- 最大回撤风险
- 风险收益比
- 适合的投资者类型

## 五、投资建议（400字）
### 5.1 短期策略（1-3个月）
- 具体操作建议
- 关注标的类型
- 仓位配置建议
- 进出场时机

### 5.2 中长期策略（6-12个月）
- 布局方向
- 持仓周期
- 止盈止损策略

## 六、风险提示（200字）
- 政策风险
- 市场风险
- 行业风险
- 公司特有风险

## 七、总结与展望（200字）
- 未来6-12个月趋势判断
- 关键观察指标
- 结论性建议

---

【写作要求】
- 专业严谨，观点鲜明
- 数据支撑，逻辑清晰
- 深入浅出，避免过于学术化
- 提供具体可操作的建议
- 总字数不少于2500字
"""

        try:
            return await self._call_ai(prompt, max_tokens=6000)
        except Exception as e:
            logger.error("Deep dive generation error: %s | %s", e, self._error_context())
            return self._generate_fallback_deep_dive(news_items)

    async def _call_ai(self, prompt: str, max_tokens: int = 2000) -> str:
        """调用AI接口（异步）"""
        if not self.api_key:
            raise RuntimeError(f"缺少 {self.provider} 的 API Key")

        if self.provider == "anthropic":
            # 使用异步 Anthropic Claude API
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=0.8,
                system=self._system_prompt(),
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        else:
            # 使用异步 OpenAI 兼容接口（豆包等）
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.8
            )
            content = response.choices[0].message.content
            return content if content else ""

    async def _stream_ai(self, prompt: str, max_tokens: int = 2000) -> AsyncIterator[str]:
        """调用支持流式输出的 AI 接口。"""
        if not self.api_key:
            raise RuntimeError(f"缺少 {self.provider} 的 API Key")

        if self.provider == "anthropic":
            full_text = await self._call_ai(prompt, max_tokens=max_tokens)
            for chunk in self._chunk_text(full_text):
                yield chunk
            return

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.8,
            stream=True,
        )
        async for part in stream:
            delta = ""
            if part.choices:
                delta = part.choices[0].delta.content or ""
            if delta:
                yield delta

    def _chunk_text(self, text: str, chunk_size: int = 120) -> List[str]:
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    def _format_stream_script(self, content: str, news_items: List[Dict]) -> str:
        """格式化直播稿"""
        date_str = datetime.now().strftime("%Y年%m月%d日 %A")
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][datetime.now().weekday()]

        formatted = f"""
{'╔' + '═'*58 + '╗'}
║  📺 财经直播稿 - 专业版                                      ║
║  📅 {date_str} {weekday}{' '*(24-len(date_str)-len(weekday))}║
{'╚' + '═'*58 + '╝'}

{content}

{'─'*60}
📌 本稿由 AI 助手生成，仅供参考，请结合实际情况调整
📊 预计直播时长：{len(news_items) * 3}-{len(news_items) * 5} 分钟
{'─'*60}
"""
        return formatted

    def _format_article(self, content: str) -> Dict:
        """格式化公众号文章"""
        # 解析标题选项
        titles = []
        if "===标题选项===" in content:
            parts = content.split("===正文===")
            title_section = parts[0].replace("===标题选项===", "").strip()
            titles = [t.strip() for t in title_section.split("\n") if t.strip()][:3]
            content_body = parts[1] if len(parts) > 1 else content
        else:
            # 兼容旧格式
            title_match = re.search(r'【标题选项】\n(.+?)\n\n', content, re.DOTALL)
            if title_match:
                titles = [t.strip("- 123. ") for t in title_match.group(1).split("\n") if t.strip()]
            content_body = content

        if not titles:
            titles = [f"财经深度解读 {datetime.now().strftime('%m月%d日')}"]

        return {
            "titles": titles,
            "content": content_body.strip(),
            "html": self._markdown_to_html(content_body)
        }

    def _markdown_to_html(self, md: str) -> str:
        """Markdown转HTML（用于公众号）"""
        html = md

        # 清理旧格式标记
        html = html.replace("===标题选项===", "").replace("===正文===", "")
        html = re.sub(r'【标题选项】.+?\n\n', '', html, flags=re.DOTALL)

        # 标题转换
        html = re.sub(r'^# (.+)$', r'<h1 style="font-size: 22px; font-weight: bold; margin: 20px 0; color: #1a1a1a;">\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2 style="font-size: 18px; font-weight: bold; margin: 15px 0; color: #333;">\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3 style="font-size: 16px; font-weight: bold; margin: 12px 0; color: #555;">\1</h3>', html, flags=re.MULTILINE)

        # 加粗
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

        # 列表
        html = re.sub(r'^• (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.+<\/li>\n?)+', lambda m: f"<ul style='margin: 10px 0; padding-left: 20px;'>{m.group(0)}</ul>", html)

        # 段落处理
        paragraphs = html.split("\n\n")
        formatted_paragraphs = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith("<h") and not p.startswith("<ul") and not p.startswith("<li"):
                p = f"<p style='line-height: 1.8; margin: 15px 0; color: #333;'>{p}</p>"
            formatted_paragraphs.append(p)

        return "\n".join(formatted_paragraphs)

    def _generate_fallback_script(self, news_items: List[Dict]) -> str:
        """AI调用失败时的备用脚本"""
        date_str = datetime.now().strftime("%Y年%m月%d日")

        script = f"""
【开场白】
各位投资者朋友大家好，欢迎来到今天的财经直播间！今天是{date_str}，我是你们的主播。今天市场上发生了不少大事，从宏观政策到行业动态，每一条都可能影响你的投资决策。让我们一起来深入解读。

"""

        for i, news in enumerate(news_items, 1):
            script += f"""
【新闻{i}】{news['title']}

【深度解读】
这条消息来自{news['source']}，属于{news.get('category', '财经')}类别。从这条新闻可以看出，相关领域正在发生重要变化。对于投资者来说，需要密切关注相关板块的后续走势。

【数据支撑】
建议关注相关板块的成交量变化和资金流向，这些指标往往能够反映市场的真实态度。

【互动提问】
各位朋友，这条新闻对相关板块会有什么影响？欢迎在评论区分享你的观点！

"""

        script += f"""
【今日总结】
以上就是今天的主要内容。总结一下，今天最重要的消息有{len(news_items)}条，涉及{len(set(n.get('category','') for n in news_items))}个领域。建议大家重点关注政策导向明确、景气度提升的板块。

【明日关注】
• 关注市场成交量变化
• 关注北向资金流向
• 关注政策面动向
• 关注行业轮动节奏

感谢大家的收看，记得点赞关注，我们明天再见！

{'─'*60}
"""
        return script

    def _generate_fallback_article(self, news_items: List[Dict]) -> Dict:
        """备用文章生成"""
        date_str = datetime.now().strftime("%m月%d日")
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][datetime.now().weekday()]

        titles = [
            f"【财经日报】{news_items[0]['title'][:20]}等重磅新闻速览",
            f"今日市场热点：{len(news_items)}条重要新闻深度解读",
            f"投资者必看：{date_str}财经要闻汇总"
        ]

        content = f"# {titles[0]}\n\n"
        content += f"**{datetime.now().strftime('%Y年%m月%d日')} {weekday} | 财经要闻深度解读**\n\n"

        content += "## 📰 导读\n\n"
        content += f"今日市场共筛选出{len(news_items)}条重要新闻，涵盖宏观政策、行业动态、市场异动等多个领域。以下是深度解读：\n\n"

        for i, news in enumerate(news_items, 1):
            content += f"## 📌 新闻{i}：{news['title']}\n\n"
            content += f"**来源**：{news['source']} | **分类**：{news.get('category', '财经')}\n\n"
            content += "**深度解读**：\n\n"
            content += f"这条新闻反映了{news.get('category', '相关')}领域正在发生的重要变化。建议投资者关注相关板块的后续走势，特别是龙头企业的表现。\n\n"
            content += "**投资启示**：\n\n"
            content += "- 关注政策导向和落地进度\n- 关注行业基本面的改善\n- 关注市场资金的流向变化\n\n"

        content += "## 💡 今日总结\n\n"
        content += f"综合来看，今日{len(news_items)}条新闻传递出市场正在发生的变化。建议投资者保持理性，结合自身风险偏好，谨慎决策。\n\n"
        content += "> ⚠️ 本文仅供参考，不构成投资建议。投资有风险，入市需谨慎。\n"
        content += f"> 📅 报告生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n"

        return {
            "titles": titles,
            "content": content,
            "html": self._markdown_to_html(content)
        }

    def _generate_fallback_deep_dive(self, news_items: List[Dict]) -> str:
        """备用深度长文生成"""
        topic = news_items[0]['title']
        date_str = datetime.now().strftime("%Y年%m月%d日")

        return f"""
# 深度调研报告：{topic}

**报告日期**：{date_str}
**分析师**：AI 助手

---

## 一、核心摘要

本报告针对近期市场热点事件"{topic[:30]}"进行深度分析，为投资者提供专业的投资参考。

**主要结论**：
- 该事件短期内可能引发市场情绪波动
- 中长期来看，相关板块存在结构性机会
- 建议投资者关注基本面优质的标的

---

## 二、事件背景

{topic}

该事件近期受到市场广泛关注，可能对相关板块产生重要影响。从历史经验来看，类似事件往往带来板块性的投资机会。

---

## 三、市场分析

### 3.1 短期影响

短期内，市场情绪可能受到事件催化，相关板块可能出现波动。建议关注成交量和资金流向的变化。

### 3.2 中长期影响

从中长期来看，该事件可能加速行业格局重塑。龙头企业有望凭借优势进一步扩大市场份额。

---

## 四、投资建议

### 短期策略（1-3个月）

- 建议谨慎观望，等待市场方向明确
- 关注事件进展和政策动向
- 控制仓位，保持灵活性

### 中长期策略（6-12个月）

- 关注基本面改善的优质标的
- 把握行业格局重塑带来的机会
- 坚持价值投资理念

---

## 五、风险提示

1. **政策风险**：相关政策可能发生变化
2. **市场风险**：市场情绪波动可能超预期
3. **行业风险**：行业竞争格局可能发生变化
4. **公司风险**：公司经营存在不确定性

---

## 六、免责声明

本报告由 AI 助手生成，仅供参考，不构成投资建议。投资者据此操作，风险自担。

---

*报告生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}*
"""


# 全局实例
generator = ContentGenerator()
