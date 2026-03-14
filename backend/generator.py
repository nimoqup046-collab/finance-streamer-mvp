"""
AI内容生成模块
支持生成直播稿、公众号文章、深度长文
支持多种AI提供商：豆包、Anthropic Claude、OpenAI
"""
import logging
import re
import io
import json
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List

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
            "你是一位顶级中文财经内容总编，同时熟悉证券研究、产业分析和大众传播。"
            "你的任务不是把新闻改写一遍，而是把当日信息流重组为真正有洞察、有判断、有传播力的内容。"
            "你尤其擅长："
            "1. 从零散新闻里提炼主线，判断市场真正该关注什么；"
            "2. 用商业分析框架解释事件背后的利益关系、因果链条和行业影响；"
            "3. 用通俗但不浅薄的中文，把复杂财经问题讲给普通投资者听明白；"
            "4. 保持专业克制，不胡编数据，不输出空话套话。"
            "写作气质要求：结构化、洞察感强、语言流畅、解释清楚、有记忆点。"
            "禁止：新闻罗列、口号式总结、没有依据的强预测、泛泛而谈的鸡汤。"
        )

    def _news_snapshot(self, news_items: List[Dict]) -> str:
        lines = []
        for index, news in enumerate(news_items, 1):
            lines.append(
                f"{index}. 标题：{news['title']}\n"
                f"   分类：{news.get('category', '财经')} | 来源：{news['source']} | 时间：{news.get('time', '')}\n"
                f"   链接：{news.get('url') or '无'}"
            )
        return "\n".join(lines)

    def _style_profile(self, style: str) -> str:
        style = (style or "专业").strip()
        profiles = {
            "专业": (
                "行文以专业主播口吻输出，强调关键事实、资金逻辑、产业逻辑和受益受损方。"
                "整体气质偏商业洞察型：先讲结论，再拆原因，再落到普通投资者能理解的影响。"
            ),
            "轻松": (
                "语言更口语化，但不能油腻。要把专业结论翻译成普通观众能秒懂的话，"
                "适当加入类比、提问和提醒，依然保留逻辑深度。"
            ),
            "解读型": (
                "重点强化“这条新闻到底意味着什么”，多做背景补充、因果拆解和风险提示，"
                "减少表面播报，增加判断。"
            ),
            "洞察": (
                "强调主线、反直觉判断和结构化洞察。写法要像成熟财经作者在带读者看门道，"
                "既讲事件，也讲市场定价和预期差。"
            ),
        }
        return profiles.get(style, profiles["专业"])

    def _fallback_editorial_brief(self, news_items: List[Dict], goal: str) -> Dict[str, Any]:
        categories = list(dict.fromkeys(n.get("category", "财经") for n in news_items))
        return {
            "goal": goal,
            "lead_angle": f"今日最值得抓住的主线是{categories[0] if categories else '财经'}方向的预期变化，而不是简单复述新闻。",
            "core_conflicts": [
                "政策预期与市场定价是否错位",
                "短期情绪催化能否转化为中期基本面",
                "投资者该关注主线还是防守风险",
            ],
            "market_pulse": [
                "先判断事件影响的是估值、盈利还是风险偏好",
                "区分主题交易与基本面改善，不混为一谈",
            ],
            "audience_takeaways": [
                "今天最重要的不是新闻数量，而是主线和节奏",
                "真正值得追踪的是后续验证指标，而不是单日情绪",
            ],
            "slide_outline": [
                {"headline": news["title"][:28], "bullets": [f"来源：{news['source']}", f"分类：{news.get('category', '财经')}", "关注其对市场预期的边际影响"]}
                for news in news_items[:8]
            ],
        }

    def _extract_json(self, text: str) -> Dict[str, Any]:
        text = (text or "").strip()
        if not text:
            raise ValueError("empty json text")

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    async def _prepare_editorial_brief(self, news_items: List[Dict], goal: str, style: str) -> Dict[str, Any]:
        prompt = f"""请你扮演财经内容总编，先不要直接写正文，而是基于以下新闻生成一份“编辑部策划brief”。

【生成目标】
{goal}

【写作气质】
{self._style_profile(style)}

【新闻池】
{self._news_snapshot(news_items)}

请输出严格 JSON，不要 Markdown，不要解释，不要多余文本。JSON 结构如下：
{{
  "goal": "一句话写作目标",
  "lead_angle": "最值得展开的总论点，必须有判断，不要空泛",
  "core_conflicts": ["3条矛盾/预期差/市场真正该关心的问题"],
  "market_pulse": ["3条市场脉搏判断：情绪/资金/产业/政策"],
  "audience_takeaways": ["3条普通投资者最该带走的结论"],
  "slide_outline": [
    {{
      "headline": "适合做PPT页标题的一句话",
      "bullets": ["3-4条高信息密度 bullet，每条不超过28字"]
    }}
  ]
}}

要求：
1. 所有内容必须基于给定新闻，不要凭空编数据。
2. 观点要像成熟财经作者做选题会，不要像机器摘要。
3. 如果素材不足，也要明确“该继续追踪什么指标/问题”。
"""
        try:
            content = await self._call_ai(prompt, max_tokens=1800)
            return self._extract_json(content)
        except Exception as e:
            logger.warning("Editorial brief fallback triggered: %s | %s", e, self._error_context())
            return self._fallback_editorial_brief(news_items, goal)

    def _build_stream_script_prompt(
        self,
        news_items: List[Dict],
        editorial_brief: Dict[str, Any],
        duration: int = 30,
        style: str = "专业",
    ) -> str:
        """生成直播稿 prompt，供普通生成和流式生成复用。"""
        news_details = self._news_snapshot(news_items)
        core_conflicts = "\n".join([f"- {item}" for item in editorial_brief.get("core_conflicts", [])])
        market_pulse = "\n".join([f"- {item}" for item in editorial_brief.get("market_pulse", [])])
        takeaways = "\n".join([f"- {item}" for item in editorial_brief.get("audience_takeaways", [])])

        time_per_news = max(3, duration // len(news_items))
        return f"""请写一份真正可上播的财经直播稿，而不是新闻摘要。你要像成熟财经主播在带观众抓主线、讲逻辑、给判断。

【写作目标】
{editorial_brief.get("goal", "输出一份高质量财经直播稿")}

【核心总论点】
{editorial_brief.get("lead_angle", "")}

【今日要闻】共 {len(news_items)} 条
{news_details}

【你必须抓住的矛盾/预期差】
{core_conflicts or '- 没有额外补充'}

【你必须融入的市场脉搏判断】
{market_pulse or '- 没有额外补充'}

【观众最终要带走的结论】
{takeaways or '- 没有额外补充'}

【直播约束】
- 总时长：约 {duration} 分钟
- 每条新闻：约 {time_per_news} 分钟
- 风格：{style}
- 写作气质：{self._style_profile(style)}

【脚本要求】
1. 开场必须先给“今晚最重要的一句话判断”，再带出为什么。
2. 每条新闻不能只复述，必须包含：
   - 事实提炼：真正发生了什么
   - 背景原因：为什么现在发生
   - 市场影响：影响哪类资产/行业/公司
   - 观众视角：普通投资者该怎么理解
3. 每条新闻都尽量给一个“别被表象带偏”的提醒。
4. 结尾必须总结主线、风险点、明日验证指标。

【质量底线】
- 不要说空话，例如“值得持续关注”“影响深远”而不解释。
- 不要写成公文或研报黑话堆砌。
- 不要编造具体数字、机构观点或未给出的公司数据。
- 要有镜头感、主播感，但依然专业。

【输出格式】
【开场判断】
...

【主线一：...】
...

【主线二：...】
...

【逐条展开】
【新闻1】...
【新闻2】...

【收尾总结】
...

【明日关注】
- ...
- ...
- ...
"""
    async def generate_stream_script(
        self,
        news_items: List[Dict],
        duration: int = 30,
        style: str = "专业"
    ) -> str:
        """生成直播稿（目标1500-2000字）"""
        editorial_brief = await self._prepare_editorial_brief(
            news_items,
            goal="输出一份适合直播口播、判断明确、能帮观众抓主线的财经直播稿",
            style=style,
        )
        prompt = self._build_stream_script_prompt(
            news_items,
            editorial_brief=editorial_brief,
            duration=duration,
            style=style,
        )

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
        editorial_brief = await self._prepare_editorial_brief(
            news_items,
            goal="输出一份适合直播口播、判断明确、能帮观众抓主线的财经直播稿",
            style=style,
        )
        prompt = self._build_stream_script_prompt(
            news_items,
            editorial_brief=editorial_brief,
            duration=duration,
            style=style,
        )

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

        editorial_brief = await self._prepare_editorial_brief(
            news_items,
            goal="输出一份适合晨会/直播前准备的财经简报PPT大纲",
            style=style,
        )
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
        add_textbox(
            slide,
            f"{editorial_brief.get('lead_angle', f'共 {len(news_items)} 条精选财经资讯')}  |  {date_str}",
            Inches(1),
            Inches(3.9),
            Inches(11.3),
            Inches(0.8),
            font_size=18,
            color=RGBColor(0xA0, 0xAE, 0xC0),
            align=PP_ALIGN.CENTER,
        )

        slide = prs.slides.add_slide(layout)
        add_bg(slide, white)
        add_textbox(slide, "📋 目录", Inches(0.8), Inches(0.3), Inches(11), Inches(0.8), font_size=28, bold=True, color=blue)
        line = slide.shapes.add_shape(rectangle, Inches(0.8), Inches(1.2), Inches(11.7), Emu(30000))
        line.fill.solid()
        line.fill.fore_color.rgb = blue
        line.line.fill.background()

        slide_outline = editorial_brief.get("slide_outline", [])
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

            outline = slide_outline[idx] if idx < len(slide_outline) else {}
            bullets = outline.get("bullets") or [
                f"事件性质：{news.get('category', '财经')}方向的新变化",
                f"市场含义：关注{news['source']}后续是否带来预期修正",
                "跟踪指标：政策、订单、价格、成交量与资金流",
            ]
            bullet_top = Inches(3.6)
            for bullet in bullets[:4]:
                add_textbox(slide, bullet, Inches(0.8), bullet_top, Inches(11.5), Inches(0.5), font_size=13, color=dark)
                bullet_top += Inches(0.55)

        slide = prs.slides.add_slide(layout)
        add_bg(slide, dark)
        add_textbox(slide, "📊 今日总结", Inches(1), Inches(1.5), Inches(11), Inches(1), font_size=36, bold=True, color=white, align=PP_ALIGN.CENTER)
        categories_seen = list(dict.fromkeys(n.get("category", "财经") for n in news_items))
        summary = (
            f"{editorial_brief.get('lead_angle', '今天最值得关注的是市场主线变化')}\n\n"
            f"本次共收录 {len(news_items)} 条精选财经资讯\n"
            f"涵盖领域：{' · '.join(categories_seen)}\n"
            f"重点带走：{'；'.join(editorial_brief.get('audience_takeaways', [])[:3])}\n"
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
        editorial_brief = await self._prepare_editorial_brief(
            news_items,
            goal="写一篇能发在公众号上的高质量财经文章，不止要讲发生了什么，更要讲为什么重要",
            style="洞察" if title else "解读型",
        )
        prompt = f"""请写一篇成熟财经公众号作者级别的长文。注意：不是把新闻拼接起来，而是围绕一个总论点把当天信息重新组织。

【总论点】
{editorial_brief.get("lead_angle", "")}

【必须回答的关键问题】
{chr(10).join(f"- {item}" for item in editorial_brief.get("core_conflicts", []))}

【普通读者最该带走的结论】
{chr(10).join(f"- {item}" for item in editorial_brief.get("audience_takeaways", []))}

【新闻池】
{self._news_snapshot(news_items)}

【写作要求】
1. 标题必须给 3 个备选，像成熟财经大号标题，而不是标题党。
2. 导语第一段就要回答“今天最该关注什么变化”。
3. 正文按“结论 -> 背景 -> 影响 -> 机会/风险”来展开。
4. 语言要通俗，但不能失去专业判断；要解释专业概念，不要堆黑话。
5. 每个小节都要告诉读者：这件事影响谁、影响多久、后续看什么指标。
6. 可以有判断，但不要编造数据、引述或内幕。
7. 允许适当使用短句和反问，增强阅读感。

【气质要求】
{self._style_profile("洞察")}

【篇幅要求】
- 总字数 2200-3200 字
- 导语 250-350 字
- 每个主体小节 350-500 字
- 结尾必须落到“接下来怎么看”

【输出格式】
===标题选项===
标题1
标题2
标题3

===正文===
# 主标题

**导语**
...

## 一、今天市场真正的重点是什么
...

## 二、这几条新闻背后是一条什么主线
...

## 三、对普通投资者意味着什么
...

## 四、接下来重点看什么
...

**结尾**
...

*本文仅供参考，不构成投资建议*
==="""

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

        editorial_brief = await self._prepare_editorial_brief(
            news_items,
            goal="写一篇有研究框架、有投资视角、能帮助读者建立判断的深度长文",
            style="洞察",
        )
        prompt = f"""请围绕以下核心事件，写一篇真正像“深度研判”而不是“信息汇总”的长文。

【核心事件】
{focus_topic}

【总论点】
{editorial_brief.get("lead_angle", "")}

【你必须拆清楚的问题】
{chr(10).join(f"- {item}" for item in editorial_brief.get("core_conflicts", []))}

【新闻池】
{self._news_snapshot(news_items[:10])}

【写作要求】
1. 先给明确结论，再展开论证。
2. 多做因果链分析：政策/行业/公司/市场预期之间如何传导。
3. 不能虚构机构观点、财务数字、研报数据；没有数据时就明确写“当前还需观察”。
4. 要把复杂问题解释清楚，给普通投资者也能看懂，但专业读者也觉得有框架。
5. 必须同时写机会和风险，不能只唱多或只唱空。
6. 结尾要给出“未来 1-4 周重点验证指标”。

【篇幅】
- 总字数 2800-4200 字
- 每个一级章节都要有实质内容，不可空泛

【输出结构】
# 深度研判：{focus_topic[:40]}

## 一、先说结论
...

## 二、事件到底改变了什么
...

## 三、市场为什么会对它敏感
...

## 四、真正的机会在哪里
...

## 五、最大的风险与误判点
...

## 六、接下来怎么跟踪验证
...

## 七、总结
...
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
                temperature=0.65,
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
                temperature=0.65
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
            temperature=0.65,
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
