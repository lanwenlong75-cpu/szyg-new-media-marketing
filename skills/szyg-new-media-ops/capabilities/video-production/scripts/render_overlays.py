"""Full-frame, timed transparent board renderer. No media generation or ASR calls."""
from pathlib import Path
import argparse,hashlib,json,math,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def require(ok,msg):
 if not ok:raise ValueError(msg)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def stamp(t):
 n=round(t*100);h,n=divmod(n,360000);m,n=divmod(n,6000);s,n=divmod(n,100)
 return f'{h}:{m:02}:{s:02}.{n:02}'
def clean(t):
 require(isinstance(t,str) and t.strip() and not any(c in t for c in ['{','}','\\']),'显示文字不能为空或含ASS控制字符')
 return t.replace('\n',r'\N')
def ass_color(rgb):return '&H'+rgb[4:6]+rgb[2:4]+rgb[:2]+'&'
def render(source,plan,out,variant,start=0,duration=None,ffmpeg='ffmpeg',ffprobe='ffprobe'):
 source=Path(source).resolve();out=Path(out).resolve();require(source.is_file(),'原声母版不存在')
 require(not out.exists(),'输出目录已存在；请另存新版本')
 require(not out.is_relative_to(source.parent) or source.parent!=out,'输出不能覆盖输入')
 probe=subprocess.run([ffprobe,'-v','error','-show_streams','-show_format','-of','json',str(source)],capture_output=True,text=True,check=True)
 meta=json.loads(probe.stdout);video=next(x for x in meta['streams'] if x['codec_type']=='video');has_audio=any(x['codec_type']=='audio' for x in meta['streams'])
 require(video.get('color_transfer') not in ['arib-std-b67','smpte2084'],'本工具接收已核对的SDR母版；HDR先按MOTION色彩流程实际转换并核验，不能只改标签')
 w,h=video['width'],video['height'];require(plan.get('canvas')==[w,h],'计划画布必须与实际母版相同，保持人物全屏')
 ratio=video.get('avg_frame_rate','0/1').split('/');fps=float(ratio[0])/float(ratio[1]);require(math.isfinite(fps) and fps>0,'视频帧时钟无效')
 total=float(meta['format']['duration']);duration=float(duration or plan.get('duration') or total-start)
 require(start>=0 and duration>0 and start+duration<=total+.05,'请求时段超出当前母版')
 cues=plan.get('cues',[]);caps=plan.get('captions',[]);require(isinstance(cues,list) and isinstance(caps,list),'计划需包含真实时码数组')
 safe=plan.get('boardBounds',[round(w*.04),round(h*.015),round(w*.96),round(h*.23)])
 require(len(safe)==4 and 0<=safe[0]<safe[2]<=w and 0<=safe[1]<safe[3]<=h,'板书区域越界')
 color='FFFFFF' if variant=='B' else '252927';fade_ms=round(1000*float(plan.get('fade',.4)))
 family='Noto Sans SC';size=int(plan.get('fontSize',round(w*.05)));caption_size=int(plan.get('captionSize',round(w*.056)))
 lines=['[Script Info]','ScriptType: v4.00+',f'PlayResX: {w}',f'PlayResY: {h}','ScaledBorderAndShadow: yes','[V4+ Styles]',
 'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
 f'Style: Board,{family},{size},&H00FFFFFF,&H00FFFFFF,&H00191919,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1',
 f'Style: Caption,{family},{caption_size},&H00FFFFFF,&H00FFFFFF,&H00191919,&H60000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,0,1',
 '[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
 def event(at,end,text,style='Board',layer=1):
  require(math.isfinite(at) and math.isfinite(end) and 0<=at<end<=duration+.001,'显示区间超出本段真实时钟')
  lines.append(f'Dialogue: {layer},{stamp(at)},{stamp(end)},{style},,0,0,0,,{text}')
 if variant=='B':
  # A soft alpha gradient protects the top board while retaining the original full-frame footage.
  for i in range(36):
   y0=round(safe[3]*i/36);y1=round(safe[3]*(i+1)/36);alpha=round(255-148*(1-i/36)**1.4)
   event(0,duration,'{\\an7\\pos(0,0)\\p1\\bord0\\c&H000000&\\alpha&H%02X&}m 0 %d l %d %d %d %d 0 %d'%(alpha,y0,w,y0,w,y1,y1),layer=0)
 if variant=='C':
  x0,y0,x1,y1=safe
  event(0,duration,'{\\an7\\pos(0,0)\\p1\\bord1\\blur2\\1c&HFFFFFF&\\1a&HDC&\\3c&HFFFFFF&\\3a&H80&}m %d %d l %d %d %d %d %d %d'%(x0,y0,x1,y0,x1,y1,x0,y1),layer=0)
 for c in cues:
  at=float(c['at']);end=min(duration,float(c.get('end',duration)));require(at<end,'板书未获得有效时码')
  common='{\\fad(%d,0)\\c%s}'%(fade_ms,ass_color(c.get('color',color)))
  if c['kind']=='text':
   x,y=c['pos'];s=int(c.get('size',size));require(s>0 and safe[0]<=x<=safe[2] and safe[1]<=y<=safe[3],'板书文字坐标不在声明区域')
   text=clean(c['text']);require(max(map(len,text.split(r'\N')))*s*.56<=safe[2]-safe[0],'当前板书文字过宽，需缩短或分行后实际复核')
   event(at,end,'{\\an5\\pos(%g,%g)\\fs%d}'%(x,y,s)+common+text)
  elif c['kind'] in ['line','arrow']:
   (x0,y0),(x1,y1)=c['points'];require(all(safe[0]<=x<=safe[2] and safe[1]<=y<=safe[3] for x,y in [(x0,y0),(x1,y1)]),'连接线越界')
   steps=12;growth=min(float(c.get('drawSeconds',.35)),end-at)
   for i in range(steps):
    a=i/steps;b=(i+1)/steps;xx0=x0+(x1-x0)*a;yy0=y0+(y1-y0)*a;xx1=x0+(x1-x0)*b;yy1=y0+(y1-y0)*b
    thickness=float(c.get('width',max(2,w/540)));dx,dy=xx1-xx0,yy1-yy0;length=math.hypot(dx,dy);require(length>0,'连接线长度为零');nx=-dy/length*thickness/2;ny=dx/length*thickness/2
    path='m %g %g l %g %g %g %g %g %g'%(xx0+nx,yy0+ny,xx1+nx,yy1+ny,xx1-nx,yy1-ny,xx0-nx,yy0-ny)
    event(at+growth*a,end,'{\\an7\\pos(0,0)\\p1\\bord0}'+common+path)
  else:raise ValueError('当前工具只接收text、line、arrow，其他图形按完整模板工程制作')
 for c in caps:
  y=float(c.get('y',round(h*.8125)));require(0<y<h,'字幕高度无效')
  event(float(c['start']),float(c['end']),'{\\an2\\pos(%g,%g)}'%(w/2,y)+clean(c['text']),'Caption',2)
 out.mkdir(parents=True);ass=out/'overlay.ass';ass.write_text('\n'.join(lines)+'\n',encoding='utf-8-sig',newline='\n')
 caption_lines=lines[:lines.index('[Events]')+2]+[line for line in lines if line.startswith('Dialogue:') and line.split(',',9)[3]=='Caption']
 (out/'captions.ass').write_text('\n'.join(caption_lines)+'\n',encoding='utf-8-sig',newline='\n')
 font=ROOT/'assets/fonts/NotoSansSC.ttf';require(font.is_file(),'随包字体缺失')
 fonts=str(font.parent).replace('\\','/').replace(':','\\:').replace("'",r"\'")
 final=out/'preview.mp4';command=[ffmpeg,'-hide_banner','-v','warning','-n','-ss',str(start),'-i',str(source),'-t',str(duration),'-vf',"subtitles=overlay.ass:fontsdir='"+fonts+"',setsar=1",'-map','0:v:0','-map','0:a?','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-r',str(fps),'-fps_mode','cfr','-c:a','aac','-b:a','192k','-movflags','+faststart',str(final)]
 result=subprocess.run(command,cwd=out,capture_output=True,text=True,encoding='utf-8',errors='replace');(out/'render.log').write_text(result.stderr,encoding='utf-8');require(result.returncode==0,'渲染失败，见render.log')
 record={'schema':'transparent-board/1','input':str(source),'input_sha256':sha(source),'input_interval':[start,start+duration],'output':str(final),'output_sha256':sha(final),'variant':variant,'canvas':[w,h],'fps':fps,'personTransform':'identity; original full frame retained','caption_center':w/2,'cues':cues,'audio':'same source segment, AAC re-encoded; no speech rewrite','audio_present':has_audio,'humanListeningChecked':False,'visualStyleAccepted':False,'semanticReview':'计划须由助手与实际保留口播核对，渲染器不判断词义','quality_state':'待当前使用者观看反馈'}
 (out/'project.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');shutil.copy2(font,out/'used-font.ttf')
 return record
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--variant',choices=['A','B','C'],default='B');p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe');a=p.parse_args()
 try:print(json.dumps(render(a.input,read(a.plan),a.out_dir,a.variant,a.start,a.duration,a.ffmpeg,a.ffprobe),ensure_ascii=False,indent=2))
 except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as e:p.exit(2,str(e)+'\n')
if __name__=='__main__':main()
