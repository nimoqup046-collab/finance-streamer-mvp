"""
AI内容生成模块 —— 深度创作版
融合刘润商业洞察力 × 小Lin说叙事魅力 × 顶级分析师专业深度
支持生成：直播稿、公众号文章、深度长文、PPT脚本
支持多种AI提供商：豆包、Anthropic Claude、OpenAI
"""
import logging
import re
from datetime import datetime
from typing import List, Dict

from backend.config import AI_PROVIDER, AI_API_KEY, AI_API_BASE, AI_MODEL

logger = logging.getLogger(__name__)


# ============================================================
# 核心人格设定：融合三重顶级能力的财经深度创作大师
# ============================================================
MASTER_SYSTEM_PROMPT = """你是「财经深度创作大师」，汇聚三重顶级能力，创作风格融合刘润的商业洞察力与小Lin说的叙事魅力：

【身份一：商业洞察者（刘润式）】
- 用第一性原理穿透财经现象，找到底层商业逻辑，而不是停留在表面描述
- 擅长"反直觉"分析：大多数人认为A，真相却是B，你要找到那个B
- 每个结论必须有数据支撑，每个数据必须有洞察解读，数字不是装饰品
- 擅长三层递进框架：表象→本质→趋势，让读者/观众豁然开朗
- 核心追问：这件事的商业本质是什么？谁真正受益，谁真正受损？

【身份二：叙事高手（小Lin说式）】
- 永远从一个具体的人、公司、数字或场景切入，绝不从"今天市场"或定义开始
- 用生动类比将复杂概念可视化——"这就好比..."让普通人秒懂专业知识
- 善于制造"转折时刻"：铺垫→打破认知→建立新认知，保持读者/观众全程专注
- 每一段都要回答"所以呢？这跟我有什么关系？"——让读者感到与自己相关
- 核心追问：普通投资者看完这篇能学到什么？他/她的第一反应是什么？

【身份三：预判专家（分析师式）】
- 不只报道"发生了什么"，更要预判"会发生什么"，有时间节点和量化预期
- 明确区分"市场主流观点"与"我的独到判断"，勇于与主流唱反调
- 提供可验证的先行指标：告诉读者"如果看到X信号，就意味着Y正在发生"
- 核心追问：6个月后回头看这件事，它的历史意义会是什么？

【写作铁律——必须遵守】
1. 开篇必须有"钩子"：震惊数字、反直觉事实、或生动场景，前3句话决定是否继续看
2. 每个论点必须追问"为什么"：不停留在描述，深挖原因，至少挖两层
3. 必须有"所以呢"：明确告诉读者/观众这件事如何影响他们的钱包和决策
4. 结尾必须留下"记忆点"：一句让人能转发的核心判断，态度鲜明
5. 具体胜于抽象：说"降了50个基点，影响3000万小微企业"，不说"有所下调，影响较大"
6. 有勇气表态：给出明确的看多/看空/等待建议，禁止用"可能""或许""需要观察"敷衍

【绝对禁止词汇】
❌ 建议关注 ❌ 可能有影响 ❌ 需要观察 ❌ 存在不确定性 ❌ 仅供参考 ❌ 有一定影响
❌ 或将 ❌ 不排除 ❌ 值得关注 ❌ 影响几何 ❌ 仁者见仁"""


class ContentGenerator:
    """内容生成器 —— 深度创作版"""

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

    async def generate_stream_script(
        self,
        news_items: List[Dict],
        duration: int = 30,
        style: str = "专业"
    ) -> str:
        """生成直播稿 —— 刘润×小Lin说融合风格（目标2000+字）"""
        news_details = "\n".join([
            f"{i+1}. 【{n.get('category', '财经')}】{n['title']}\n   来源：{n['source']}"
            for i, n in enumerate(news_items)
        ])

        date_str = datetime.now().strftime("%Y年%m月%d日")
        weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now().weekday()]

        # 找出新闻之间的隐含联系，作为节目主线
        categories = list(set(n.get('category', '财经') for n in news_items))
        category_str = "、".join(categories[:3])

        prompt = f"""【今日直播场景】
今天是{date_str}{weekday}，你是拥有百万粉丝的顶级财经主播。
你的粉丝关注你，因为你从不说废话，每次开播都能让他们学到别处学不到的东西。

【今日要解读的{len(news_items)}条新闻】
{news_details}

【直播时长】约{duration}分钟
【今日涉及领域】{category_str}

---

请生成一份让粉丝"舍不得离开直播间"的完整直播稿。不是照本宣科，是真正的内容创作。

═══════════════════════════════════════
【一、震撼开场】（150-200字）
═══════════════════════════════════════

开场三要素（缺一不可）：

▶ 第1句（钩子句）：用一个惊人的数字、反直觉的事实、或一个让人意外的问题开场。
  绝对禁止用"大家好"、"欢迎收看"等废话开头。
  示例风格："你知道吗，今天有一件事，很多人觉得是坏消息，但我看完之后，发现它可能是今年最被低估的机会。"

▶ 第2-3句（放大器）：扩展这个钩子，用具体数字或场景放大冲击感，让观众感到"这跟我的钱包有关"

▶ 第4-6句（主线预告）：用一句话找到今天{len(news_items)}条新闻之间的隐藏逻辑联系（不是简单罗列，是找到它们共同指向的一个更大趋势或问题），然后用悬念句结束开场："接下来，我要告诉你一个大多数人还没有意识到的事情..."

═══════════════════════════════════════
【二、核心内容解读】（每条新闻280-350字）
═══════════════════════════════════════

每条新闻按以下结构展开：

🎯 【破题一句话】（一句话精华，说清楚这件事为什么重要，不超过30字）

📖 【场景切入】（2-3句，用一个具体的人、公司、或生活场景引出新闻，不直接说新闻内容）
  示例："假设你是一个做外贸的老板，今天早上刷手机，突然看到这条消息..."

🔍 【三层剥皮】
  第一层：发生了什么？（事实陈述，必须包含至少1个具体数字）
  第二层：为什么会发生？（挖掘2个底层原因，至少1个是大多数人没想到的）
  第三层：接下来会怎样？（给出明确的趋势判断，有时间节点，如"未来3个月内..."）

💡 【反直觉洞察】（用以下句式引出独特判断）
  "但你可能没想到的是..." 或
  "大多数人的直觉是X，但我的判断是Y，原因是..."

❓ 【高价值互动】（不是"大家觉得呢"，而是一个有答案的思考题）
  示例："你们知道上次出现同样信号是哪年吗？那次之后的3个月里，相关板块涨了还是跌了？答案你们猜猜，我等一下揭晓。"
  （如果上面提问了悬念，在后续内容里要揭晓答案）

═══════════════════════════════════════
【三、金句收尾】（150-200字）
═══════════════════════════════════════

▶ 首尾呼应：回到开场的那个钩子，给出答案或更深一层的解读

▶ 今日三条铁律（用序号列出，每条一句话，必须是态度鲜明的判断，不是描述）：
  ① [具体判断，有立场]
  ② [具体判断，有立场]
  ③ [具体判断，有立场]

▶ 明天最重要的1件事（只1件，越具体越好，要有可操作性）：
  "明天，我建议你重点关注一件事：[具体事项+具体时间+你为什么这么判断]"

▶ 今日金句（你的个人标志性判断，态度鲜明，让粉丝记住并转发）：
  示例风格："记住今天我说的这句话：[某具体预判]。如果我判断错了，欢迎来怼我；如果判断对了，记得来告诉我一声。"

---

【硬性指标——不达到不算完成】
✅ 总字数不少于1800字
✅ 全文出现至少5个具体数字（百分比/金额/时间/数量，真实合理）
✅ 至少1个历史类比（"上次类似情况发生在X年，当时的结果是..."）
✅ 至少1个反主流判断（与市场主流观点相反的独到见解）
✅ 互动提问必须有悬念感，并在后文揭晓答案
✅ 语言口语化，有个人情感，像真人在和朋友讲话，不是在读新闻稿
✅ 禁止词汇：建议关注、可能有影响、需要观察、存在不确定性、仅供参考

请直接输出完整直播稿内容，不要有任何前言说明：
"""

        try:
            response = await self._call_ai(prompt, max_tokens=5000)
            return self._format_stream_script(response, news_items, duration)
        except Exception as e:
            logger.error("Generation error: %s | %s", e, self._error_context())
            return self._generate_fallback_script(news_items)

    async def generate_article(
        self,
        news_items: List[Dict],
        title: str = ""
    ) -> Dict:
        """生成公众号文章 —— 让人看完想转发的深度好文（目标1800-2500字）"""
        news_details = "\n".join([
            f"• {n['title']}（来源：{n['source']}，分类：{n.get('category','财经')}）"
            for n in news_items
        ])

        date_str = datetime.now().strftime("%Y年%m月%d日")
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][datetime.now().weekday()]

        prompt = f"""【写作任务】
你要写一篇让人读完就想转发的公众号文章。
衡量标准：读者读完后，对某件事的理解比读10篇普通新闻还深，且觉得"这个我得让朋友看看"。

【今日素材】共{len(news_items)}条新闻
{news_details}

【写作日期】{date_str} {weekday}

---

═══════════════════════════════════════
【第一步：三个标题候选】
═══════════════════════════════════════

三个标题分别运用不同的心理钩子：

标题A（数字+悬念型）：
  公式：[具体数字] + [让人意外的结论]
  示例风格："一个数字，看懂今天A股的真实信号" / "这3个信号同时出现，上次是2019年"
  禁止模式：❌"重磅！降准！"❌"今日要闻汇总"

标题B（反直觉型）：
  公式：打破读者的预期认知
  示例风格："所有人都在讨论降息，但真正的机会根本不在这里" / "你以为是利空，其实是反转信号"
  要求：标题本身就是一个观点，读者同意或不同意都想点进来看

标题C（读者利益型）：
  公式：直接告诉读者"看完这篇，你能得到什么"
  示例风格："今天这3件事，决定你接下来3个月怎么配置" / "如果你还持有X类资产，今天必须看这篇"

═══════════════════════════════════════
【第二步：正文内容】（不少于1800字）
═══════════════════════════════════════

**开篇（150-200字）——本文最重要的部分，决定读者是否继续读**

绝对禁止从"今天市场..."或"据报道..."开始。

要从一个具体的、有画面感的细节切入：
- 可以是一个真实或假设的场景："2015年那个夏天，不少投资者..."
- 可以是一个令人意外的数字："你可能不知道，在过去12个月里..."
- 可以是一个反常识的事实："大多数人认为这是坏消息。但你仔细看完这篇，可能会改变想法。"

开篇结尾用一句话，自然衔接到今天要讲的内容，形成流畅的过渡。

---

**主体内容（每条新闻各自成节，每节300-400字）**

每节结构（必须有以下四个要素）：

① 小标题（能独立成一条微博的那种，有观点有信息量）
  好标题示例："降息50基点：表面是礼包，本质是压力测试"
  差标题示例："央行宣布降息50基点"（没有观点）

② 是什么（1-2句，用具体数字说清楚事实）

③ 为什么（挖掘2-3个深层原因，至少1个是读者没想到的角度）
  用"但鲜为人知的是..."或"背后还有一个被忽视的原因..."引出深层逻辑

④ 然后呢（最重要！明确告诉读者这件事对他们意味着什么）
  给出明确判断：看涨/看跌/等待，或具体建议
  禁止用：可能/或许/或将/不排除/仁者见仁
  要用：我的判断是.../从历史数据来看.../这意味着...

---

**结尾（150-200字）**

不要写："希望对大家有所帮助，欢迎点赞关注。"
不要写："以上仅供参考，投资有风险。"

要写：
1. 用一句话总结今天{len(news_items)}条新闻共同指向的那个更大的趋势或判断
2. 给读者一个今天就能做的具体动作（不是"多加关注"，而是"今天可以查一查..."或"如果你的仓位里有...，可以考虑..."）
3. 结尾金句：你对这个市场/这个趋势的核心判断（态度鲜明，让人记住）

---

【输出格式——严格遵守】

===标题选项===
标题A：[内容]
标题B：[内容]
标题C：[内容]

===正文===
（从这里开始输出完整正文，使用Markdown格式，标题用##，加粗用**）

（正文最后加一行）
*本文内容仅供参考，不构成投资建议。投资有风险，决策需谨慎。*
===

【硬性指标】
✅ 正文总字数不少于1800字
✅ 全文至少出现6个具体数字（真实合理，涉及金额/百分比/时间/数量）
✅ 至少1处历史类比（"上次这种情况是X年X月，当时..."）
✅ 至少1个反主流判断（与市场主流认知不同的独到看法，并给出理由）
✅ 每节结尾必须有明确的倾向性判断，禁止模棱两可
✅ 绝对禁止词：建议关注、可能有影响、需要观察、存在不确定性
"""

        try:
            response = await self._call_ai(prompt, max_tokens=5000)
            return self._format_article(response)
        except Exception as e:
            logger.error("Article generation error: %s | %s", e, self._error_context())
            return self._generate_fallback_article(news_items)

    async def generate_deep_dive(
        self,
        news_items: List[Dict],
        focus_topic: str = ""
    ) -> str:
        """生成深度长文 —— 能被人截图传播的原创深度分析（目标3000+字）"""
        if not focus_topic:
            focus_topic = news_items[0]["title"]

        news_details = "\n".join([
            f"• {n['title']}（{n['source']}）"
            for n in news_items[:6]
        ])

        date_str = datetime.now().strftime("%Y年%m月%d日")

        prompt = f"""【深度研究任务】
你要写的不是"新闻汇总"，而是一篇能被人截图传播的原创深度分析。
衡量标准：读者读完后，对这件事的理解比读完20篇普通新闻还深，且能用3句话向朋友解释清楚。

【核心事件】
{focus_topic}

【相关素材】
{news_details}

【写作日期】{date_str}

---

═══════════════════════════════════════
深度分析框架（按以下维度展开，总字数不少于3000字）
═══════════════════════════════════════

【一、破题——打破认知（200-300字）】

先说结论，再说论证（这叫结论前置，是最高效的写法）。

▶ 第一句话就是本文最核心的判断：[一句话，态度鲜明，不含任何模糊词汇]

▶ 打破认知：绝大多数人看到这件事的第一反应是什么？他们的直觉为什么是错的（或者为什么只看到了一半）？

▶ 本文要解决的核心问题：把这篇文章最值得读的理由，用2-3句话说清楚

【二、溯源——这件事是怎么走到今天这一步的（400-500字）】

▶ 追溯时间线：从6个月前（或更早）开始，梳理导致今天这件事发生的因果链
  格式示例：
  [时间节点1]：[发生了什么，为什么重要]
  [时间节点2]：[发生了什么，为前一件事的结果或推进]
  [时间节点3]：[今天的事件，在这条因果链中的位置]

▶ 找到大多数报道没有提到的背景因素（至少1个）：为什么现在发生，不是早一年、晚一年？

【三、深度拆解——三个维度全面分析（600-700字）】

维度一：对不同参与者的差异化影响（普通散户 vs 机构 vs 外资 vs 产业链上下游）
  - 谁是这件事最大的受益者？（具体说明，带理由）
  - 谁是最大的受损者？（具体说明，带理由）
  - 有没有"意外受益者"——表面上和这件事无关，但实际上会间接受益的行业/群体？

维度二：时间维度的演化路径（短期/中期/长期分开分析）
  - 短期（1-3个月）：市场最可能的反应是什么？为什么？
  - 中期（3-12个月）：更深层的影响会在哪里显现？
  - 长期（1-3年）：这件事在历史上会占什么位置？

维度三：市场的定价是否充分？
  - 目前市场的主流解读是什么？
  - 哪里被高估（市场过于乐观）？哪里被低估（市场还没反映到）？
  - 如果市场错了，最可能错在哪里？

【四、历史镜鉴——上次类似的事是怎么演化的（400-500字）】

▶ 找到最近的一次高度类似事件（必须具体到年月，具体到事件名称）
  "最近一次类似的情况发生在[X年X月]，当时的背景是..."

▶ 相同之处（让人觉得历史在重演的地方）

▶ 不同之处（为什么今天的情况不能完全复制历史经验）

▶ 从历史案例中，能得出什么可操作的结论？（至少1条）

【五、蝴蝶效应——这件事的二阶、三阶影响（400-500字）】

一阶影响：大家都知道，不详细展开
二阶影响（这才是重点）：因为A发生了→所以B会发生→因此C也会间接受影响
  - 点出2-3个市场目前还没有充分反映的间接影响
  - "意外受益者"清单：表面上无关，实际上会从中获益的行业/公司类型
  - "意外受损者"清单：表面上无关，实际上会被间接拖累的行业/公司类型

【六、情景推演——三种可能的未来（400-500字）】

不能只给一个预测，要给出三种情景：

🟢 乐观情景（概率估计：X%）
  触发条件：[具体说明，什么事情发生了，才会走向这个情景]
  演化路径：[如果是这个情景，会怎么发展]
  对应策略：[投资者应该怎么做]

🟡 中性情景（概率估计：X%）
  触发条件：[具体说明]
  演化路径：[具体说明]
  对应策略：[具体说明]

🔴 悲观情景（概率估计：X%）
  触发条件：[具体说明]
  演化路径：[具体说明]
  对应策略：[具体说明]

（三种情景的概率加起来等于100%，且必须给出具体数字，不能说"较高/较低"）

【七、先行指标——告诉读者盯住什么（300-400字）】

给读者3个"金丝雀指标"——如果这些信号出现，就说明某种趋势开始验证：

📍 指标一：[具体看什么数据/事件] + [出现什么变化代表什么含义] + [大概在什么时间节点能观察到]
📍 指标二：[同上]
📍 指标三：[同上]

这部分是整篇文章最有实用价值的地方，要具体到让读者明天就能去查。

【八、核心结论——这篇文章的记忆点（200-300字）】

▶ 一句话结论：如果只能记住这篇文章的一件事，那就是——[态度鲜明，有时间节点的核心判断]

▶ 你的立场：看多/看空/中性？理由是什么？（必须明确表态）

▶ 6个月后的具体预测：[具体事件] 在 [具体时间] 之前，[具体的可量化结果]
  这个预测是可以被验证的，6个月后你可以回来对照。

▶ 结尾金句：一句让人印象深刻的话，总结你对这件事最独特的判断

---

【硬性指标——不达标不算完成】
✅ 总字数不少于3000字
✅ 至少出现10个具体数字（真实合理的历史数据、预测数字、对比数字）
✅ 至少1个完整的历史案例（具体到年份、事件名称、当时的结果）
✅ 三种情景推演必须都有具体概率数字
✅ 先行指标必须具体到可操作（不是"关注政策面"，而是"如果看到X数据超过Y，就说明..."）
✅ 结尾必须有明确的6个月预测，可被验证
✅ 全文必须有至少1个反主流判断（与市场主流认知不同，并给出理由）
✅ 绝对禁止：建议关注、可能有影响、需要观察、存在不确定性、仅供参考、或将、不排除

请直接输出完整深度长文，使用Markdown格式：
"""

        try:
            return await self._call_ai(prompt, max_tokens=7000)
        except Exception as e:
            print(f"Deep dive generation error: {e}")
            return self._generate_fallback_deep_dive(news_items)

    async def generate_ppt(
        self,
        news_items: List[Dict],
        focus_topic: str = ""
    ) -> str:
        """生成PPT脚本 —— 能"震住场子"的财经演讲幻灯片脚本"""
        if not focus_topic:
            focus_topic = news_items[0]["title"]

        news_details = "\n".join([
            f"{i+1}. 【{n.get('category','财经')}】{n['title']}（{n['source']}）"
            for i, n in enumerate(news_items[:6])
        ])

        date_str = datetime.now().strftime("%Y年%m月%d日")
        n_news = min(len(news_items), 5)
        slide_news_end = 4 + n_news
        slide_connect = slide_news_end + 1
        slide_scenario = slide_connect + 1
        slide_action = slide_scenario + 1
        slide_end = slide_action + 1

        prompt = f"""【PPT创作任务】
你要生成一套"震住场子"的财经演讲PPT完整脚本。
使用场景：投资者路演、内部汇报、财经自媒体视频讲解。
衡量标准：听众在PPT结束时，觉得"这人真懂市场，我要把他的观点分享出去"。

【核心主题】
{focus_topic}

【素材新闻】（共{len(news_items)}条）
{news_details}

【演讲日期】{date_str}

---

每张PPT按以下固定格式输出：

┌─────────────────────────────────────────┐
│ 【第X张 · 页面类型】                     │
│ 标题：[幻灯片标题]                       │
├─────────────────────────────────────────┤
│ 🎯 核心信息（≤20字，有观点的判断句）     │
│                                         │
│ 📌 要点：                               │
│   • [要点1，≤15字]                      │
│   • [要点2，≤15字]                      │
│   • [要点3，≤15字]                      │
│                                         │
│ 🎤 演讲者口播（100-150字，口语化）       │
│                                         │
│ 📊 视觉设计建议（具体说明用什么图/数据）  │
└─────────────────────────────────────────┘

---

请按以下顺序生成完整PPT脚本（共{slide_end}张）：

【第1张 · 封面】
- 主标题：不超过20字，要有冲击力，像一个让人停下来的悬念
- 副标题：一句话说清楚"今天要回答一个什么问题"
- 演讲者口播（开场30秒钩子）：
  从一个让人意外的数字或反常识事实开始，引出今天的主题。
  禁止从"大家好"开始。
- 视觉建议：深色背景+大字体数字，营造庄重感

【第2张 · 结论前置】
- 今天最重要的3个结论先放出来（先说答案，再说论证）
- 每条结论都是一个有观点的判断，不是描述
- 演讲者口播：解释为什么先说结论（"很多人喜欢卖关子，但我觉得时间宝贵..."）
- 视觉建议：三个结论用1/2/3序号突出，每条旁边有一个小图标

【第3张 · 问题设定一：为什么这件事值得今天讨论？】
- 用1-2个数字量化这件事的规模/重要性
- 演讲者口播：制造紧迫感——"如果今天这件事你没搞清楚，接下来X个月你可能会后悔"
- 视觉建议：大数字配对比色，凸显量级

【第4张 · 问题设定二：大多数人的误解在哪里？】
- 展示"主流认知 vs 真实情况"的对比
- 这是全程最重要的认知冲突设置
- 演讲者口播：用"大多数人认为...但实际上..."结构，制造认知颠覆感
- 视觉建议：左右对比布局，左边"误解"（红色×），右边"真相"（绿色✓）

{self._generate_ppt_news_slides(news_items[:n_news], start=5)}

【第{slide_connect}张 · 连接与洞察：这些事件的底层逻辑是什么？】
- 这是整套PPT的高光时刻：把前面所有新闻串联起来，找到它们共同指向的一个更大的趋势或结构性变化
- 核心信息必须是一个让人"哇"的连接发现
- 演讲者口播：
  "你们有没有发现，今天讲的这{len(news_items)}件事，表面上看毫不相关，但如果你把它们放在一起看..."
  然后说出那个连接判断，这是今天演讲最有价值的部分
- 视觉建议：用思维导图或连接线，把各事件连向中心判断

【第{slide_scenario}张 · 情景推演：接下来会怎样？】
- 三种情景（乐观/中性/悲观），每种给出具体概率估计
- 每种情景的触发条件（什么事情发生了，才会走向这个情景）
- 演讲者口播：
  "我不喜欢只给一个预测，因为未来是有不确定性的。所以我给三个情景，三种概率。"
  然后说出你最看好的情景和理由
- 视觉建议：三列布局，用绿黄红配色，每列一个情景

【第{slide_action}张 · 行动指南：你现在应该做什么？】
- 针对三类投资者（保守型/稳健型/积极型）各给1条具体、可执行的建议
- 建议必须具体到可以明天就执行，不能说"保持关注"
- 还要给出3个"先行指标"——如果这些信号出现，意味着需要重新判断
- 演讲者口播：
  "好，讲了这么多分析，最后说点对大家真正有用的..."
  然后给出直接、具体的行动建议，不留废话
- 视觉建议：三行对应三类投资者，每行一条具体建议，旁边有图标

【第{slide_end}张 · 记忆点收尾】
- 今天整场演讲的最核心判断，一句话，让听众记住带走
- 3个"先行指标"：告诉听众回去后应该关注什么具体信号
- 你的6个月预测：有时间节点、可量化、可被验证
- 演讲者口播：
  制造"终局感"——"如果今天你只能记住一件事，那就是..."
  然后说出那句金句，语气坚定，有个人风格
- 视觉建议：大字金句居中，配上演讲者签名式的设计元素

---

【硬性要求】
✅ 每张PPT的"核心信息"必须是有观点的判断句，不是描述句
✅ 演讲者口播必须口语化，像真人在说话，不是官方发言稿
✅ 至少4张PPT有具体的数字数据
✅ 至少1张PPT有反直觉判断（挑战主流认知）
✅ 视觉建议必须具体（"2015年vs2024年折线对比图"，不是"建议用图表"）
✅ 行动建议必须可执行（"查一下你持仓中X类资产的比例"，不是"保持关注"）
✅ 禁止词汇：建议关注、可能有影响、需要观察、存在不确定性、仅供参考

请直接输出完整PPT脚本：
"""

        try:
            return await self._call_ai(prompt, max_tokens=6000)
        except Exception as e:
            logger.error("PPT generation error: %s | %s", e, self._error_context())
            return self._generate_fallback_ppt(news_items, focus_topic)

    def _generate_ppt_news_slides(self, news_items: List[Dict], start: int = 5) -> str:
        """生成新闻解析幻灯片的提示词片段"""
        slides = []
        for i, news in enumerate(news_items):
            slide_num = start + i
            slides.append(f"""【第{slide_num}张 · 新闻深析{i+1}：{news['title'][:20]}...】
- 核心信息：用一句话说清楚这条新闻为什么比表面看起来更重要
- 要点1：是什么（事实+具体数字）
- 要点2：为什么（最深层的原因，不是表面原因）
- 要点3：然后呢（明确的判断，看多/看空/等待，有理由）
- 演讲者口播：先用一个类比或场景让听众代入，再给出分析，最后说出反直觉的洞察
- 视觉建议：关键数字用大字突出，配1张相关图片或数据图表""")
        return "\n\n".join(slides)

    async def _call_ai(self, prompt: str, max_tokens: int = 4000) -> str:
        """调用AI接口（异步）"""
        if not self.api_key:
            raise RuntimeError(f"缺少 {self.provider} 的 API Key")

        if self.provider == "anthropic":
            # 使用异步 Anthropic Claude API
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=0.85,
                system=MASTER_SYSTEM_PROMPT,
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
                    {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.85
            )
            content = response.choices[0].message.content
            return content if content else ""

    def _format_stream_script(self, content: str, news_items: List[Dict], duration: int = 30) -> str:
        """格式化直播稿"""
        date_str = datetime.now().strftime("%Y年%m月%d日")
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][datetime.now().weekday()]

        formatted = f"""
╔══════════════════════════════════════════════════════════╗
║  📺 财经深度直播稿                                        ║
║  📅 {date_str} {weekday}                                  ║
║  ⏱ 预计时长：{duration}分钟  📊 共{len(news_items)}条新闻  ║
╚══════════════════════════════════════════════════════════╝

{content}

{'─'*60}
📌 本稿由 AI 深度创作，融合刘润×小Lin说风格
📊 预计直播时长：{len(news_items) * 4}-{len(news_items) * 6} 分钟
{'─'*60}
"""
        return formatted

    def _format_article(self, content: str) -> Dict:
        """格式化公众号文章"""
        titles = []
        if "===标题选项===" in content:
            parts = content.split("===正文===")
            title_section = parts[0].replace("===标题选项===", "").strip()
            raw_titles = [t.strip() for t in title_section.split("\n") if t.strip()]
            # 清理标题前缀（标题A：/ 标题B：等）
            for t in raw_titles:
                cleaned = re.sub(r'^标题[A-Ca-c：:]\s*', '', t).strip()
                if cleaned:
                    titles.append(cleaned)
            titles = titles[:3]
            content_body = parts[1] if len(parts) > 1 else content
            # 去掉最后的===
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
            "html": self._markdown_to_html(content_body)
        }

    def _markdown_to_html(self, md: str) -> str:
        """Markdown转HTML（用于公众号）"""
        html = md

        # 清理格式标记
        html = html.replace("===标题选项===", "").replace("===正文===", "").replace("===", "")
        html = re.sub(r'标题[A-Ca-c：:].+?\n', '', html)
        html = re.sub(r'【标题选项】.+?\n\n', '', html, flags=re.DOTALL)

        # 标题转换
        html = re.sub(r'^# (.+)$', r'<h1 style="font-size:22px;font-weight:bold;margin:20px 0;color:#1a1a1a;">\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2 style="font-size:18px;font-weight:bold;margin:16px 0 8px;color:#1a1a1a;border-left:4px solid #0066cc;padding-left:10px;">\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3 style="font-size:16px;font-weight:bold;margin:12px 0 6px;color:#333;">\1</h3>', html, flags=re.MULTILINE)

        # 加粗
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#0066cc;">\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

        # 列表
        html = re.sub(r'^[•·▶📍📌✅❌🎯💡❓🟢🟡🔴] (.+)$', r'<li style="margin:6px 0;">\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'^- (.+)$', r'<li style="margin:6px 0;">\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li.+<\/li>\n?)+', lambda m: f'<ul style="margin:10px 0;padding-left:20px;list-style:disc;">{m.group(0)}</ul>', html)

        # 段落
        paragraphs = html.split("\n\n")
        formatted = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith("<h") and not p.startswith("<ul") and not p.startswith("<li"):
                p = f'<p style="line-height:1.9;margin:15px 0;color:#333;font-size:15px;">{p}</p>'
            formatted.append(p)

        return "\n".join(formatted)

    def _generate_fallback_script(self, news_items: List[Dict]) -> str:
        """AI调用失败时的备用脚本"""
        date_str = datetime.now().strftime("%Y年%m月%d日")
        script = f"""
【开场白】
各位投资者朋友，今天是{date_str}，让我告诉你今天市场上一个很多人没注意到的信号——

"""
        for i, news in enumerate(news_items, 1):
            script += f"""
【新闻{i}】{news['title']}

【深度解读】
来自{news['source']}的这条消息，表面上是{news.get('category', '财经')}方向的新闻，但背后的逻辑值得我们多想一层。

【互动提问】
这件事发展下去，你们觉得最先受影响的会是哪个板块？评论区说说你的判断。

"""
        script += f"""
【今日总结】
今天{len(news_items)}条新闻，其实都在指向同一件事：市场正在重新定价。

【明日关注】
明天最重要的一件事：关注资金面的变化，特别是北向资金的方向——那通常是最聪明的钱先走的地方。

{'─'*60}
"""
        return script

    def _generate_fallback_article(self, news_items: List[Dict]) -> Dict:
        """备用文章生成"""
        date_str = datetime.now().strftime("%m月%d日")
        titles = [
            f"今天这{len(news_items)}件事，比大多数人想得更重要",
            f"一个被忽视的信号：{news_items[0]['title'][:18]}背后的逻辑",
            f"{date_str}财经深度：看懂这几件事，看懂接下来的市场"
        ]

        content = f"# {titles[0]}\n\n"
        content += f"**{datetime.now().strftime('%Y年%m月%d日')} | 深度解读**\n\n"
        content += "## 导读\n\n"
        content += f"今天发生了{len(news_items)}件值得认真对待的事。不是因为它们"重要"这个形容词，而是因为它们合在一起，指向了一个市场还没有完全定价的方向。\n\n"

        for i, news in enumerate(news_items, 1):
            content += f"## {news['title']}\n\n"
            content += f"**来源**：{news['source']} | **分类**：{news.get('category', '财经')}\n\n"
            content += f"这条新闻的表面意思大家都看到了。但它真正值得关注的地方在于：相关领域正在发生的变化，可能比市场目前定价的更深远。\n\n"

        content += "## 核心判断\n\n"
        content += f"把今天这{len(news_items)}条新闻放在一起看，你会发现一个共同的底层逻辑：市场的天平正在悄悄移动。\n\n"
        content += "*本文内容仅供参考，不构成投资建议。*\n"

        return {"titles": titles, "content": content, "html": self._markdown_to_html(content)}

    def _generate_fallback_deep_dive(self, news_items: List[Dict]) -> str:
        """备用深度长文"""
        topic = news_items[0]['title']
        date_str = datetime.now().strftime("%Y年%m月%d日")
        return f"""# 深度分析：{topic}

**{date_str} | 原创深度研究**

---

## 破题：大多数人的理解可能只对了一半

"{topic[:30]}"——这件事的表面含义，相信大家都已经看过很多报道了。但我想从另一个角度来讲这件事。

大多数报道关注的是这件事"是什么"。我更想讨论的是：它"为什么现在发生"，以及"它在告诉我们什么"。

## 溯源

这件事不是凭空出现的。如果把时间线拉长来看，会发现它其实是过去6-12个月一系列动作的自然结果。

## 深度拆解

**对不同参与者的影响各不相同。** 对于普通散户、机构投资者、产业链上下游，这件事的含义是完全不一样的。

## 先行指标

如果想知道这件事的走向，建议关注以下3个具体信号：
1. 相关政策的后续跟进情况
2. 主要参与者的实际行动（而不是表态）
3. 资金流向的变化——这通常是最诚实的信号

## 核心结论

我的判断是：这件事的长期意义，可能远比短期市场反应所显示的更大。6个月后回头看，今天可能是一个值得记住的时间节点。

---
*本文为AI辅助生成，仅供参考。*
"""

    def _generate_fallback_ppt(self, news_items: List[Dict], focus_topic: str = "") -> str:
        """备用PPT脚本"""
        topic = focus_topic or news_items[0]['title']
        date_str = datetime.now().strftime("%Y年%m月%d日")
        return f"""# PPT脚本：{topic[:30]}

**{date_str} | 财经深度演讲**

---

┌─────────────────────────────────────────┐
│ 【第1张 · 封面】                          │
│ 标题：{topic[:20]}——它比你想的更重要      │
├─────────────────────────────────────────┤
│ 🎯 核心信息：今天要揭示一个被低估的信号   │
│ 📌 要点：                               │
│   • 表面是X，本质是Y                    │
│   • 历史上出现过类似信号                 │
│   • 接下来3个月是关键窗口               │
│ 🎤 口播：开场不说"大家好"，直接抛出数字  │
│ 📊 视觉：深色背景+大字主题，简洁有力     │
└─────────────────────────────────────────┘

【第2张 · 结论前置】
今天3个核心判断：
1. [具体判断1]
2. [具体判断2]
3. [具体判断3]

【第3-{2+len(news_items[:4])}张 · 逐条解析】
每条新闻一张，重点说"为什么重要"而非"是什么"

【最后一张 · 记忆点】
金句：[今天最核心的一句判断]
先行指标：[3个具体可观察的信号]

---
*以上为AI生成的PPT脚本框架，请根据实际情况补充具体数据。*
"""


# 全局实例
generator = ContentGenerator()
