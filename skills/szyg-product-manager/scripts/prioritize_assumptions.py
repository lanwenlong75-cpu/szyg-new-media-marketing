"""Evidence-labelled JSON adapter for the vendored MIT assumption mapper."""
from pathlib import Path
import argparse
import importlib.util
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT/'third_party/alireza-product-discovery/product-discovery/scripts/assumption_mapper.py'
MODES = {'evidence_backed', 'analyst_estimate', 'synthetic_test'}
CATEGORIES = {'desirability', 'viability', 'feasibility', 'usability'}

def load_upstream():
    name = '_product_upstream_assumption_mapper'
    spec = importlib.util.spec_from_file_location(name, UPSTREAM)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(name+' must be numeric, or both scores must be null')
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(name+' must be finite and in [0, 1]')
    return float(value)

def prioritize(data):
    mode = data.get('mode')
    if mode not in MODES:
        raise ValueError('mode must identify evidence_backed, analyst_estimate, or synthetic_test')
    rows = data.get('assumptions')
    if not isinstance(rows, list) or not rows:
        raise ValueError('assumptions must be a nonempty list')
    upstream = load_upstream()
    ids, output = set(), []
    for row in rows:
        identity, text = row.get('id'), row.get('statement')
        if not isinstance(identity, str) or not identity.strip() or identity in ids:
            raise ValueError('assumption id must be nonempty and unique')
        ids.add(identity)
        if not isinstance(text, str) or not text.strip():
            raise ValueError('assumption statement is missing')
        category = row.get('category')
        if category not in CATEGORIES:
            raise ValueError('unrecognized assumption category')
        status = row.get('evidence_status', 'unknown')
        refs = row.get('evidence_refs', [])
        if status not in {'unknown', 'hypothesis', 'observed'}:
            raise ValueError('evidence_status must be unknown, hypothesis, or observed')
        if not isinstance(refs, list) or any(not isinstance(x, str) or not x.strip() for x in refs):
            raise ValueError('evidence_refs must be a list of nonempty references')
        if status == 'observed' and not refs:
            raise ValueError('observed claims require evidence references')
        risk, certainty = row.get('risk'), row.get('certainty')
        if (risk is None) != (certainty is None):
            raise ValueError('provide both risk and certainty, or leave both null')
        basis = row.get('score_basis', '')
        if risk is not None:
            if not isinstance(basis, str) or not basis.strip():
                raise ValueError('numeric scores require a stated score_basis')
            if mode == 'evidence_backed' and (status != 'observed' or not refs):
                raise ValueError('evidence_backed scoring requires observed references')
            risk, certainty = number(risk, 'risk'), number(certainty, 'certainty')
            score = upstream.Assumption(text, category, risk, certainty).priority_score
        else:
            score = None
        output.append({'id':identity, 'statement':text, 'category':category,
            'risk':risk, 'certainty':certainty, 'priority_score':score,
            'score_state':'unscored' if score is None else mode,
            'score_basis':basis, 'evidence_status':status, 'evidence_refs':refs,
            'suggested_test':upstream.suggest_test(category)})
    output.sort(key=lambda x:(x['priority_score'] is None, -(x['priority_score'] or 0)))
    return {'mode':mode, 'formula':'risk * (1 - certainty)',
        'interpretation':'Supplied estimates order discussion; scores are not customer outcomes or success probabilities. Null scores remain unscored.',
        'upstream':'alirezarezvani/claude-skills@19392f7a08264ed00486a251f5b2098321771f94',
        'assumptions':output}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        result=prioritize(json.loads(args.input.read_text(encoding='utf-8-sig')))
        text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(text,encoding='utf-8')
        else:
            print(text,end='')
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.exit(2,str(error)+'\n')

if __name__=='__main__':
    main()
