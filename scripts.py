import json, re, html, os, urllib.parse, urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "data", "news.json")

UA = "EconoPulse/2.1 (+GitHub Actions)"

def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_date(v):
    if not v: return None
    v = v.strip()
    try: return parsedate_to_datetime(v).astimezone(timezone.utc).isoformat()
    except Exception: pass
    try:
        return datetime.fromisoformat(v.replace("Z","+00:00")).astimezone(timezone.utc).isoformat()
    except Exception:
        return None

def text_child(el, names):
    for n in names:
        x = el.find(n)
        if x is not None and x.text:
            return clean(x.text)
    # namespace-insensitive fallback
    for x in list(el):
        tag = x.tag.split("}")[-1].lower()
        if tag in names and x.text:
            return clean(x.text)
    return ""

def link_child(el):
    # RSS
    x = el.find("link")
    if x is not None:
        if x.text and x.text.strip(): return x.text.strip()
        if x.attrib.get("href"): return x.attrib["href"]
    for x in list(el):
        tag = x.tag.split("}")[-1].lower()
        if tag == "link" and x.attrib.get("href"):
            return x.attrib["href"]
    # Atom alternate
    for x in list(el):
        if x.tag.split("}")[-1].lower() == "link" and x.attrib.get("rel","alternate") == "alternate":
            return x.attrib.get("href","")
    return ""

def parse_feed(raw, source):
    try:
        root = ET.fromstring(raw)
    except Exception:
        return []
    out=[]
    root_name = root.tag.split("}")[-1].lower()
    items = list(root) if root_name in ("rss","rdf") else []
    if root_name == "feed":
        items = [x for x in list(root) if x.tag.split("}")[-1].lower() == "entry"]
    else:
        # RSS channel/items
        items = [x for x in root.iter() if x.tag.split("}")[-1].lower() in ("item",)]
    for item in items[:100]:
        title = text_child(item, ["title"])
        summary = text_child(item, ["description","summary","content","encoded"])
        url = link_child(item)
        date = text_child(item, ["pubDate","published","updated","date"])
        if not title or not url: continue
        out.append(article(title, summary, source, date, url))
    return out

def article(title, summary, source, date, url, source_type=None, sector=None):
    text=(title+" "+summary).lower()
    sector = sector or infer_sector(text)
    impact = infer_impact(text, sector)
    return {
        "id": hashlib_id(source+"|"+url),
        "title": title[:240],
        "summary": summary[:500],
        "source": source,
        "sourceType": source_type or "officiel",
        "sector": sector,
        "published": parse_date(date) or datetime.now(timezone.utc).isoformat(),
        "url": url,
        "impact": impact,
        "entities": entities_in(text)
    }

def hashlib_id(s):
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def infer_sector(text):
    rules=[
        ("Technologie", r"\b(ai|artificial intelligence|semiconductor|chip|software|cloud|technology|cyber|quantum)\b"),
        ("Pharmaceutique", r"\b(pharma|drug|medicine|biotech|clinical trial|fda|vaccine|health)\b"),
        ("Finance", r"\b(bank|banking|finance|financial|interest rate|fed|central bank|bond|credit|mortgage)\b"),
        ("Immobilier", r"\b(real estate|housing|home prices|mortgage|property|construction)\b"),
        ("Spatial", r"\b(space|satellite|rocket|launch|aerospace|nasa)\b"),
        ("Énergie", r"\b(oil|gas|energy|electricity|solar|wind|nuclear)\b"),
        ("Politique", r"\b(president|government|election|elections|senate|congress|minister|parliament|executive order|policy)\b"),
        ("Économie", r"\b(economy|inflation|gdp|gross domestic product|recession|employment|unemployment|tariff|trade)\b")
    ]
    for name, pat in rules:
        if re.search(pat,text): return name
    return "Général"

def infer_impact(text, sector):
    major = r"\b(rate decision|interest rate|inflation|tariff|sanction|ban|approval|recall|earnings|merger|acquisition|regulation|executive order|election|war)\b"
    if re.search(major,text): return "important"
    return "à surveiller"

def entities_in(text):
    names = {
        "NVIDIA":"nvidia","AMD":" amd ","Apple":"apple","Microsoft":"microsoft","Amazon":"amazon",
        "Tesla":"tesla","Alphabet":"google","Meta":"meta","TSMC":"tsmc","OpenAI":"openai",
        "Bank of America":"bank of america","JPMorgan":"jpmorgan","Pfizer":"pfizer","Eli Lilly":"eli lilly",
        "Novo Nordisk":"novo nordisk","Lockheed Martin":"lockheed martin","Rocket Lab":"rocket lab"
    }
    found=[]
    for label,key in names.items():
        if key in (" amd ",):
            if key in " "+text+" ": found.append(label)
        elif key in text: found.append(label)
    return found

class SimpleHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.items=[]; self.in_h=False; self.in_a=False; self.cur=None; self.href=""; self.buf=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ("h2","h3","h4") and self.cur is None:
            self.in_h=True; self.buf=[]
        if tag=="a" and self.cur is None:
            self.in_a=True; self.href=a.get("href",""); self.buf=[]
    def handle_data(self,data):
        if self.in_h or self.in_a: self.buf.append(data)
    def handle_endtag(self,tag):
        if self.in_h and tag in ("h2","h3","h4"):
            t=clean(" ".join(self.buf))
            if t: self.cur={"title":t,"url":self.href}
            self.in_h=False
        elif tag=="a" and self.in_a:
            t=clean(" ".join(self.buf))
            if t and self.href: self.items.append({"title":t,"url":self.href})
            self.in_a=False; self.href=""; self.buf=[]

def web_items(url, source, sector):
    raw=get(url).decode("utf-8","ignore")
    p=SimpleHTML(); p.feed(raw)
    base="https://www.whitehouse.gov"
    out=[]
    for x in p.items[:60]:
        href=x["url"]
        if href.startswith("/"): href=base+href
        if "presidential" not in href: continue
        out.append(article(x["title"], "Source officielle : action présidentielle publiée sur le site de la Maison-Blanche.", source, "", href, "officiel", sector))
    return out

def gdelt():
    out=[]
    for q in CFG["gdelt"]["queries"]:
        url="https://api.gdeltproject.org/api/v2/doc/doc?"+urllib.parse.urlencode({
            "query": q, "mode":"artlist", "maxrecords":CFG["gdelt"]["maxrecords"],
            "format":"json", "sort":"datedesc"
        })
        try:
            data=json.loads(get(url))
            for x in data.get("articles",[]):
                title=x.get("title",""); link=x.get("url","")
                if title and link:
                    out.append(article(title, x.get("seendate",""), x.get("domain","GDELT"), x.get("seendate",""), link, "agrégé"))
        except Exception as e:
            print("GDELT error", q, e)
    return out

all_articles=[]
for s in CFG["rss"]:
    try:
        all_articles += parse_feed(get(s["url"]), s["name"])
        for a in all_articles[-100:]:
            a["sourceType"]=s["type"]
            if a["sector"]=="Général": a["sector"]=s["default_sector"]
    except Exception as e:
        print("RSS error",s["name"],e)

for s in CFG["web"]:
    try: all_articles += web_items(s["url"], s["name"], s["default_sector"])
    except Exception as e: print("WEB error",s["name"],e)

try: all_articles += gdelt()
except Exception as e: print("GDELT fatal",e)

# Deduplicate by normalized URL/title
seen=set(); final=[]
for a in sorted(all_articles, key=lambda x:x.get("published",""), reverse=True):
    key=(a["url"].split("#")[0].rstrip("/") or a["title"].lower())
    if key in seen: continue
    seen.add(key); final.append(a)

final=final[:500]

# -----------------------------
# ÉconoPulse Impact Analysis V2.2
# -----------------------------
DIRECTION_POSITIVE = [
    r"\b(rate cut|lower rates|falling rates|approval|approved|record sales|strong earnings|beat estimates|contract win|government funding|subsidy|demand rises|price increase|acquisition|boost|growth|expansion|investment|partnership|orders|successful trial)\b",
]
DIRECTION_NEGATIVE = [
    r"\b(rate hike|higher rates|rising rates|rejection|rejected|recall|miss estimates|weak earnings|layoffs|sanction|ban|tariff|trade restriction|investigation|lawsuit|demand falls|decline|slump|warning|delay|failure|losses|cut forecast|downgrade)\b",
]

COMPANY_PROFILES = {
    "NVIDIA": ["ai","semiconductor","chip","data center"],
    "AMD": ["ai","semiconductor","chip","data center"],
    "Apple": ["consumer","smartphone","tariff","supply chain"],
    "Microsoft": ["ai","cloud","software","enterprise"],
    "Amazon": ["consumer","cloud","retail","logistics"],
    "Tesla": ["ev","electric vehicle","battery","autos"],
    "TSMC": ["semiconductor","chip","ai","fab"],
    "JPMorgan": ["bank","interest rate","credit","yield"],
    "Bank of America": ["bank","interest rate","credit","yield"],
    "Pfizer": ["drug","clinical trial","fda","pharma"],
    "Eli Lilly": ["drug","obesity","fda","pharma"],
    "Novo Nordisk": ["drug","obesity","fda","pharma"],
    "Lockheed Martin": ["defense","space","government contract"],
    "Rocket Lab": ["space","satellite","launch","government contract"],
}

def analyze_impact(title, summary, sector, entities):
    text = (title + " " + summary).lower()
    pos = sum(1 for pat in DIRECTION_POSITIVE if re.search(pat, text))
    neg = sum(1 for pat in DIRECTION_NEGATIVE if re.search(pat, text))
    broad = any(x in text for x in [
        "interest rate","inflation","tariff","trade","regulation",
        "executive order","election","central bank","recession"
    ])
    score = (min(pos,2) * 28) - (min(neg,2) * 28)
    if broad:
        score += 12
    if sector in ("Politique","Économie","Finance"):
        score += 5
    score = max(-100, min(100, score))
    direction = "positif" if score >= 30 else "négatif" if score <= -30 else "neutre"
    magnitude = "élevé" if abs(score) >= 55 or broad else "moyen" if abs(score) >= 25 else "faible"
    confidence = min(95, 45 + abs(score) + (15 if entities else 0) + (10 if broad else 0))
    winners, risks = [], []
    for company in entities:
        keys = COMPANY_PROFILES.get(company, [])
        hits = sum(1 for k in keys if k in text)
        if hits:
            if score > 0:
                winners.append(company)
            elif score < 0:
                risks.append(company)
    d = {"positif":"plutôt favorable", "négatif":"plutôt défavorable", "neutre":"encore difficile à trancher"}[direction]
    explanation = f"Impact {d}, intensité {magnitude}. Secteur principal : {sector}."
    if broad:
        explanation += " Le sujet peut aussi avoir des effets indirects sur d'autres secteurs."
    if winners:
        explanation += " Entreprises potentiellement favorisées : " + ", ".join(winners) + "."
    if risks:
        explanation += " Entreprises potentiellement exposées : " + ", ".join(risks) + "."
    return {
        "score": score,
        "direction": direction,
        "magnitude": magnitude,
        "confidence": round(confidence),
        "explanation": explanation,
        "potentialWinners": winners[:6],
        "potentialRisks": risks[:6],
        "disclaimer": "Analyse automatique indicative, pas une recommandation financière."
    }

for a in final:
    a["analysis"] = analyze_impact(
        a.get("title",""),
        a.get("summary",""),
        a.get("sector","Général"),
        a.get("entities",[])
    )

payload={"updatedAt":datetime.now(timezone.utc).isoformat(),"articles":final}
with open(OUT,"w",encoding="utf-8") as f: json.dump(payload,f,ensure_ascii=False,indent=2)
print("Wrote",len(final),"articles")
