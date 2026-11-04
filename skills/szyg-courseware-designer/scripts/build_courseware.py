"""Build editable PPTX from the included layouts using Python's standard library."""
from pathlib import Path
from copy import deepcopy
from xml.etree import ElementTree as E
import argparse, html, json, posixpath, re, struct, zipfile, zlib

NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
for prefix,uri in NS.items():E.register_namespace(prefix,uri)
LAYOUTS={
 'cover':(1,{'title':3,'emphasis':4,'subtitle':5}),
 'question':(2,{'heading':2,'question':3,'prompt':4}),
 'flow':(3,{'heading':2,'label1':4,'detail1':5,'label2':8,'detail2':9,'label3':12,'detail3':13,'label4':16,'detail4':17,'summary':18}),
 'evidence':(4,{'heading':2,'evidence_note':5,'source':6}),
 'exercise':(5,{'heading':2,'step1':5,'step2':8,'step3':11}),
 'closing':(6,{'heading':2,'message':3})}
ROOT=Path(__file__).resolve().parents[1]
def template_path():
    for name in ('dark-yellow-layouts.pptx','judou-dark-yellow-layouts.pptx'):
        p=ROOT/'assets'/name
        if p.is_file():return p
    raise ValueError('Missing included editable layout template')
def xml(root):return E.tostring(root,encoding='utf-8',xml_declaration=True)
def text_of(shape):return '\n'.join(''.join(p.itertext()) for p in shape.findall('p:txBody/a:p',NS))
def replace(shape,text,font=None):
    body=shape.find('p:txBody',NS)
    if body is None:raise ValueError('Target shape has no text body')
    old=body.findall('a:p',NS);first=old[0];props=first.find('a:pPr',NS);style=first.find('a:r/a:rPr',NS)
    for p in old:body.remove(p)
    for line in str(text).split('\n'):
        p=E.SubElement(body,'{'+NS['a']+'}p')
        if props is not None:p.append(deepcopy(props))
        r=E.SubElement(p,'{'+NS['a']+'}r')
        if style is not None:r.append(deepcopy(style))
        t=E.SubElement(r,'{'+NS['a']+'}t');t.text=line
    if font:
        for p in body.findall('a:p',NS):
            for r in p.findall('a:r',NS):
                rp=r.find('a:rPr',NS)
                if rp is None:rp=E.Element('{'+NS['a']+'}rPr');r.insert(0,rp)
                for kind in ('latin','ea','cs'):
                    node=rp.find('a:'+kind,NS)
                    if node is None:node=E.SubElement(rp,'{'+NS['a']+'}'+kind)
                    node.set('typeface',font)
def image_size(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        offset=8;header=None;pixels=[];ended=False
        while offset+12<=len(raw):
            size=int.from_bytes(raw[offset:offset+4],'big');kind=raw[offset+4:offset+8];data=raw[offset+8:offset+8+size]
            if offset+12+size>len(raw) or zlib.crc32(kind+data)!=int.from_bytes(raw[offset+8+size:offset+12+size],'big'):raise ValueError('PNG chunk is truncated or has an invalid CRC')
            if kind==b'IHDR':
                if header is not None or offset!=8 or size!=13:raise ValueError('Invalid PNG header')
                header=struct.unpack('>IIBBBBB',data)
            elif kind==b'IDAT':pixels.append(data)
            elif kind==b'IEND':ended=True;break
            offset+=size+12
        if not header or not ended or not pixels or min(header[:2])<1:raise ValueError('PNG is missing image data or its closing chunk')
        decompressor=zlib.decompressobj();decoded=decompressor.decompress(b''.join(pixels),128*1024*1024+1)
        if not decoded or len(decoded)>128*1024*1024 or not decompressor.eof:raise ValueError('PNG pixels are invalid or exceed the 128 MiB decoded-image limit')
        return (*header[:2],'png','image/png')
    if raw.startswith(b'\xff\xd8') and raw.rstrip().endswith(b'\xff\xd9'):
        offset=2
        while offset+9<len(raw):
            if raw[offset]!=255:offset+=1;continue
            marker=raw[offset+1];offset+=2
            if marker in (0xD8,0xD9):continue
            length=int.from_bytes(raw[offset:offset+2],'big')
            if marker in (0xC0,0xC1,0xC2):
                h,w=struct.unpack('>HH',raw[offset+3:offset+7]);return w,h,'jpg','image/jpeg'
            if length<2:break
            offset+=length
    raise ValueError('Images must be readable PNG or JPEG')
def build(spec_path,output,template=None):
    spec_path=Path(spec_path).resolve();spec=json.loads(spec_path.read_text(encoding='utf-8-sig'))
    slides=spec.get('slides');assert isinstance(slides,list) and slides,'slides must be a nonempty list'
    output=Path(output).resolve()
    if output.exists():raise ValueError('Use a new output directory; existing versions are preserved')
    with zipfile.ZipFile(template or template_path()) as z:parts={n:z.read(n) for n in z.namelist()}
    original=dict(parts);pres=E.fromstring(parts['ppt/presentation.xml']);cx,cy=(int(pres.find('p:sldSz',NS).get(k)) for k in ('cx','cy'))
    ids=pres.find('p:sldIdLst',NS)
    for node in list(ids):ids.remove(node)
    rels=E.fromstring(parts['ppt/_rels/presentation.xml.rels'])
    for rel in list(rels):
        if rel.get('Type','').endswith('/slide'):rels.remove(rel)
    types=E.fromstring(parts['[Content_Types].xml'])
    for node in list(types):
        if re.match(r'/ppt/(slides/slide|notesSlides/notesSlide)',node.get('PartName','')):types.remove(node)
    for name in list(parts):
        if name.startswith(('ppt/slides/','ppt/notesSlides/')):del parts[name]
    records=[];previews=[];maxrid=1000
    for i,item in enumerate(slides,1):
        layout=item.get('layout');assert layout in LAYOUTS,'Unknown layout: '+str(layout)
        source,mapping=LAYOUTS[layout];fields=item.get('text',{})
        if set(fields)!=set(mapping):raise ValueError(f'Page {i}: expected text fields {sorted(mapping)}, got {sorted(fields)}; explicitly fill or leave empty, no sample text is carried over')
        if not isinstance(item.get('notes'),str) or not item['notes'].strip():raise ValueError(f'Page {i}: provide actual speaker notes')
        root=E.fromstring(original[f'ppt/slides/slide{source}.xml'])
        shapes={int(s.find('p:nvSpPr/p:cNvPr',NS).get('id')):s for s in root.findall('p:cSld/p:spTree/p:sp',NS)}
        for key,shape_id in mapping.items():
            if not isinstance(fields[key],str):raise ValueError('Text fields must be strings')
            replace(shapes[shape_id],fields[key],spec.get('font'))
        slide_rels=E.fromstring(original[f'ppt/slides/_rels/slide{source}.xml.rels'])
        for rel in list(slide_rels):
            if rel.get('Type','').endswith('/notesSlide'):slide_rels.remove(rel)
        E.SubElement(slide_rels,'{'+REL+'}Relationship',Id='rIdNotes',Type=NS['r']+'/notesSlide',Target=f'../notesSlides/notesSlide{i}.xml')
        images=[]
        for j,image in enumerate(item.get('images',[]),1):
            path=(spec_path.parent/image['path']).resolve();raw=path.read_bytes();w,h,ext,mime=image_size(raw)
            rect=[float(image[k]) for k in ('x','y','width','height')]
            x,y,bw,bh=rect
            if min(bw,bh)<=0 or x<0 or y<0 or x+bw>1280 or y+bh>720:raise ValueError('Image rectangle must stay inside 1280x720')
            ratio=min(bw/w,bh/h);ww,hh=w*ratio,h*ratio;x+=(bw-ww)/2;y+=(bh-hh)/2
            pic=E.fromstring(f'<p:pic xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}" xmlns:r="{NS["r"]}"><p:nvPicPr><p:cNvPr id="{100+j}" name="Evidence {j}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rIdImage{j}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{int(x*cx/1280)}" y="{int(y*cy/720)}"/><a:ext cx="{int(ww*cx/1280)}" cy="{int(hh*cy/720)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')
            root.find('p:cSld/p:spTree',NS).append(pic)
            media=f'courseware-{i}-{j}.{ext}';parts['ppt/media/'+media]=raw
            E.SubElement(slide_rels,'{'+REL+'}Relationship',Id='rIdImage'+str(j),Type=NS['r']+'/image',Target='../media/'+media)
            if not any(n.get('Extension')==ext for n in types):E.SubElement(types,'{'+CT+'}Default',Extension=ext,ContentType=mime)
            images.append({'path':path.name,'rect':[x,y,ww,hh]})
        notes=E.fromstring(original[f'ppt/notesSlides/notesSlide{source}.xml'])
        for shape in notes.findall('p:cSld/p:spTree/p:sp',NS):
            ph=shape.find('p:nvSpPr/p:nvPr/p:ph',NS)
            if ph is not None and ph.get('type')=='body':replace(shape,item['notes'],spec.get('font'))
        notes_rels=E.fromstring(original[f'ppt/notesSlides/_rels/notesSlide{source}.xml.rels'])
        for rel in notes_rels:
            if rel.get('Type','').endswith('/slide'):rel.set('Target',f'../slides/slide{i}.xml')
        parts[f'ppt/slides/slide{i}.xml']=xml(root);parts[f'ppt/slides/_rels/slide{i}.xml.rels']=xml(slide_rels)
        parts[f'ppt/notesSlides/notesSlide{i}.xml']=xml(notes);parts[f'ppt/notesSlides/_rels/notesSlide{i}.xml.rels']=xml(notes_rels)
        maxrid+=1;rid='rId'+str(maxrid);E.SubElement(ids,'{'+NS['p']+'}sldId',id=str(255+i),attrib={'{'+NS['r']+'}id':rid})
        E.SubElement(rels,'{'+REL+'}Relationship',Id=rid,Type=NS['r']+'/slide',Target=f'slides/slide{i}.xml')
        for location,kind in ((f'/ppt/slides/slide{i}.xml','slide'),(f'/ppt/notesSlides/notesSlide{i}.xml','notesSlide')):
            E.SubElement(types,'{'+CT+'}Override',PartName=location,ContentType='application/vnd.openxmlformats-officedocument.presentationml.'+kind+'+xml')
        records.append({'page':i,'layout':layout,'text':fields,'notes':item['notes'],'images':images})
        previews.append('<section><h2>'+str(i)+'. '+html.escape(layout)+'</h2>'+''.join('<p><b>'+html.escape(k)+'</b> '+html.escape(v).replace('\n','<br>')+'</p>' for k,v in fields.items())+'<details><summary>讲师备注</summary>'+html.escape(item['notes']).replace('\n','<br>')+'</details></section>')
    parts['ppt/presentation.xml']=xml(pres);parts['ppt/_rels/presentation.xml.rels']=xml(rels);parts['[Content_Types].xml']=xml(types)
    # Check internal relationship targets before writing a deliverable.
    for name,raw in parts.items():
        if not name.endswith('.rels'):continue
        base='' if name=='_rels/.rels' else posixpath.dirname(posixpath.dirname(name))
        for rel in E.fromstring(raw):
            if rel.get('TargetMode')=='External':continue
            target=posixpath.normpath(posixpath.join(base,rel.get('Target',''))).lstrip('/')
            if target not in parts:raise ValueError('Broken relationship: '+name+' -> '+target)
    output.mkdir(parents=True)
    pptx=output/'courseware.pptx'
    with zipfile.ZipFile(pptx,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(parts.items()):z.writestr(name,raw)
    (output/'handout.html').write_text('<!doctype html><meta charset="utf-8"><title>'+html.escape(spec.get('title','课件'))+'</title><style>body{max-width:900px;margin:40px auto;font:20px sans-serif;line-height:1.6}section{break-after:page;margin:60px 0}p{white-space:pre-wrap}</style><h1>'+html.escape(spec.get('title','课件'))+'</h1><p>内容与备注回读页；不是PPTX逐页渲染图。</p>'+''.join(previews),encoding='utf-8')
    report={'built':True,'slides':len(slides),'editable_text_and_shapes':True,'notes_embedded':True,'internal_relationships_valid':True,'powerpoint_rendered':False,'classroom_accepted':False,'output':str(pptx),'pages':records}
    (output/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {k:v for k,v in report.items() if k!='pages'}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path);p.add_argument('--output',type=Path);p.add_argument('--template',type=Path);p.add_argument('--layouts',action='store_true');a=p.parse_args()
    try:
        if a.layouts:print(json.dumps({k:list(v[1]) for k,v in LAYOUTS.items()},ensure_ascii=False,indent=2))
        elif not a.input or not a.output:p.error('--input and --output are required')
        else:print(json.dumps(build(a.input,a.output,a.template),ensure_ascii=False,indent=2))
    except Exception as e:p.exit(2,str(e)+'\n')
