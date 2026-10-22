"""Uncleaned full-timeline local ASR. Downloads require an explicit flag."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,subprocess,sys,time
def require(ok,msg):
 if not ok:raise ValueError(msg)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def srtstamp(t):
 n=round(t*1000);h,n=divmod(n,3600000);m,n=divmod(n,60000);s,n=divmod(n,1000);return f'{h:02}:{m:02}:{s:02},{n:03}'
def transcribe(source,out,model,device,compute,language,allow_download,cache,require_gpu):
 from faster_whisper import WhisperModel
 import importlib.metadata
 import ctranslate2
 source=Path(source).resolve();out=Path(out).resolve();require(source.is_file(),'当前音视频文件不存在');require(not out.exists(),'原始识别稿输出已存在，请另存新版本')
 if device=='auto':device='cuda' if ctranslate2.get_cuda_device_count()>0 else 'cpu'
 require(not require_gpu or device=='cuda','当前任务要求GPU，当前没有可用CUDA设备；先检查GPU，不能静默回退CPU')
 require(device!='cuda' or ctranslate2.get_cuda_device_count()>0,'所选CUDA设备不可用')
 if compute=='auto':compute='float16' if device=='cuda' else 'int8'
 local=Path(model).expanduser().is_dir();require(local or allow_download,'首次模型下载未授权；使用实际本地模型目录，或明确传入--allow-download')
 print(json.dumps({'phase':'loading','device':device,'compute_type':compute,'model':model,'may_download':not local and allow_download,'scope':'本地转写，原始输出保留口头语与重起；不等同人工听校'},ensure_ascii=False),flush=True)
 start=time.monotonic();engine=WhisperModel(model,device=device,compute_type=compute,download_root=str(cache) if cache else None,local_files_only=not allow_download)
 out.mkdir(parents=True);iterator,info=engine.transcribe(str(source),language=language,word_timestamps=True,vad_filter=False,condition_on_previous_text=False,beam_size=5)
 rows=[]
 for seg in iterator:
  row={'id':seg.id,'start':seg.start,'end':seg.end,'text':seg.text,'avg_logprob':seg.avg_logprob,'no_speech_prob':seg.no_speech_prob,'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in seg.words or []]}
  rows.append(row);print(json.dumps({'phase':'segment','end':round(seg.end,2)},ensure_ascii=False),flush=True)
 data={'schema':'raw-spoken-asr/1','source':str(source),'source_sha256':sha(source),'model':model,'device':device,'compute_type':compute,'language':info.language,'language_probability':info.language_probability,'duration':info.duration,'segments':rows,'humanListeningChecked':False,'source_text_cleaned':False,'versions':{'faster-whisper':importlib.metadata.version('faster-whisper'),'ctranslate2':importlib.metadata.version('ctranslate2')},'wall_seconds':round(time.monotonic()-start,3),'unresolvedItems':['模型仍可能漏掉重复、口误或低声片段，按原声及独立短窗复核，不能据此自动删句']}
 (out/'raw-transcript.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (out/'raw-fulltext.txt').write_text('\n'.join(r['text'] for r in rows)+'\n',encoding='utf-8')
 (out/'raw-timestamped.txt').write_text('\n'.join(srtstamp(r['start'])+' --> '+srtstamp(r['end'])+' '+r['text'] for r in rows)+'\n',encoding='utf-8')
 (out/'raw.srt').write_text('\n\n'.join(str(i)+'\n'+srtstamp(r['start'])+' --> '+srtstamp(r['end'])+'\n'+r['text'] for i,r in enumerate(rows,1))+'\n',encoding='utf-8')
 return {'output':str(out),'duration':info.duration,'segments':len(rows),'device':device,'humanListeningChecked':False}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--model',default='small');p.add_argument('--device',choices=['auto','cuda','cpu'],default='auto');p.add_argument('--compute-type',default='auto');p.add_argument('--language',default='zh');p.add_argument('--allow-download',action='store_true');p.add_argument('--model-cache',type=Path);p.add_argument('--require-gpu',action='store_true');a=p.parse_args()
 try:print(json.dumps(transcribe(a.input,a.out_dir,a.model,a.device,a.compute_type,a.language,a.allow_download,a.model_cache,a.require_gpu),ensure_ascii=False,indent=2))
 except (ImportError,ValueError,OSError,RuntimeError) as e:p.exit(2,str(e)+'\n')
if __name__=='__main__':main()
