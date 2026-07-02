import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.slide_image_generation import SlidePrompt, write_prompt_pack

def test_prompt_pack_rejects_placeholders(tmp_path):
    s=SlidePrompt(1,'标题','founders',['#111','#eee','#f60'],'bento',['Lorem ipsum placeholder'],'visual')
    m=write_prompt_pack([s], tmp_path)
    assert not m['ok'] and any('placeholder' in e.lower() for e in m['errors'])

def test_prompt_pack_accepts_real_text(tmp_path):
    s=SlidePrompt(1,'增长飞轮','运营团队',['#111111','#F5F5F5','#FF6600'],'hub-spoke',['核心指标：新增线索提升 18%','动作一：统一内容入口','动作二：沉淀复盘模板'],'中心飞轮连接四个行动卡片')
    m=write_prompt_pack([s], tmp_path)
    assert m['ok'], m['errors']
