#!/usr/bin/env python3
"""Anti-AI style/static quality guard for Fractovision.

Focus: artifact naming/style risk, overly synthetic language markers,
and aggressive visual/branding defaults that often indicate template-heavy slop.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]

RULES = [
    {
        "name": "文本 emoji 过密（可能偏机器默认语体）",
        "pattern": re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]"),
        "limit": 30,
    },
    {
        "name": "过多动效/幻觉模板符号（CSS/JS 滥用迹象）",
        "pattern": re.compile(r"linear-gradient\(|radial-gradient\(|box-shadow|filter:\s*blur\(|backdrop-filter", re.IGNORECASE),
        "limit": 40,
    },
    {
        "name": "过量全大写词（口号化倾向）",
        "pattern": re.compile(r"\b[A-Z]{5,}\b"),
        "limit": 26,
    },
]

TARGET_EXTENSIONS = {".md", ".txt", ".py", ".json", ".yml", ".yaml", ".js", ".ts", ".tsx", ".css", ".html", ".mdx"}



def collect_style_guard_report(root: Path | None = None) -> Dict[str, Any]:
    root = root or ROOT
    checks = []

    for rule in RULES:
        total = 0
        samples = []
        for p in root.rglob('*'):
            if not p.is_file() or '.git' in p.parts or p.name == 'anti_ai_style_guard.py':
                continue
            if p.suffix.lower() not in TARGET_EXTENSIONS:
                continue
            try:
                text = p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            hits = rule['pattern'].findall(text)
            if hits:
                total += len(hits)
                if len(samples) < 2:
                    samples.append(str(p.relative_to(root)))

        checks.append(
            {
                "name": rule['name'],
                "ok": total <= rule['limit'],
                "count": total,
                "limit": rule['limit'],
                "sample_files": samples,
                "fix": "降低模板化视觉指纹，结合 kill-ai-slop 风格清洗策略重新组织配色与动效节奏",
            }
        )

    anti_doc = root / 'references' / 'content-guidelines.md'
    checks.append(
        {
            "name": "反AI风格执行文档",
            "ok": anti_doc.exists(),
            "fix": "补齐反AI风格文档（content-guidelines）并绑定 doctor 闭环",
            "sample_files": [str(anti_doc.relative_to(root))] if anti_doc.exists() else [],
        }
    )

    return {
        "checks": checks,
        "passed": all(c['ok'] for c in checks),
    }
