"""Portable suite setup/status. Never registers a plugin or sends inference."""
import os,sys,json,subprocess,tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['MGC_ROOT']=str(ROOT)
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'src'))
from mgc.vault import Vault,choose_files
from mgc.paths import python_executable

VERSION='0.3'

def check():
    from mgc.codex_open import codex_app_executable
    try:codex_app_executable();installed=True
    except ValueError:installed=False
    home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
    config=home/'config.toml'
    parsed=tomllib.loads(config.read_text(encoding='utf-8-sig')) if config.exists() else {}
    known={'openai':'original','mgc_vertex_gateway':'google','mgc_mixed_gateway':'mixed'}
    result={'suite_version':VERSION,'vertex_credentials_configured':Vault().status()['configured'],
        'codex_installed':installed,'active_mode':known.get(parsed.get('model_provider','openai'),'other'),
        'default_model':parsed.get('model'),'inference_performed':False}
    catalog_path=ROOT/'gateway_mixed/models.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.exists() else {}
    astra=next((m for m in catalog.get('models',[]) if m.get('slug')=='gpt-6-astra'),{})
    result['mixed_astra_reasoning_levels']=[x['effort'] for x in astra.get('supported_reasoning_levels',[])]
    result['google_deadline_seconds']=json.loads((ROOT/'gateway/settings.json').read_text(encoding='utf-8'))['timeout_seconds']
    print(json.dumps(result,ensure_ascii=False,indent=2))

def main():
    command=sys.argv[1] if len(sys.argv)>1 else 'check'
    if command=='import':
        path=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'VertexAI/Cloud.txt'
        if len(sys.argv)<=2:
            ready=path.is_file() and 'YOUR_PROJECT_ID' not in path.read_text(encoding='utf-8-sig')
            if not ready:
                files=choose_files(credentials=True)
                if not files:print('已取消；原凭证没有改动。');return
                path=Path(files[0])
        Vault().import_file(path)
        print('Vertex AI 信息已导入并使用当前 Windows 用户加密。没有发送模型请求。')
    elif command=='check':check()
    elif command=='stop':
        for name in ('gateway','gateway_mixed'):
            subprocess.run([str(python_executable()),'-B',str(ROOT/name/'manage.py'),'stop'],check=True,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    else:raise ValueError('Unknown command')

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError) as e:print(str(e),file=sys.stderr);sys.exit(1)
    except Exception:print('操作失败，请检查文件路径、运行环境和权限；未显示私有信息。',file=sys.stderr);sys.exit(1)
