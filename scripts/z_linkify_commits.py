#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import pathlib
import re
import sys
from typing import Iterable

# 列表前缀 + 任意文本 + // + 提交哈希（行尾）
PATTERN = re.compile(
    r'^(\s*[-*]\s+)'          # 列表前缀
    r'(.*?)'                  # 文本（非贪婪）
    r'\s*//\s*'               # 分隔符 //
    r'([0-9a-fA-F]{7,40})'    # 提交哈希
    r'\s*$'                   # 行尾
)

def transform_line(line: str, base_url: str) -> str:
    m = PATTERN.match(line)
    if not m:
        return line
    prefix, raw_text, commit = m.groups()
    label = raw_text.rstrip()  # 保持原始方括号，不转义
    return f"{prefix}[{label}]({base_url}/commit/{commit})\n"

def process_lines(lines: Iterable[str], base_url: str) -> Iterable[str]:
    for line in lines:
        yield transform_line(line, base_url)

def main():
    p = argparse.ArgumentParser(description="将 '- 文本 // <hash>' 转为 GitHub 提交链接")
    p.add_argument("input_md", help="输入 .md 文件路径")
    p.add_argument("-o", "--output", help="输出文件路径；不指定则原地覆盖并生成 .bak 备份")
    p.add_argument("--owner", default="hiowenluke", help="GitHub owner，默认 hiowenluke")
    p.add_argument("--repo", default="headshot-ai", help="GitHub repo，默认 headshot-ai")
    p.add_argument("--dry-run", action="store_true", help="仅打印结果")
    args = p.parse_args()

    in_path = pathlib.Path(args.input_md)
    if not in_path.exists():
        print(f"输入文件不存在: {in_path}", file=sys.stderr)
        sys.exit(1)

    base_url = f"https://github.com/{args.owner}/{args.repo}"

    with in_path.open("r", encoding="utf-8") as f:
        new_lines = list(process_lines(f, base_url))

    if args.dry_run:
        sys.stdout.writelines(new_lines)
        return

    if args.output:
        out_path = pathlib.Path(args.output)
    else:
        backup = in_path.with_suffix(in_path.suffix + ".bak")
        backup.write_text(in_path.read_text(encoding="utf-8"), encoding="utf-8")
        out_path = in_path

    out_path.write_text("".join(new_lines), encoding="utf-8")

if __name__ == "__main__":
    main()