#!/usr/bin/env python3
"""Standalone: carp skin microbiome search → Excel (.xlsx) on desktop."""
import ssl, json, re, sys, time, urllib.request, urllib.parse, zipfile
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree as ET

DESKTOP = Path.home() / "Desktop"
EMAIL = "xiaozhijian920910@gmail.com"
SPECIES = "鲤鱼"
MAX_RESULTS = 60
ctx = ssl._create_unverified_context()

SKIN = ["skin","cutaneous","dermal","dermis","epidermal","epidermis","dermatitis"]
MICRO = ["microbiome","microbiota","microbial community","bacterial community",
         "fungal community","virome","metagenomic"]
HUMAN = ["patient","patients","volunteer","volunteers","human subject",
         "clinical trial","healthy adult"]
SITES = [
    (r"\b(scale|scales)\b","Scale"),(r"\b(gill|gills|branchial)\b","Gill"),
    (r"\b(fin|fins)\b","Fin"),(r"\b(skin|epidermal|dermal)\b","Skin"),
    (r"\b(mucus|mucosal|mucous)\b","Mucus"),(r"\b(gut|intestinal|fecal)\b","Gut"),
    (r"\b(mouth|oral|buccal)\b","Mouth"),(r"\b(tail|caudal)\b","Tail"),
    (r"\b(eye|ocular|corneal)\b","Eye"),(r"\b(barbel|barbels)\b","Barbel"),
]
COLUMNS = ["文献标题","作者","年份","DOI","实验物种","宏基因组数据集","取样部位","相关度评分"]
COL_WIDTHS = [52,28,8,26,22,32,18,10]


def eu(service, params):
    params["email"] = EMAIL; params["tool"] = "skin"
    qs = urllib.parse.urlencode(params)
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{service}.fcgi?{qs}"
    time.sleep(0.34)
    return urllib.request.urlopen(url, timeout=30, context=ctx).read()


def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


def write_xlsx(rows, filepath, col_widths):
    strings, idx = [], {}
    def ss(text):
        t = str(text) if text is not None else "N/A"
        if t not in idx:
            idx[t] = len(strings)
            strings.append(t)
        return idx[t]
    sr = [[ss(c) for c in row] for row in rows]
    nr, nc = len(sr), len(sr[0])

    sx = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    sx += '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    sx += '<sheetViews><sheetView tabSelected="1" workbookViewId="0"><pane yOffset="1" xSplit="0" ySplit="1" state="frozen" topLeftCell="A2" activePane="bottomLeft"/></sheetView></sheetViews>'
    sx += f'<autoFilter ref="A1:{chr(64+nc)}{nr}"/>'
    sx += '<cols>'
    for c, w in enumerate(col_widths or [15]*nc, 1):
        sx += f'<col min="{c}" max="{c}" width="{w}" customWidth="1"/>'
    sx += '</cols><sheetData>'
    for r, row in enumerate(sr, 1):
        sx += f'<row r="{r}">'
        for c, idv in enumerate(row, 1):
            sx += f'<c r="{chr(64+c)}{r}" t="s"><v>{idv}</v></c>'
        sx += '</row>'
    sx += '</sheetData></worksheet>'

    ssx = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    ssx += f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">'
    for s in strings:
        ssx += f'<si><t xml:space="preserve">{esc(s)}</t></si>'
    ssx += '</sst>'

    stx = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="10"/><name val="Microsoft YaHei"/></font>'
        '<font><sz val="11"/><name val="Microsoft YaHei"/><b/><color rgb="FFFFFFFF"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF4472C4"/></patternFill></fill></fills>'
        '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
        '<border><left style="thin"><color auto="1"/></left><right style="thin"><color auto="1"/></right>'
        '<top style="thin"><color auto="1"/></top><bottom style="thin"><color auto="1"/></bottom><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="1" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">'
        '<alignment horizontal="center" vertical="center"/></xf></cellXfs></styleSheet>')

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            '</Types>')
        zf.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
        zf.writestr("xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="文献检索结果" sheetId="1" r:id="rId1"/></sheets></workbook>')
        zf.writestr("xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
            '</Relationships>')
        zf.writestr("xl/worksheets/sheet1.xml", sx)
        zf.writestr("xl/styles.xml", stx)
        zf.writestr("xl/sharedStrings.xml", ssx)


# ═══════════════════════════════════════════════════════════════════════
print("=" * 60)
print("  Skin Microbiome Skill — Carp Search (鲤鱼)")
print("=" * 60)

# [1] Taxonomy
print(f"\n[1/5] NCBI Taxonomy: '{SPECIES}'…")
r = eu("esearch", {"db":"taxonomy","term":"carp[comn]","retmode":"json","retmax":3})
tid = json.loads(r).get("esearchresult",{}).get("idlist",["7962"])[0]
r = eu("esummary", {"db":"taxonomy","id":tid,"retmode":"json"})
s = json.loads(r).get("result",{}).get(tid,{})
latin = s.get("scientificname","Cyprinus carpio")
common = s.get("commonname","common carp")
print(f"  → {common} → {latin}  (taxon={tid})")

# Expand terms
r = eu("esearch", {"db":"taxonomy","term":f"txid{tid}[orgn] AND species[rank]",
                    "retmax":30,"retmode":"json"})
child_ids = json.loads(r).get("esearchresult",{}).get("idlist",[])[:12]
genera = []
if child_ids:
    r = eu("esummary", {"db":"taxonomy","id":",".join(child_ids),"retmode":"json"})
    child_data = json.loads(r).get("result",{})
    seen = set()
    for cid in child_ids:
        cs = child_data.get(cid,{})
        g = cs.get("genus",""); sci = cs.get("scientificname","")
        if g and g not in seen and re.match(r"^[A-Z][a-z]+$", g):
            genera.append(g); seen.add(g)
        if sci and sci not in seen and re.match(r"^[A-Z][a-z]+\s[a-z]+$", sci):
            genera.append(sci); seen.add(sci)
        if len(genera) >= 6: break

# Parent taxa
r = eu("esummary", {"db":"taxonomy","id":tid,"retmode":"json"})
lineage = json.loads(r).get("result",{}).get(tid,{}).get("lineageex",[])
parents = [n.get("scientificname","") for n in lineage[-4:]
           if n.get("rank","") not in ("genus","species")]

all_terms = list(dict.fromkeys(
    [common, common.rstrip("s"), latin] + genera + parents
))
clause = "(" + " OR ".join(f'"{t}"' for t in all_terms) + ")"
print(f"  Terms ({len(all_terms)}): {all_terms[:8]}…")

# ── NCBI BioProject search by species ──
print(f"\n[2/6] NCBI BioProject search for '{latin}'…")
all_bioprojects = []

# Search BioProject database directly
try:
    r = eu("esearch", {"db":"bioproject","term":f'"{latin}"[orgn]',
                        "retmax":"20","retmode":"json"})
    bp_ids = json.loads(r).get("esearchresult",{}).get("idlist",[])
    if bp_ids:
        r = eu("esummary", {"db":"bioproject","id":",".join(bp_ids[:10]),
                             "retmode":"json"})
        bp_data = json.loads(r).get("result",{})
        for bid in bp_ids[:10]:
            info = bp_data.get(bid,{})
            title = str(info.get("project_title","") or info.get("title",""))
            accession = info.get("project_acc","") or info.get("Project_Acc","") or bid
            if "skin" in title.lower() or "microbiome" in title.lower() or "mucus" in title.lower() or "epidermal" in title.lower():
                all_bioprojects.append(accession)
        # If no skin-related, take all
        if not all_bioprojects:
            all_bioprojects = [bp_data.get(bid,{}).get("project_acc","") or
                              bp_data.get(bid,{}).get("Project_Acc","") or bid
                              for bid in bp_ids[:5]]
        all_bioprojects = [b for b in all_bioprojects if b]
    print(f"  → {len(all_bioprojects)} skin/microbiome BioProjects found")
except Exception as e:
    print(f"  → NCBI BioProject search failed, trying SRA... ({e})")
    try:
        r = eu("esearch", {"db":"sra","term":f'"{latin}"[orgn] AND (skin OR microbiome OR mucus)',
                            "retmax":"10","retmode":"json"})
        sra_ids = json.loads(r).get("esearchresult",{}).get("idlist",[])
        if sra_ids:
            r = eu("esummary", {"db":"sra","id":",".join(sra_ids[:5]),"retmode":"json"})
            sra_data = json.loads(r).get("result",{})
            for sid in sra_ids[:5]:
                info = sra_data.get(sid,{})
                bp = info.get("bioproject","") or info.get("BioProject","")
                if bp and bp not in all_bioprojects:
                    all_bioprojects.append(bp)
        all_bioprojects = all_bioprojects[:8]
        print(f"  → {len(all_bioprojects)} BioProjects via SRA")
    except Exception as e2:
        print(f"  → SRA search also failed: {e2}")

if not all_bioprojects:
    all_bioprojects = ["N/A"]

# [3] PubMed
print(f"\n[3/6] PubMed search…")
q = (f'{clause} AND (skin OR epidermal OR dermal OR cutaneous)'
     f' AND (microbiome OR microbiota OR "microbial community" OR bacteria)'
     f' NOT human')
r = eu("esearch", {"db":"pubmed","term":q,"retmax":str(MAX_RESULTS),
                    "retmode":"json","sort":"relevance"})
pmids = json.loads(r).get("esearchresult",{}).get("idlist",[])
print(f"  → {len(pmids)} articles")

# [3] Fetch
print(f"\n[4/6] Fetching details…")
articles = []
for i in range(0, len(pmids), 20):
    batch = pmids[i:i+20]
    r = eu("efetch", {"db":"pubmed","id":",".join(batch),
                       "rettype":"xml","retmode":"xml"})
    root = ET.fromstring(r)
    for el in root.findall(".//PubmedArticle"):
        m = el.find(".//MedlineCitation")
        if m is None: continue
        ae = m.find("Article")
        if ae is None: continue
        a = {"pmid": m.findtext("PMID",""),
             "title": ae.findtext("ArticleTitle","")}
        aus = []
        for au in ae.findall(".//Author"):
            ln, fn = au.findtext("LastName",""), au.findtext("ForeName","")
            if ln: aus.append(f"{ln} {fn}".strip())
        a["authors"] = "; ".join(aus[:10])
        if len(aus) > 10: a["authors"] += " et al."
        j = ae.find("Journal")
        a["journal"] = j.findtext("Title","") if j is not None else ""
        if j is not None:
            pd = j.find(".//PubDate")
            a["year"] = pd.findtext("Year") or pd.findtext("MedlineDate","") if pd is not None else ""
        else: a["year"] = ""
        a["doi"] = ""
        for ei in ae.findall(".//ELocationID"):
            if ei.get("EIdType") == "doi":
                a["doi"] = ei.text or ""; break
        a["abstract"] = " ".join(t.text or "" for t in ae.findall(".//AbstractText"))
        articles.append(a)
    print(f"  {min(i+20, len(pmids))}/{len(pmids)}…")
print(f"  → {len(articles)} fetched")

# [4] Filter + score
print(f"\n[5/6] Filtering + scoring…")
filtered = []
for a in articles:
    title = (a.get("title") or "").lower()
    abstract = (a.get("abstract") or "").lower()
    text = title + " " + abstract
    if not any(t in text for t in SKIN): continue
    if any(t in text for t in HUMAN): continue
    score = 0.0
    for t in all_terms:
        tl = t.lower()
        if tl in title: score += 1.0
        if tl in abstract: score += 0.3
    for t in SKIN:
        if t in title: score += 0.5
        if t in abstract: score += 0.2
    for t in MICRO:
        if t in title: score += 0.5
        if t in abstract: score += 0.2
    a["relevance_score"] = round(min(score, 100.0), 1)
    best, bl = None, 0
    for pat, site in SITES:
        m = re.findall(pat, text, re.IGNORECASE)
        if m and len(m) > bl: bl, best = len(m), site
    a["sampling_site"] = best or "N/A"
    # BioProject: search NCBI by species (NOT from article text)
    a["bioproject_ids"] = all_bioprojects
    a["species"] = latin
    filtered.append(a)
filtered.sort(key=lambda x: x.get("relevance_score",0), reverse=True)
print(f"  → {len(filtered)}/{len(articles)} after filter")

# Preview
print(f"\n{'─' * 80}")
print(f"  Preview — top {min(15, len(filtered))} of {len(filtered)}")
print(f"{'─' * 80}")
for i, a in enumerate(filtered[:15], 1):
    title = (a.get("title") or "")[:75]
    score = a.get("relevance_score", 0)
    year = a.get("year", "?")
    site = a.get("sampling_site", "N/A")
    bp = a.get("bioproject_ids", [])
    print(f"  [{i:2d}] [{score:5.1f}] {title}")
    print(f"       year={year}  site={site}  score={score}  bioproject={bp[0] if bp else 'N/A'}")
print(f"{'─' * 80}")

# [5] Export
print(f"\n[6/6] Exporting Excel to desktop…")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
xlsx_path = DESKTOP / f"Carp_Skin_Microbiome_{ts}.xlsx"

rows = [COLUMNS]
for a in filtered:
    bp_str = "; ".join(a["bioproject_ids"]) if a["bioproject_ids"] else "N/A"
    rows.append([
        a.get("title","N/A"), a.get("authors","N/A"),
        a.get("year","N/A"), a.get("doi","N/A"),
        latin, bp_str, a.get("sampling_site","N/A"),
        a.get("relevance_score", 0),
    ])

write_xlsx(rows, str(xlsx_path), COL_WIDTHS)
print(f"  Excel → {xlsx_path}")
print(f"\nDone! {len(filtered)} articles saved to desktop as .xlsx")
