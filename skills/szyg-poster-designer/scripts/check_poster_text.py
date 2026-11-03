"""Compare an explicit poster copy checklist with saved OCR or text, without editing images."""
import argparse
import difflib
import json
from pathlib import Path
import re
import sys
import unicodedata


def normalize(value):
    value = unicodedata.normalize('NFKC', value).casefold()
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', value)


def read_observed(path):
    raw = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() != '.json':
        return raw, raw.splitlines()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('OCR JSON必须是含Text或Lines字段的对象')
    lines = data.get('Lines', data.get('lines', []))
    if not isinstance(lines, list):
        raise ValueError('OCR Lines必须是列表')
    extracted = []
    for line in lines:
        if isinstance(line, str):
            extracted.append(line)
        elif isinstance(line, dict):
            extracted.append(str(line.get('Text', line.get('text', ''))))
    full = data.get('Text', data.get('text'))
    if full is not None and not isinstance(full, str):
        raise ValueError('OCR Text必须是字符串')
    if not full:
        full = '\n'.join(extracted)
    if not full.strip():
        raise ValueError('OCR结果没有文字')
    return full, extracted or full.splitlines()


def requirement(value, fallback_id):
    if isinstance(value, str):
        value = {'text': value}
    if not isinstance(value, dict) or not isinstance(value.get('text'), str) or not normalize(value['text']):
        raise ValueError('每个待核项必须包含非空text')
    aliases = value.get('aliases', [])
    if not isinstance(aliases, list) or not all(isinstance(a, str) and normalize(a) for a in aliases):
        raise ValueError('aliases必须是非空字符串列表')
    return {'id': str(value.get('id', fallback_id)), 'text': value['text'], 'aliases': aliases}


def check_item(item, full, lines):
    for variant in [item['text'], *item['aliases']]:
        norm = normalize(variant)
        found = bool(re.search(r'(?<!\d)' + re.escape(norm) + r'(?!\d)', full)) if norm.isdigit() else norm in full
        if found:
            return {**item, 'status': 'exact_match', 'matched_variant': variant, 'similarity_hint': 1.0}
    expected = normalize(item['text'])
    best_score, best = 0.0, ''
    # Short labels and numbers are too easy to confuse; require a complete normalized match.
    if len(expected) >= 6 and not expected.isdigit():
        candidates = set(lines)
        # Recover local windows when an OCR provider returns a single flat Text string.
        matcher = difflib.SequenceMatcher(None, expected, full, autojunk=False)
        for block in matcher.get_matching_blocks():
            if block.size < 2:
                continue
            start = max(0, block.b - block.a)
            for shift in (-2, 0, 2):
                left = max(0, start + shift)
                for length_delta in (-2, 0, 2):
                    candidates.add(full[left:left + len(expected) + length_delta])
        for observed in candidates:
            score = difflib.SequenceMatcher(None, expected, observed, autojunk=False).ratio()
            if score > best_score:
                best_score, best = score, observed
    return {**item, 'status': 'review_match' if best_score >= 0.78 else 'not_seen',
            'similarity_hint': round(best_score, 4), 'closest_normalized': best}


def compare(expected, observed_text, observed_lines):
    if not isinstance(expected, dict):
        raise ValueError('文字清单必须是JSON对象')
    sections, facts = expected.get('sections', []), expected.get('facts', [])
    if not isinstance(sections, list) or not isinstance(facts, list):
        raise ValueError('sections与facts必须是列表')
    full = normalize(observed_text)
    if not full:
        raise ValueError('观测文本为空')
    lines = [normalize(x) for x in observed_lines if normalize(x)]
    lines += [lines[i] + lines[i + 1] for i in range(len(lines) - 1)]
    results = []
    all_checks = []
    for index, section in enumerate(sections, 1):
        if not isinstance(section, dict) or not isinstance(section.get('required'), list) or not section['required']:
            raise ValueError('每个section必须包含非空required列表')
        checks = [check_item(requirement(v, f'{index}.{i}'), full, lines)
                  for i, v in enumerate(section['required'], 1)]
        results.append({'id': str(section.get('id', index)), 'label': section.get('label', str(index)),
                        'checks': checks, 'exact_count': sum(x['status'] == 'exact_match' for x in checks),
                        'unseen_count': sum(x['status'] == 'not_seen' for x in checks)})
        all_checks += checks
    fact_results = [check_item(requirement(v, f'fact-{i}'), full, lines) for i, v in enumerate(facts, 1)]
    all_checks += fact_results
    if not all_checks:
        raise ValueError('至少需要一项待核文字，不能用空清单得出通过结论')
    counts = {s: sum(x['status'] == s for x in all_checks) for s in ['exact_match', 'review_match', 'not_seen']}
    return {'status': 'all_text_found' if counts['exact_match'] == len(all_checks) else 'review_required',
            'expected_items': len(all_checks), 'counts': counts, 'sections': results, 'facts': fact_results,
            'image_or_design_approved': False,
            'scope': '仅文字覆盖提示；近似或未见需回到最终图检查，全部命中也不证明位置、版式、扫码或用户认可'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected', required=True, type=Path)
    parser.add_argument('--observed', required=True, type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        expected = json.loads(args.expected.read_text(encoding='utf-8-sig'))
        full, lines = read_observed(args.observed)
        result = compare(expected, full, lines)
        result.update(expected_source=str(args.expected), observed_source=str(args.observed))
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_bytes(rendered.encode('utf-8'))
        print(rendered, end='')
        return 0
    except (ValueError, OSError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
