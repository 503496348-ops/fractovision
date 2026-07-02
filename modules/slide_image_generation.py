from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, re, time
PLACEHOLDER_RE=re.compile(r'\b(lorem|ipsum|placeholder|todo|sample text)\b|占位|待填写|示例文字', re.I)
@dataclass
class SlidePrompt:
    slide_no:int; title:str; audience:str; palette:list[str]; layout_frame:str; page_text:list[str]; visual_brief:str
    def validate(self)->list[str]:
        errors=[]; joined='\n'.join([self.title,*self.page_text,self.visual_brief])
        if not self.page_text or sum(len(x.strip()) for x in self.page_text)<30: errors.append(f'slide {self.slide_no}: page_text too thin')
        if PLACEHOLDER_RE.search(joined): errors.append(f'slide {self.slide_no}: placeholder marker detected')
        if len(set(self.palette))<3: errors.append(f'slide {self.slide_no}: palette needs at least 3 colors')
        return errors
    def to_prompt(self)->str:
        text_block='\n'.join(f'- {t}' for t in self.page_text)
        return f'Create a complete 16:9 slide image for {self.audience}.\nPalette: {", ".join(self.palette)}. Layout: {self.layout_frame}.\nTitle: {self.title}\nAll visible text must appear verbatim:\n{text_block}\nVisual brief: {self.visual_brief}\nNo lorem ipsum, no placeholder boxes, no invented numbers.'
def slug(text:str)->str: return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+','-',text).strip('-')[:40] or 'slide'
def write_prompt_pack(slides:list[SlidePrompt], out_dir:str|Path)->dict:
    out=Path(out_dir); out.mkdir(parents=True, exist_ok=True); manifest={'created_at':time.time(),'slides':[]}; all_errors=[]; frames=[]
    for s in slides:
        frames.append(s.layout_frame); errors=s.validate(); all_errors.extend(errors)
        p=out/f'{s.slide_no:02d}-{slug(s.title)}.md'; p.write_text(s.to_prompt(), encoding='utf-8')
        manifest['slides'].append(asdict(s)|{'prompt_file':str(p),'errors':errors})
    if len(frames)!=len(set(frames)): all_errors.append('layout_frame repeats across slides')
    manifest['ok']=not all_errors; manifest['errors']=all_errors
    (out/'image_prompt_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest
