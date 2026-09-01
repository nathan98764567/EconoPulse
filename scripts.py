import json, re, html, os, urllib.parse, urllib.request, hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
from html.parser import HTMLParser

ROOT=os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT,'sources.json'),encoding='utf-8') as f: CFG=json.load(f)
OUT=os.path.join(ROOT,'data','news.json'); UA='EconoPulse/2.2 (+GitHub Actions)'

def get(url,timeout=30):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()
def clean(s):
    s=html.unescape(s or '');s=re.sub(r'<[^>]+>',' ',s);return re.sub(r'\s+',' ',s).strip()
def parse_date(v):
    if not v:return None
    try:return parsedate_to_datetime(v.strip()).astimezone(timezone.utc).isoformat()
    except Exception:pass
    try:return datetime.fromisoformat(v.strip().replace('Z','+00:00')).astimezone(timezone.utc).isoformat()
    except Exception:return None
def text_child(el,names):
    wanted={x.lower() for x in names}
    for x in list(el.iter()):
        if x.tag.split('}')[-1].lower() in wanted and x.text:return clean(x.text)
    return ''
def link_child(el):
    for x in list(el.iter()):
        if x.tag.split('}')[-1].lower()=='link':
            if x.attrib.get('href'):return x.attrib['href']
            if x.text and x.text.strip():return x.text.strip()
    return ''
def infer_sector(text):
    rules=[('Technologie',r'\b(ai|artificial intelligence|semiconductor|chip|software|cloud|technology|cyber|quantum)\b'),('Pharmaceutique',r'\b(pharma|drug|medicine|biotech|clinical trial|fda|vaccine|health)\b'),('Finance',r'\b(bank|banking|finance|financial|interest rate|fed|central bank|bond|credit|mortgage)\b'),('Immobilier',r'\b(real estate|housing|home prices|mortgage|property|construction)\b'),('Spatial',r'\b(space|satellite|rocket|launch|aerospace|nasa)\b'),('Énergie',r'\b(oil|gas|energy|electricity|solar|wind|nuclear)\b'),('Politique',r'\b(president|government|election|senate|congress|minister|parliament|executive order|policy)\b'),('Économie',r'\b(economy|inflation|gdp|gross domestic product|recession|employment|unemployment|tariff|trade)\b')]
    for n,p in rules:
        if re.search(p,text):return n
    return 'Général'
def entities_in(text):
    names={'NVIDIA':'nvidia','AMD':' amd ','Apple':'apple','Microsoft':'microsoft','Amazon':'amazon','Tesla':'tesla','Alphabet':'google','Meta':'meta','TSMC':'tsmc','OpenAI':'openai','JPMorgan':'jpmorgan','Bank of America':'bank of america','Pfizer':'pfizer','Eli Lilly':'eli lilly','Novo Nordisk':'novo nordisk','Lockheed Martin':'lockheed martin','Rocket Lab':'rocket lab'}
    p=' '+text.lower()+' ';return [k for k,v in names.items() if v in p]
def impact_flag(text):return 'important' if re.search(r'\b(rate decision|interest rate|inflation|tariff|sanction|ban|approval|recall|earnings|merger|acquisition|regulation|executive order|election|war)\b',text) else 'à surveiller'
def article(title,summary,source,date,url,stype,default_sector):
    text=(title+' '+summary).lower();sector=infer_sector(text);return {'id':hashlib.sha256((source+'|'+url).encode()).hexdigest()[:16],'title':title[:240],'summary':summary[:500],'source':source,'sourceType':stype,'sector':sector if sector!='Général' else default_sector,'published':parse_date(date) or datetime.now(timezone.utc).isoformat(),'url':url,'impact':impact_flag(text),'entities':entities_in(text)}
def parse_feed(raw,source):
    try:root=ET.fromstring(raw)
    except Exception as e:print('XML parse error',source['name'],e);return []
    out=[]
    for item in [x for x in root.iter() if x.tag.split('}')[-1].lower() in ('item','entry')][:100]:
        t=text_child(item,['title']);u=link_child(item);d=text_child(item,['pubDate','published','updated','date']);s=text_child(item,['description','summary','content','encoded'])
        if t and u:out.append(article(t,s,source['name'],d,u,source['type'],source['default_sector']))
    return out
class SimpleHTML(HTMLParser):
    def __init__(self):super().__init__();self.items=[];self.in_a=False;self.buf=[];self.href=''
    def handle_starttag(self,tag,attrs):
        if tag=='a':a=dict(attrs);self.in_a=True;self.buf=[];self.href=a.get('href','')
    def handle_data(self,data):
        if self.in_a:self.buf.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.in_a:
            t=clean(' '.join(self.buf))
            if t and self.href:self.items.append({'title':t,'url':self.href})
            self.in_a=False;self.buf=[];self.href=''
def web_items(source):
    p=SimpleHTML();p.feed(get(source['url']).decode('utf-8','ignore'));out=[]
    for x in p.items[:80]:
        u=x['url'];u='https://www.whitehouse.gov'+u if u.startswith('/') else u
        if '/presidential-actions/' in u:out.append(article(x['title'],'Source officielle : action publiée sur le site de la Maison-Blanche.',source['name'],'',u,source['type'],source['default_sector']))
    return out
def gdelt():
    out=[]
    for q in CFG['gdelt']['queries']:
        u='https://api.gdeltproject.org/api/v2/doc/doc?'+urllib.parse.urlencode({'query':q,'mode':'artlist','maxrecords':CFG['gdelt']['maxrecords'],'format':'json','sort':'datedesc'})
        try:
            data=json.loads(get(u))
            for x in data.get('articles',[]):
                t=x.get('title','');link=x.get('url','')
                if t and link:out.append(article(t,'',x.get('domain','GDELT'),'','%s'%link,'agrégé','Général'))
        except Exception as e:print('GDELT error',e)
    return out
POS=re.compile(r'\b(rate cut|lower rates|falling rates|approval|approved|record sales|strong earnings|beat estimates|contract win|government funding|subsidy|demand rises|price increase|acquisition|growth|expansion|investment|partnership|orders|successful trial)\b')
NEG=re.compile(r'\b(rate hike|higher rates|rising rates|rejection|rejected|recall|miss estimates|weak earnings|layoffs|sanction|ban|tariff|trade restriction|investigation|lawsuit|demand falls|decline|slump|warning|delay|failure|losses|cut forecast|downgrade)\b')
def analyze(a):
    text=(a.get('title','')+' '+a.get('summary','')).lower();score=min(2,len(POS.findall(text)))*28-min(2,len(NEG.findall(text)))*28;broad=any(x in text for x in ['interest rate','inflation','tariff','trade','regulation','executive order','election','central bank','recession'])
    if broad:score+=12
    if a.get('sector') in ('Politique','Économie','Finance'):score+=5
    score=max(-100,min(100,score));direction='positif' if score>=30 else 'négatif' if score<=-30 else 'neutre';magnitude='élevé' if abs(score)>=55 or broad else 'moyen' if abs(score)>=25 else 'faible';confidence=min(95,45+abs(score)+(15 if a.get('entities') else 0)+(10 if broad else 0))
    wins=a.get('entities',[]) if score>0 else [];risks=a.get('entities',[]) if score<0 else [];desc={'positif':'plutôt favorable','négatif':'plutôt défavorable','neutre':'encore difficile à trancher'}[direction]
    expl=f'Impact {desc}, intensité {magnitude}. Secteur principal : {a.get("sector")}.'
    if broad:expl+=' Le sujet peut aussi avoir des effets indirects sur d’autres secteurs.'
    if wins:expl+=' Entreprises potentiellement favorisées : '+', '.join(wins[:6])+'.'
    if risks:expl+=' Entreprises potentiellement exposées : '+', '.join(risks[:6])+'.'
    a['analysis']={'score':score,'direction':direction,'magnitude':magnitude,'confidence':round(confidence),'explanation':expl,'potentialWinners':wins[:6],'potentialRisks':risks[:6],'disclaimer':'Analyse automatique indicative, pas une recommandation financière.'}
all_articles=[]
for s in CFG.get('rss',[]):
    try:all_articles+=parse_feed(get(s['url']),s)
    except Exception as e:print('RSS error',s['name'],e)
for s in CFG.get('web',[]):
    try:all_articles+=web_items(s)
    except Exception as e:print('WEB error',s['name'],e)
try:all_articles+=gdelt()
except Exception as e:print('GDELT fatal',e)
seen=set();final=[]
for a in sorted(all_articles,key=lambda x:x.get('published',''),reverse=True):
    k=a['url'].split('#')[0].rstrip('/')
    if k in seen:continue
    seen.add(k);analyze(a);final.append(a)
final=final[:500]
payload={'updatedAt':datetime.now(timezone.utc).isoformat(),'articles':final}
with open(OUT,'w',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2)
print('Wrote',len(final),'articles')
