import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import copy,json,os
from build_catalog import build


def build_mixed(home=None):
    home=home or Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
    choices=[home/'models_cache.json',home/'models_cache.codex_work_desktop.json']
    models=[]
    for path in choices:
        if not path.exists():continue
        values=json.loads(path.read_text(encoding='utf-8'))
        models=[copy.deepcopy(m) for m in values.get('models',[]) if m.get('slug','').startswith('gpt-')]
        if models:break
    if not models:raise ValueError('没有找到 Codex 的 GPT 目录缓存；请先正常登录 Codex 并加载一次模型列表')
    for model in models:
        model['use_responses_lite']=False
    return {'models':models+build()['models']}

if __name__=='__main__':
    catalog=build_mixed()
    (bootstrap.HERE/'models.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    print('已生成混合目录，模型数：',len(catalog['models']))
