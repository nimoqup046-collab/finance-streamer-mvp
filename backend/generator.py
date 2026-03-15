"""
AI内容生成模块 —— Claude Prompt 基底整合版
支持生成：直播稿、公众号文章、深度长文、PPT脚本、PPTX 文件
支持多种AI提供商：智谱、豆包、Anthropic Claude、OpenAI
"""
import io
import json
import logging
import re
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from backend.config import AI_PROVIDER, AI_API_BASE, AI_API_KEY, AI_MODEL

logger = logging.getLogger(__name__)


STREAM_SCRIPT_SYSTEM_PROMPT = """你是一位顶尖中文财经主播。你的优势不是复述新闻，而是把复杂信息讲成观众愿意一直听下去的内容。

【写作目标】
- 把零散新闻串成一条主线
- 讲清楚为什么重要、为什么是现在、接下来会怎样
- 既专业，又让普通投资者听得懂

【表达原则】
- 口语化，但不油腻
- 有态度，但不虚张声势
- 有金句，但不能只靠情绪和口号
- 每一段都要回答“所以呢”

【强制要求】
- 禁止空话：如“建议关注”“影响深远”“需要观察”等
- 不能只讲现象，必须讲因果链
- 能用生活化比喻解释专业概念，但不能牺牲准确性
- 互动提问必须有价值，不是无意义暖场
"""

ARTICLE_SYSTEM_PROMPT = """你是一位顶级中文财经作者，擅长把新闻变成有洞察、有结构、可传播的公众号长文。

【写作目标】
- 不是拼接新闻，而是提炼当天真正的主线和判断
- 让读者看完后，理解深度明显超过普通新闻汇总
- 兼具商业洞察、市场判断和可读性

【表达原则】
- 结构化强，最好有“结论 -> 背景 -> 影响 -> 行动”脉络
- 通俗解释专业问题，但不降低分析质量
- 给明确判断，避免模糊措辞
- 标题必须是观点驱动，不是关键词堆砌

【强制要求】
- 每个小节都要告诉读者：这件事影响谁、影响多久、后续看什么
- 不编造机构观点、财务数字或内幕
- 禁止空话和正确的废话
"""

DEEP_DIVE_SYSTEM_PROMPT = """你是一位顶级策略分析师兼长期主义投资研究者。

【写作目标】
- 输出真正有研究感的深度文章，而不是新闻扩写
- 同时从宏观、产业、资金、情绪多个维度做分析
- 明确区分市场主流看法与你的独到判断

【表达原则】
- 结论前置
- 论证清晰，因果链完整
- 既讲机会，也讲风险
- 给出后续验证指标，而不是停在抽象结论

【强制要求】
- 不允许空泛术语堆砌
- 没有数据支持的地方，要明确写“仍待验证”
- 预测必须带时间窗口与验证指标
"""

PPT_SYSTEM_PROMPT = """你是一位顶级商业演讲顾问，擅长把财经判断转成可以直接用于路演、直播准备、内部汇报的 PPT 脚本。

【写作目标】
- 每一页都有明确观点，而不是素材堆砌
- 屏幕文字极简，讲者备注有说服力
- 让演讲者知道这一页为什么存在、该怎么讲、下一页怎么接

【强制输出结构】
每页必须包含：
- 标题
- 核心论点
- 屏幕要点（3-4条）
- 讲者逐字稿
- 可视化建议
"""

MASTER_SYSTEM_PROMPT = DEEP_DIVE_SYSTEM_PROMPT


class ContentGenerator:
    """内容生成器"""

    def __init__(self):
        self.provider = AI_PROVIDER
        self.model = AI_MODEL
        self.api_key = AI_API_KEY
        self.api_base = AI_API_BASE
        self.client = self._init_client()

    def _init_client(self):
        if self.provider == "anthropic":
            from anthropic import AsyncAnthropic
            return AsyncAnthropic(api_key=self.api_key)

        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=self.api_key, base_url=self.api_base or None)

    def _error_context(self) -> str:
        return (
            f"provider={self.provider}, "
            f"model={self.model}, "
            f"base_url={self.api_base or 'default'}"
        )

    def _system_prompt(self) -> str:
        return (
            "你是一位顶级中文财经内容总编。你的任务不是把新闻改写一遍，而是把当日信息流"
            "重组为真正有洞察、有判断、有传播力的内容。你擅长从新闻中提炼主线、用商业"
            "分析框架解释因果，并用通俗但不浅薄的中文讲清复杂问题。"
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
            "专业": "强调事实、结构和专业判断，像成熟财经主播。",
            "轻松": "语言更口语化，多用类比，但不能牺牲准确性。",
            "解读型": "重点放在‘这意味着什么’，增加背景和因果拆解。",
            "洞察": "突出主线、预期差、反直觉判断和结构化洞察。",
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
                "判断后续该看哪些验证指标，而不是被单日情绪带偏",
            ],
            "audience_takeaways": [
                "今天最重要的不是新闻数量，而是主线和节奏",
                "真正值得追踪的是后续验证指标，而不是单日情绪",
                "区分噪音和主线，别被标题热闹带偏",
            ],
            "slide_outline": [
                {
                    "headline": news["title"][:28],
                    "bullets": [
                        f"来源：{news['source']}",
                        f"分类：{news.get('category', '财经')}",
                        "关注其对市场预期的边际影响",
                    ],
                }
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
        prompt = f"""请你扮演财经内容总编，先不要直接写正文，而是基于以下新闻生成一份“编辑部策划 brief”。

【生成目标】
{goal}

【写作气质】
{self._style_profile(style)}

【新闻池】
{self._news_snapshot(news_items)}

请输出严格 JSON，不要 Markdown，不要解释。结构如下：
{{
  "goal": "一句话写作目标",
  "lead_angle": "最值得展开的总论点，必须有判断",
  "core_conflicts": ["3条关键矛盾/预期差"],
  "market_pulse": ["3条市场脉搏判断"],
  "audience_takeaways": ["3条读者最该带走的结论"],
  "slide_outline": [
    {{
      "headline": "适合做PPT页标题的一句话",
      "bullets": ["3-4条高信息密度 bullet，每条不超过28字"]
    }}
  ]
}}
"""
        try:
            content = await self._call_ai(prompt, max_tokens=1800, system_prompt=self._system_prompt())
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
        news_details = "\n".join([
            f"{i+1}. 【{n.get('category', '财经')}】{n['title']}\n   来源：{n['source']}"
            for i, n in enumerate(news_items)
        ])
        categories = list(dict.fromkeys(n.get("category", "财经") for n in news_items))
        category_str = "、".join(categories[:4])
        time_per_news = max(3, duration // max(len(news_items), 1))
        core_conflicts = "\n".join(f"- {item}" for item in editorial_brief.get("core_conflicts", []))
        market_pulse = "\n".join(f"- {item}" for item in editorial_brief.get("market_pulse", []))
        takeaways = "\n".join(f"- {item}" for item in editorial_brief.get("audience_takeaways", []))

        emotion_arc_section = ""
        if duration >= 60:
            emotion_arc_section = f"""
【情绪弧线设计（{duration}分钟版）】
- 0-5分钟：用最强冲突或反直觉结论抓住观众
- 5-15分钟：给出第一个高价值“原来如此”时刻
- 15-{duration//2}分钟：铺设背景、逻辑和资金/产业链解释
- {duration//2}-{duration}分钟：抛出核心判断、风险点和明日验证指标
"""

        return f"""【内容任务】
请生成一份真正可上播的财经直播稿，而不是新闻摘要。

【编辑部主线】
{editorial_brief.get('lead_angle', '')}

【你必须抓住的矛盾/预期差】
{core_conflicts or '- 没有额外补充'}

【你必须融入的市场脉搏判断】
{market_pulse or '- 没有额外补充'}

【观众最终要带走的结论】
{takeaways or '- 没有额外补充'}

【今日要闻】共{len(news_items)}条，涉及领域：{category_str}
{news_details}

【直播约束】
- 总时长：约{duration}分钟
- 每条新闻：约{time_per_news}分钟
- 风格：{style}
- 写作气质：{self._style_profile(style)}
{emotion_arc_section}

【结构要求】
1. 开场不要寒暄，第一段必须先给“今晚最重要的一句话判断”。
2. 每条新闻必须包含：发生了什么、为什么是现在、影响谁、接下来怎么判断。
3. 至少加入 1 个反直觉观点、1 个历史类比、3 个生活化比喻。
4. 互动提问必须有信息含量，不是无意义暖场。
5. 结尾必须总结主线、风险点、明日关注指标。
6. 可以加入[互动]、[留人钩子]、[揭晓悬念]、[情绪提示：...]等标记，但不要滥用。

【硬性指标】
- 总字数不少于1800字
- 至少出现5个具体数字
- 禁止空话：建议关注、可能有影响、需要观察、存在不确定性、仅供参考

请直接输出完整直播稿，不要写解释：
"""

    async def generate_stream_script(self, news_items: List[Dict], duration: int = 30, style: str = "专业") -> str:
        editorial_brief = await self._prepare_editorial_brief(
            news_items,
            goal="输出一份适合直播口播、判断明确、能帮观众抓主线的财经直播稿",
            style=style,
        )
        prompt = self._build_stream_script_prompt(news_items, editorial_brief, duration=duration, style=style)
        try:
            response = await self._call_ai(
                prompt,
                max_tokens=5000,
                system_prompt=STREAM_SCRIPT_SYSTEM_PROMPT,
            )
            return self._format_stream_script(response, news_items, duration)
        except Exception as e:
            logger.error("Generation error: %s | %s", e, self._error_context())
            return self._generate_fallback_script(news_items)

    async def stream_stream_script(self, news_items: List[Dict], duration: int = 30, style: str = "专业") -> AsyncIterator[str]:
        editorial_brief = await self._prepare_editorial_brief(
            news_items,
            goal="输出一份适合直播口播、判断明确、能帮观众抓主线的财经直播稿",
            style=style,
        )
        prompt = self._build_stream_script_prompt(news_items, editorial_brief, duration=duration, style=style)
        try:
            async for chunk in self._stream_ai(
                prompt,
                max_tokens=5000,
                system_prompt=STREAM_SCRIPT_SYSTEM_PROMPT,
            ):
                if chunk:
                    yield chunk
        except Exception as e:
            logger.error("Streaming generation error: %s | %s", e, self._error_context())
            fallback = self._generate_fallback_script(news_items)
            for chunk in self._chunk_text(fallback, chunk_size=160):
                yield chunk

    async def generate_article(self, news_items: List[Dict], title: str = "", focus_topic: str = "") -> Dict:
        editorial_brief = await self._prepare_editorial_brief(
            news_items,
            goal="写一篇能发在公众号上的高质量财经文章，不止要讲发生了什么，更要讲为什么重要",
            style="洞察" if title else "解读型",
        )
        preferred_title = f"\n【标题方向偏好】\n{title}\n" if title else ""
        focus_hint = f"\n【重点聚焦】\n{focus_topic}\n" if focus_topic else ""
        prompt = f"""【内容任务】
请写一篇让人读完就想转发的财经公众号长文。
{preferred_title}{focus_hint}
【总论点】
{editorial_brief.get('lead_angle', '')}

【必须回答的关键问题】
{chr(10).join(f'- {item}' for item in editorial_brief.get('core_conflicts', []))}

【普通读者最该带走的结论】
{chr(10).join(f'- {item}' for item in editorial_brief.get('audience_takeaways', []))}

【新闻池】
{self._news_snapshot(news_items)}

【写作要求】
1. 必须提供3个标题备选：数字悬念型 / 反直觉型 / 读者利益型。
2. 开篇不能从“今天市场”或“据报道”开始，要用具体场景、反常识事实或数字切入。
3. 正文按“结论 -> 背景 -> 影响 -> 行动”来展开。
4. 每一节都要写清：是什么、为什么、深层原因、明确判断。
5. 结尾不能是“点赞关注”，而要给可执行动作或明确判断。
6. 不能编造数据、机构观点或内幕。
7. 可以有锋利判断，但必须能自圆其说。

【篇幅】
- 总字数不少于1800字
- 至少6个具体数字
- 至少1处历史类比
- 至少1个反主流判断

【输出格式】
===标题选项===
标题A：[内容]
标题B：[内容]
标题C：[内容]

===正文===
（从这里开始输出完整正文，使用Markdown格式）

*本文内容仅供参考，不构成投资建议。投资有风险，决策需谨慎。*
===
"""
        try:
            response = await self._call_ai(prompt, max_tokens=5000, system_prompt=ARTICLE_SYSTEM_PROMPT)
            return self._format_article(response)
        except Exception as e:
            logger.error("Article generation error: %s | %s", e, self._error_context())
            return self._generate_fallback_article(news_items)

    async def _analyze_news_outline(self, news_items: List[Dict], focus_topic: str, date_str: str) -> str:
        news_details = "\n".join([f"• {n['title']}（{n['source']}）" for n in news_items[:6]])
        analysis_prompt = f"""请对以下财经新闻做内部分析（不写文章，只做分析框架）：

核心事件：{focus_topic}
相关新闻：
{news_details}
分析日期：{date_str}

请按以下结构输出简洁分析框架（不超过600字）：
1. 反共识洞察：主流判断是什么？被低估的一面是什么？
2. 利益流向图：谁受益，谁受损，有哪些意外受益者？
3. 历史镜像：最相似的历史案例 + 关键不同点
4. 二阶影响：列出3个大多数分析忽视的间接影响
5. 核心金句：一句话总结本次事件的本质（≤20字）
6. 6个月预测：一个具体可量化可验证的预测
"""
        try:
            return await self._call_ai(
                analysis_prompt,
                max_tokens=1200,
                system_prompt=DEEP_DIVE_SYSTEM_PROMPT,
            )
        except Exception as e:
            logger.warning("Outline analysis failed, proceeding without: %s", e)
            return ""

    async def generate_deep_dive(self, news_items: List[Dict], focus_topic: str = "") -> str:
        if not focus_topic:
            focus_topic = news_items[0]["title"]

        editorial_brief = await self._prepare_editorial_brief(
            news_items,
            goal="写一篇有研究框架、有投资视角、能帮助读者建立判断的深度长文",
            style="洞察",
        )
        date_str = datetime.now().strftime("%Y年%m月%d日")
        internal_outline = await self._analyze_news_outline(news_items, focus_topic, date_str)
        outline_context = f"\n【预分析框架】\n{internal_outline}\n" if internal_outline else ""
        prompt = f"""【深度研究任务】
你要写的不是新闻汇总，而是一篇能被人截图传播的原创深度分析。

【总论点】
{editorial_brief.get('lead_angle', '')}
{outline_context}
【核心事件】
{focus_topic}

【新闻池】
{self._news_snapshot(news_items[:10])}

【必须拆清楚的问题】
{chr(10).join(f'- {item}' for item in editorial_brief.get('core_conflicts', []))}

【写作结构】
## 一、破题——打破认知
## 二、溯源——这件事为什么走到今天
## 三、深度拆解——从宏观/产业/资金/情绪看问题
## 四、历史镜鉴——上次类似的事怎么演化
## 五、蝴蝶效应——二阶和三阶影响
## 六、情景推演——乐观/中性/悲观三种路径与概率
## 七、先行指标——接下来该盯什么验证
## 八、核心结论——6个月内的可验证预测

【强制要求】
- 总字数不少于3000字
- 至少10个具体数字
- 三种情景必须给出具体概率，且和为100%
- 至少1个反主流判断
- 每章节之间要有桥接句，不要硬切换
- 结尾必须给出6个月内可验证预测
- 禁止空话：建议关注、可能有影响、需要观察、存在不确定性、仅供参考

请直接输出完整深度长文，使用Markdown格式：
"""
        try:
            return await self._call_ai(prompt, max_tokens=7000, system_prompt=DEEP_DIVE_SYSTEM_PROMPT)
        except Exception as e:
            logger.error("Deep dive generation error: %s | %s", e, self._error_context())
            return self._generate_fallback_deep_dive(news_items)

    async def generate_ppt_script(self, news_items: List[Dict], focus_topic: str = "") -> str:
        if not focus_topic:
            focus_topic = news_items[0]["title"]
        editorial_brief = await self._prepare_editorial_brief(
            news_items,
            goal="输出一份适合晨会、直播前准备或路演汇报的财经 PPT 脚本",
            style="洞察",
        )
        news_details = "\n".join([
            f"{i+1}. 【{n.get('category','财经')}】{n['title']}（{n['source']}）"
            for i, n in enumerate(news_items[:6])
        ])
        prompt = f"""【PPT创作任务】
你要生成一套可直接用于财经讲解、路演、直播准备的完整 PPT 脚本。

【核心主题】
{focus_topic}

【总论点】
{editorial_brief.get('lead_angle', '')}

【必须传递给观众的结论】
{chr(10).join(f'- {item}' for item in editorial_brief.get('audience_takeaways', []))}

【素材新闻】
{news_details}

【输出要求】
请按页输出，每页都必须包含以下字段：
- 【第X张 · 页面类型】
- 标题：
- 💡 核心论点：
- 📌 屏幕要点：3-4条
- 🎤 讲者逐字稿：120-220字
- 📊 可视化建议：

【页面建议结构】
1. 封面
2. 结论前置：今天最重要的3个判断
3. 为什么这件事比你想的更重要
4. 打破认知：主流判断哪里错了
5-N. 逐条新闻深析
N+1. 把几条新闻串起来的共同逻辑
N+2. 情景推演
N+3. 行动指南
N+4. 记忆点与先行指标

【硬性要求】
- 每页核心论点必须是观点句，不是描述句
- 屏幕要点保持极简，每条不超过18字
- 口播要像真人在讲，不是官方发言稿
- 至少4页出现具体数字
- 至少1页是反直觉判断
- 禁止空话：建议关注、可能有影响、需要观察、存在不确定性、仅供参考

请直接输出完整PPT脚本：
"""
        try:
            return await self._call_ai(prompt, max_tokens=6500, system_prompt=PPT_SYSTEM_PROMPT)
        except Exception as e:
            logger.error("PPT script generation error: %s | %s", e, self._error_context())
            return self._generate_fallback_ppt_script(news_items, focus_topic)

    async def generate_ppt(self, news_items: List[Dict], title: str = "", style: str = "专业", focus_topic: str = "") -> bytes:
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN
        from pptx.util import Inches, Pt

        ppt_script = await self.generate_ppt_script(news_items, focus_topic=focus_topic or title)
        slides = self._parse_ppt_script(ppt_script)
        if not slides:
            slides = self._fallback_slide_data(news_items, title or focus_topic)

        prs = Presentation()
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)
        layout = prs.slide_layouts[6]

        blue = RGBColor(0x1A, 0x56, 0xDB)
        dark = RGBColor(0x1F, 0x2A, 0x3C)
        white = RGBColor(0xFF, 0xFF, 0xFF)
        gray = RGBColor(0x6B, 0x72, 0x80)

        def add_bg(slide, color):
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = color

        def add_textbox(slide, text, left, top, width, height, font_size=18, bold=False, color=None, align=PP_ALIGN.LEFT):
            tx_box = slide.shapes.add_textbox(left, top, width, height)
            tf = tx_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = align
            run = p.add_run()
            run.text = text
            run.font.size = Pt(font_size)
            run.font.bold = bold
            if color:
                run.font.color.rgb = color
            return tx_box

        cover_title = title or focus_topic or f"财经简报 · {datetime.now().strftime('%Y年%m月%d日')}"
        cover = prs.slides.add_slide(layout)
        add_bg(cover, dark)
        add_textbox(cover, cover_title, Inches(0.9), Inches(1.7), Inches(11.4), Inches(1.5), font_size=32, bold=True, color=white, align=PP_ALIGN.CENTER)
        add_textbox(cover, slides[0].get('core', '今天最重要的判断，先讲结论再讲论证'), Inches(1.1), Inches(3.4), Inches(11.1), Inches(1), font_size=18, color=RGBColor(0xC7, 0xD2, 0xFE), align=PP_ALIGN.CENTER)

        for slide_data in slides:
            slide = prs.slides.add_slide(layout)
            add_bg(slide, white)
            add_textbox(slide, slide_data['title'], Inches(0.7), Inches(0.5), Inches(11.8), Inches(0.8), font_size=24, bold=True, color=dark)
            add_textbox(slide, f"💡 核心论点：{slide_data['core']}", Inches(0.8), Inches(1.4), Inches(11.4), Inches(0.8), font_size=15, bold=True, color=blue)
            add_textbox(slide, "📌 屏幕要点", Inches(0.8), Inches(2.2), Inches(3), Inches(0.4), font_size=13, bold=True, color=blue)
            top = 2.7
            for bullet in slide_data['bullets'][:4]:
                add_textbox(slide, f"• {bullet}", Inches(1.0), Inches(top), Inches(5.4), Inches(0.45), font_size=14, color=dark)
                top += 0.45
            add_textbox(slide, "🎤 讲者备注", Inches(6.4), Inches(2.2), Inches(3), Inches(0.4), font_size=13, bold=True, color=blue)
            add_textbox(slide, slide_data['speaker_notes'], Inches(6.5), Inches(2.7), Inches(5.7), Inches(2.7), font_size=13, color=dark)
            add_textbox(slide, f"📊 可视化建议：{slide_data['visual']}", Inches(0.8), Inches(5.9), Inches(11.2), Inches(0.6), font_size=12, color=gray)

        buf = io.BytesIO()
        prs.save(buf)
        return buf.getvalue()

    def _parse_ppt_script(self, script: str) -> List[Dict[str, Any]]:
        sections = re.split(r"(?=【第\d+张)", script or "")
        slides: List[Dict[str, Any]] = []
        for section in sections:
            section = section.strip()
            if not section.startswith("【第"):
                continue
            title = ""
            core = ""
            bullets: List[str] = []
            speaker_notes = ""
            visual = ""

            title_match = re.search(r"标题[:：]\s*(.+)", section)
            if title_match:
                title = title_match.group(1).strip()
            else:
                header_match = re.search(r"【第\d+张[^】]*】\s*(.+)", section)
                title = header_match.group(1).strip() if header_match else "未命名页"

            core_match = re.search(r"[💡🎯]\s*(?:核心论点|核心信息)[:：]\s*(.+)", section)
            if core_match:
                core = core_match.group(1).strip()

            bullet_match = re.search(r"📌\s*(?:屏幕上的文字要点|屏幕要点|要点)[:：](.*?)(?:🎤|📊|$)", section, re.DOTALL)
            if bullet_match:
                for line in bullet_match.group(1).splitlines():
                    line = re.sub(r"^[\s•·\-]+", "", line).strip()
                    if line:
                        bullets.append(line)

            speaker_match = re.search(r"🎤\s*(?:讲者逐字稿|演讲者口播)[^\n]*\n(.*?)(?:📊|$)", section, re.DOTALL)
            if speaker_match:
                speaker_notes = "\n".join(line.strip() for line in speaker_match.group(1).splitlines() if line.strip())

            visual_match = re.search(r"📊\s*(?:可视化建议|视觉设计建议)[:：]\s*(.+)", section)
            if visual_match:
                visual = visual_match.group(1).strip()

            if title or core or bullets or speaker_notes:
                slides.append({
                    "title": title or "未命名页",
                    "core": core or "这一页的核心是帮助观众抓住真正的主线",
                    "bullets": bullets or ["补充关键事实", "解释深层逻辑", "提示后续验证指标"],
                    "speaker_notes": speaker_notes or "这一页要讲清楚：为什么这件事重要、为什么是现在、接下来要看什么。",
                    "visual": visual or "建议使用对比结构、关键数字放大或时间线布局。",
                })
        return slides

    def _fallback_slide_data(self, news_items: List[Dict], focus_topic: str = "") -> List[Dict[str, Any]]:
        topic = focus_topic or news_items[0]["title"]
        slides = [{
            "title": "今天最重要的3个判断",
            "core": "先讲结论，再讲论证，帮助观众快速抓住主线。",
            "bullets": [
                "市场真正定价的是主线变化",
                "短期情绪不等于中期趋势",
                "接下来要看验证指标",
            ],
            "speaker_notes": "先把答案告诉观众，再逐步解释为什么，避免观众在前3分钟流失。",
            "visual": "建议使用三栏对比布局，突出结论1/2/3。",
        }]
        for news in news_items[:6]:
            slides.append({
                "title": news["title"][:26],
                "core": f"这条新闻真正重要的地方，在于它会改变{news.get('category', '财经')}方向的预期。",
                "bullets": [
                    f"来源：{news['source']}",
                    f"分类：{news.get('category', '财经')}",
                    "看清市场真正关心什么",
                ],
                "speaker_notes": f"这条新闻表面上是{news.get('category', '财经')}事件，真正要讲的是它如何影响预期、情绪和后续验证指标。",
                "visual": "建议采用标题+三条 bullet + 底部备注的简洁结构。",
            })
        slides.append({
            "title": topic[:26],
            "core": "如果只能记住一件事，那就是主线比碎片更重要。",
            "bullets": ["看主线", "看验证", "看风险收益比"],
            "speaker_notes": "收尾时把整场逻辑合成一句能被记住的话，并提醒观众明天开始该看什么。",
            "visual": "建议极简收尾页，核心句居中，验证指标置于下方。",
        })
        return slides

    async def _call_ai(self, prompt: str, max_tokens: int = 4000, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise RuntimeError(f"缺少 {self.provider} 的 API Key")

        sys_prompt = system_prompt or MASTER_SYSTEM_PROMPT

        if self.provider == "anthropic":
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=0.75,
                system=sys_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.75,
        )
        content = response.choices[0].message.content
        return content if content else ""

    async def _stream_ai(self, prompt: str, max_tokens: int = 2000, system_prompt: Optional[str] = None) -> AsyncIterator[str]:
        if not self.api_key:
            raise RuntimeError(f"缺少 {self.provider} 的 API Key")

        sys_prompt = system_prompt or MASTER_SYSTEM_PROMPT

        if self.provider == "anthropic":
            full_text = await self._call_ai(prompt, max_tokens=max_tokens, system_prompt=sys_prompt)
            for chunk in self._chunk_text(full_text):
                yield chunk
            return

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.75,
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

    def _format_stream_script(self, content: str, news_items: List[Dict], duration: int = 30) -> str:
        date_str = datetime.now().strftime("%Y年%m月%d日")
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][datetime.now().weekday()]
        return f"""
╔══════════════════════════════════════════════════════════╗
║  📺 财经深度直播稿                                        ║
║  📅 {date_str} {weekday}                                  ║
║  ⏱ 预计时长：{duration}分钟  📊 共{len(news_items)}条新闻  ║
╚══════════════════════════════════════════════════════════╝

{content}

{'─'*60}
📌 本稿由 AI 深度创作生成，请结合实时盘面和最新数据调整
📊 预计直播时长：{len(news_items) * 4}-{len(news_items) * 6} 分钟
{'─'*60}
"""

    def _format_article(self, content: str) -> Dict:
        titles = []
        if "===标题选项===" in content:
            parts = content.split("===正文===")
            title_section = parts[0].replace("===标题选项===", "").strip()
            raw_titles = [t.strip() for t in title_section.split("\n") if t.strip()]
            for t in raw_titles:
                cleaned = re.sub(r"^标题[A-Ca-c：:]\s*", "", t).strip()
                if cleaned:
                    titles.append(cleaned)
            titles = titles[:3]
            content_body = parts[1] if len(parts) > 1 else content
            content_body = content_body.split("===")[0].strip()
        else:
            title_match = re.search(r'【标题选项】\n(.+?)\n\n', content, re.DOTALL)
            if title_match:
                titles = [t.strip("- 123. ") for t in title_match.group(1).split("\n") if t.strip()]
            content_body = content

        if not titles:
            titles = [f"财经深度解读 {datetime.now().strftime('%m月%d日')}"]

        return {
            "titles": titles,
            "content": content_body.strip(),
            "html": self._markdown_to_html(content_body),
        }

    def _markdown_to_html(self, md: str) -> str:
        html = md
        html = html.replace("===标题选项===", "").replace("===正文===", "").replace("===", "")
        html = re.sub(r"标题[A-Ca-c：:].+?\n", "", html)
        html = re.sub(r'【标题选项】.+?\n\n', '', html, flags=re.DOTALL)
        html = re.sub(r'^# (.+)$', r'<h1 style="font-size:22px;font-weight:bold;margin:20px 0;color:#1a1a1a;">\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2 style="font-size:18px;font-weight:bold;margin:16px 0 8px;color:#1a1a1a;border-left:4px solid #0066cc;padding-left:10px;">\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3 style="font-size:16px;font-weight:bold;margin:12px 0 6px;color:#333;">\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#0066cc;">\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'^[•·▶📍📌✅❌🎯💡❓🟢🟡🔴] (.+)$', r'<li style="margin:6px 0;">\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'^- (.+)$', r'<li style="margin:6px 0;">\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li.+</li>\n?)+', lambda m: f'<ul style="margin:10px 0;padding-left:20px;list-style:disc;">{m.group(0)}</ul>', html)
        paragraphs = html.split("\n\n")
        formatted = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith("<h") and not p.startswith("<ul") and not p.startswith("<li"):
                p = f'<p style="line-height:1.9;margin:15px 0;color:#333;font-size:15px;">{p}</p>'
            formatted.append(p)
        return "\n".join(formatted)

    def _generate_fallback_script(self, news_items: List[Dict]) -> str:
        date_str = datetime.now().strftime("%Y年%m月%d日")
        script = f"""
【开场判断】
今天最重要的，不是某一条新闻本身，而是市场正在重新定价的方向。今天是{date_str}，下面我们把真正值得看的主线拆开来说。

"""
        for i, news in enumerate(news_items, 1):
            script += f"""
【新闻{i}】{news['title']}

【深度解读】
这条消息来自{news['source']}，属于{news.get('category', '财经')}。表面上它是一条单点新闻，但更值得关注的是它会如何影响预期、情绪和后续验证指标。

[互动] 如果你也在盯这个方向，在评论区扣1

"""
        script += """
【收尾总结】
把今天这些消息合在一起看，真正该盯的是主线，而不是单条标题带来的短期情绪。

【明日关注】
- 资金流向是否持续
- 关键政策或数据是否跟进验证
- 相关板块是否从情绪走向业绩与基本面
"""
        return script

    def _generate_fallback_article(self, news_items: List[Dict]) -> Dict:
        date_str = datetime.now().strftime("%m月%d日")
        titles = [
            f"今天这{len(news_items)}件事，比大多数人想得更重要",
            f"一个被忽视的信号：{news_items[0]['title'][:18]}背后的逻辑",
            f"{date_str}财经深度：看懂这几件事，看懂接下来的市场",
        ]
        content = f"# {titles[0]}\n\n"
        content += f"**{datetime.now().strftime('%Y年%m月%d日')} | 深度解读**\n\n"
        content += f"今天发生了{len(news_items)}件值得认真对待的事。把它们放在一起看，比逐条看热闹更重要。\n\n"
        for news in news_items:
            content += f"## {news['title']}\n\n"
            content += f"**来源**：{news['source']} | **分类**：{news.get('category', '财经')}\n\n"
            content += "这条新闻的真正价值，不只在于表面事实，而在于它如何改变市场预期、资金定价和后续验证路径。\n\n"
        content += "## 核心判断\n\n把今天这些消息放在一起看，市场真正变化的是主线和预期差，而不只是热闹本身。\n\n"
        content += "*本文内容仅供参考，不构成投资建议。*\n"
        return {"titles": titles, "content": content, "html": self._markdown_to_html(content)}

    def _generate_fallback_deep_dive(self, news_items: List[Dict]) -> str:
        topic = news_items[0]['title']
        date_str = datetime.now().strftime("%Y年%m月%d日")
        return f"""# 深度分析：{topic}

**{date_str} | 原创深度研究**

## 一、先说结论
市场最容易被高估的，是短期情绪；最容易被低估的，是主线变化的持续性。

## 二、事件到底改变了什么
这件事改变的不只是表面信息，而是市场对后续政策、行业景气度和资金偏好的预期。

## 三、市场为什么会对它敏感
因为它连接的是预期差，而不是静态事实。

## 四、真正的机会在哪里
机会不在标题最热的地方，而在后续更容易被验证的方向。

## 五、最大的风险与误判点
最大的误判，是把一次性情绪催化当成长期趋势。

## 六、接下来怎么跟踪验证
重点看政策、资金流、订单、价格和盈利验证节奏。

## 七、总结
如果6个月后回头看，今天更可能是一个预期重定价的起点，而不是单日噪音。
"""

    def _generate_fallback_ppt_script(self, news_items: List[Dict], focus_topic: str = "") -> str:
        topic = focus_topic or news_items[0]['title']
        return f"""【第1张 · 封面】
标题：{topic[:20]}——它比你想的更重要
💡 核心论点：今天真正要讲的是主线，而不是碎片新闻
📌 屏幕要点：
• 先看结论
• 再看论证
• 最后看行动
🎤 讲者逐字稿：今天我们不一条条念新闻，而是把这些消息重新放回同一张地图里，看看到底哪条线最值得你花时间。
📊 可视化建议：深色背景 + 大标题 + 一句判断。
"""


generator = ContentGenerator()
