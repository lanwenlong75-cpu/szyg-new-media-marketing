"""Filter the portable poster reference library without network or local bindings."""
import argparse, json, sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--purpose', choices=['产品','课程','活动','倒计时','品牌','观点','案例','排期'])
    parser.add_argument('--density', choices=['低','中','高'])
    parser.add_argument('--category')
    parser.add_argument('--query', default='')
    parser.add_argument('--ids', nargs='+')
    parser.add_argument('--limit', type=int, default=6)
    args = parser.parse_args()
    if args.limit < 1: parser.error('--limit must be positive')
    data = json.loads((Path(__file__).resolve().parents[1] / 'references/curated-library.json').read_text(encoding='utf-8'))
    entries = data['entries']
    if args.ids:
        by_id = {item['id']: item for item in entries}
        unknown = sorted(set(args.ids) - set(by_id))
        if unknown: parser.error('IDs not in active library: ' + ', '.join(unknown))
        entries = [by_id[key] for key in dict.fromkeys(args.ids)]
    terms = args.query.casefold().split()
    matches = []
    for item in entries:
        if args.purpose and args.purpose not in item['purposes']: continue
        if args.density and args.density not in item['text_density']: continue
        if args.category and args.category != item['category']: continue
        haystack = json.dumps(item, ensure_ascii=False).casefold()
        if terms and not all(term in haystack for term in terms): continue
        matches.append(item)
    result = {'total_matches': len(matches), 'returned': min(len(matches), args.limit), 'entries': matches[:args.limit], 'status': 'matched' if matches else 'no_match_relax_filters'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__': sys.exit(main())
