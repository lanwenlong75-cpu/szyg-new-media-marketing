"""Check centered ASS anchors against the actual output canvas (stdlib only)."""
import argparse
import json
import re
from pathlib import Path


def check(path, width, height, center=None, tolerance=1.0):
    text = path.read_text(encoding='utf-8-sig')
    center = width / 2 if center is None else center
    errors, reviews, anchors = [], [], []
    sizes = dict(re.findall(r'(?m)^PlayRes([XY]):\s*(\d+)\s*$', text))
    if sizes != {'X': str(width), 'Y': str(height)}:
        errors.append({'kind': 'canvas_mismatch', 'declared': sizes})
    style_alignment = {}
    for line in text.splitlines():
        if line.startswith('Style:'):
            fields = line.split(':', 1)[1].strip().split(',')
            if len(fields) >= 23:
                style_alignment[fields[0]] = int(fields[18])
    dialogues = [x for x in text.splitlines() if x.startswith('Dialogue:')]
    if not dialogues:
        errors.append({'kind': 'no_captions'})
    for number, line in enumerate(dialogues, 1):
        fields = line.split(',', 9)
        if len(fields) != 10:
            errors.append({'caption': number, 'kind': 'invalid_event'})
            continue
        body = fields[9]
        pos = re.findall(r'\\pos\(([-\d.]+),\s*([-\d.]+)\)', body)
        alignment = re.findall(r'\\an(\d)', body)
        alignment = int(alignment[-1]) if alignment else style_alignment.get(fields[3])
        if r'\move(' in body or r'\t(' in body:
            reviews.append({'caption': number, 'kind': 'animated_layout_needs_review'})
        if alignment not in (2, 5, 8):
            errors.append({'caption': number, 'kind': 'anchor_not_centered', 'alignment': alignment})
        if len(pos) != 1:
            reviews.append({'caption': number, 'kind': 'explicit_position_required_for_this_check'})
            continue
        x, y = map(float, pos[0])
        anchors.append({'caption': number, 'x': x, 'y': y})
        if abs(x - center) > tolerance:
            errors.append({'caption': number, 'kind': 'horizontal_offset', 'x': x, 'expected': center})
        if not 0 <= x <= width or not 0 <= y <= height:
            errors.append({'caption': number, 'kind': 'anchor_outside_canvas'})
    return {'passed': not errors and not reviews, 'canvas': [width, height],
            'expectedCenter': center, 'captionCount': len(dialogues),
            'anchors': anchors, 'errors': errors, 'manualReview': reviews,
            'scope': 'ASS canvas and anchors only; final glyph bounds, face occlusion and pacing need actual video review'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ass', type=Path, required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument('--center-x', type=float)
    parser.add_argument('--tolerance', type=float, default=1)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.width <= 0 or args.height <= 0 or args.tolerance < 0:
        parser.error('画布须为正数，容差不得为负')
    report = check(args.ass, args.width, args.height, args.center_x, args.tolerance)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['passed', 'captionCount', 'expectedCenter']}, ensure_ascii=False))
    return 0 if report['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
