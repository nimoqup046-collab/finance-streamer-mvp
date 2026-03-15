#!/usr/bin/env python3
"""
本地内容质量 benchmark：
- 读取固定样例集与 rubric
- 调用当前 generator 生成直播稿 / 公众号文章
- 输出一份可人工打分的 Markdown 报告

默认不会修改仓库内文件，报告输出到 /tmp。
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = ROOT / "benchmarks"
CASES_PATH = BENCHMARK_DIR / "content_quality_cases.json"
RUBRIC_PATH = BENCHMARK_DIR / "content_quality_rubric.json"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def render_rubric_markdown(rubric: Dict[str, Any]) -> str:
    lines = ["## 评分 Rubric", ""]
    for item in rubric["dimensions"]:
        lines.append(f"- **{item['label']}**：{item['question']}")
        lines.append(f"  - 通过信号：{item['pass_signal']}")
    lines.append("")
    return "\n".join(lines)


def render_case_header(case: Dict[str, Any]) -> str:
    lines = [
        f"## Case: {case['name']}",
        "",
        f"- `id`: `{case['id']}`",
        f"- 目标主线：{case['expected_mainline']}",
        "",
        "### 新闻池",
        "",
    ]
    for item in case["news_items"]:
        lines.append(
            f"- [{item['category']}] {item['title']}（{item['source']} {item['time']}）"
        )
    lines.append("")
    lines.append("### 直播稿验收标准")
    lines.extend([f"- {criterion}" for criterion in case["stream_script_success_criteria"]])
    lines.append("")
    lines.append("### 公众号验收标准")
    lines.extend([f"- {criterion}" for criterion in case["article_success_criteria"]])
    lines.append("")
    return "\n".join(lines)


async def run_benchmark(output_path: Path) -> None:
    from backend.generator import generator

    cases = load_json(CASES_PATH)["cases"]
    rubric = load_json(RUBRIC_PATH)

    lines: List[str] = [
        "# Content Quality Benchmark Report",
        "",
        f"- 生成时间：{datetime.now().isoformat()}",
        f"- AI_PROVIDER：`{generator.provider}`",
        f"- AI_MODEL：`{generator.model}`",
        "",
        render_rubric_markdown(rubric),
    ]

    for case in cases:
        news_items = case["news_items"]
        lines.append(render_case_header(case))

        stream_script = await generator.generate_stream_script(
            news_items,
            duration=30,
            style="洞察",
        )
        article = await generator.generate_article(
            news_items,
            focus_topic=case["expected_mainline"],
        )

        lines.extend(
            [
                "### 直播稿输出",
                "",
                "```markdown",
                stream_script.strip(),
                "```",
                "",
                "### 公众号文章标题",
                "",
            ]
        )
        for title in article.get("titles", []):
            lines.append(f"- {title}")
        lines.extend(
            [
                "",
                "### 公众号正文",
                "",
                "```markdown",
                article.get("content", "").strip(),
                "```",
                "",
                "---",
                "",
            ]
        )

    output_path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="运行固定样例集内容质量 benchmark")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只校验样例集与 rubric 结构，不调用模型",
    )
    parser.add_argument(
        "--output",
        default=f"/tmp/content-quality-benchmark-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md",
        help="报告输出路径",
    )
    args = parser.parse_args()

    cases = load_json(CASES_PATH)
    rubric = load_json(RUBRIC_PATH)
    assert len(cases["cases"]) >= 3, "固定样例集至少需要 3 组 case"
    assert len(rubric["dimensions"]) >= 5, "rubric 维度不足"

    if args.dry_run:
        print("DRY_RUN_OK")
        print(f"cases={len(cases['cases'])}")
        print(f"rubric_dimensions={len(rubric['dimensions'])}")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(run_benchmark(output_path))
    print(f"BENCHMARK_REPORT={output_path}")


if __name__ == "__main__":
    main()
