"""Read transcript timing structure without asserting semantic or listening quality."""
from pathlib import Path
import argparse,json,math
def check(path):
    value=json.loads(Path(path).read_text(encoding='utf-8-sig'));segments=value.get('segments',[]);errors=[]
    duration=value.get('duration_seconds');end=0.;word_count=0
    if not value.get('source_id'):errors.append('source_id missing')
    if not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:errors.append('invalid duration')
    if not segments:errors.append('no transcript segments')
    for i,row in enumerate(segments):
        start,stop=row.get('start'),row.get('end')
        if not all(isinstance(n,(int,float)) and math.isfinite(n) for n in (start,stop)) or start<0 or stop<=start or start<end-0.05:
            errors.append('invalid or unordered segment '+str(i));continue
        end=stop
        if isinstance(duration,(int,float)) and stop>duration+0.5:errors.append('segment exceeds media duration')
        word_count+=len(row.get('words',[]))
    return {'structural_valid':not errors,'source_id':value.get('source_id'),'errors':errors,'segment_count':len(segments),
            'word_count':word_count,'duration_seconds':duration,'last_speech_end':end,
            'semantic_review_required':True,'human_listening_checked':False,
            'scope':'timing and source structure only; verify pauses, missed speech, names and images against actual media'}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--transcript',type=Path,required=True);a=p.parse_args()
    try:r=check(a.transcript);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r['structural_valid'] else 2)
    except (ValueError,KeyError,OSError) as error:p.exit(2,str(error)+'\n')
