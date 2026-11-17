import sys,os,json,traceback,re
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)));sys.path.insert(0,R+'/monitor')
import monitor as m, requests, extrator
s=requests.Session()
for u in json.load(open(R+'/tools/urls_teste.json')):
    try:
        html=m.fetch(u,s)
        if isinstance(html,bytes): html=html.decode('utf-8','replace')
        d=extrator.extrair(html,u)
        jl=re.findall(r'"streetAddress"\s*:\s*"([^"]{2,80})"',html)[:3]
        print(json.dumps({"u":u[-70:],"len":len(html),"end":d.get("endereco"),"num":d.get("numero"),"emp":d.get("empreendimento"),"orig":d.get("endereco_origem"),"jl":jl},ensure_ascii=False))
    except Exception:
        print("ERRO",u[-60:],traceback.format_exc()[-500:].replace("\n"," | "))
