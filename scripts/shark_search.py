#!/usr/bin/env python3
"""Standalone: optimized shark skin microbiome search → Excel (.xlsx) on desktop.
Boolean keyword query + NCBI Taxonomy term expansion + relevance scoring.
Only uses Python stdlib — generates real .xlsx via ZIP + XML.
"""
import ssl, json, re, time, urllib.request, urllib.parse, zipfile
from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree as ET

# ── Config ────────────────────────────────────────────────────────────
DESKTOP = Path.home() / "Desktop"
EMAIL = "xiaozhijian920910@gmail.com"
SPECIES_INPUT = "鲨鱼"
MAX_RESULTS = 100
ctx = ssl._create_unverified_context()

_SKIN_TERMS = [
    "skin", "cutaneous", "dermal", "dermis", "epidermal", "epidermis",
    "dermatitis", "dermatology", "dermatological", "eczema", "atopic",
    "seborrheic", "sebaceous", "keratinocyte", "melanocyte",
]
_MICROBIOME_TERMS = [
    "microbiome", "microbiota", "microbial community", "microbial communities",
    "bacterial community", "fungal community", "virome", "metagenomic",
]
_HUMAN_EXCLUSIVE = [
    "patient", "patients", "volunteer", "volunteers", "human subject",
    "clinical trial", "healthy adult", "healthy adults",
]

_SAMPLING_SITE_PATTERNS = [
    (r"\b(ear|ears|auricular|otic)\b", "Ear"),
    (r"\b(nose|nasal|nares|nostril)\b", "Nose"),
    (r"\b(forehead|frontal)\b", "Forehead"),
    (r"\b(scalp|scalps)\b", "Scalp"),
    (r"\b(axilla|axillae|armpit|axillary)\b", "Axilla"),
    (r"\b(neck|cervical|nape)\b", "Neck"),
    (r"\b(shoulder|shoulders|deltoid)\b", "Shoulder"),
    (r"\b(back|dorsal trunk|interscapular)\b", "Back"),
    (r"\b(chest|thoracic|sternal|pectoral)\b", "Chest"),
    (r"\b(abdomen|abdominal|belly|ventral)\b", "Abdomen"),
    (r"\b(groin|inguinal)\b", "Groin"),
    (r"\b(perineum|perineal|perianal|anal)\b", "Perineum"),
    (r"\b(forearm|volar forearm|antecubital)\b", "Forearm"),
    (r"\b(hand|hands|palmar|interdigital)\b", "Hand"),
    (r"\b(thigh|thighs|femoral)\b", "Thigh"),
    (r"\b(calf|calves|sural|lower leg|popliteal)\b", "Calf"),
    (r"\b(foot|feet|plantar|toe|toes)\b", "Foot"),
    (r"\b(paw|paws|footpad|footpads)\b", "Paw"),
    (r"\b(tail|tail base|rump)\b", "Tail"),
    (r"\b(fin|fins|dorsal fin|pectoral fin|pelvic fin|caudal fin)\b", "Fin"),
    (r"\b(gill|gills|branchial|opercular|operculum)\b", "Gill"),
    (r"\b(scale|scales|dermal denticle|denticles|placoid)\b", "Scale"),
    (r"\b(snout|rostrum|rostral)\b", "Snout"),
    (r"\b(mouth|oral|buccal|jaw|jaws|mandibular)\b", "Mouth"),
    (r"\b(clasper|claspers)\b", "Clasper"),
]

COLUMNS = ["文献标题", "作者", "年份", "DOI", "实验物种", "宏基因组数据集", "取样部位"]
COL_WIDTHS = [52, 28, 8, 26, 22, 30, 18]


# ── NCBI E-utilities ──────────────────────────────────────────────────
def eutils(service, params):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    params["email"] = EMAIL
    params["tool"] = "skin_microbiome_skill"
    qs = urllib.parse.urlencode(params)
    url = f"{base}{service}.fcgi?{qs}"
    time.sleep(0.34)
    return urllib.request.urlopen(url, timeout=30, context=ctx).read()


# ── .xlsx writer (stdlib: ZIP + SpreadsheetML) ────────────────────────
def _xml_escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_xlsx(rows, filepath, col_widths=None):
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
        ssx += f'<si><t xml:space="preserve">{_xml_escape(s)}</t></si>'
    ssx += '</sst>'
    stx = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="10"/><name val="Microsoft YaHei"/></font>
<font><sz val="11"/><name val="Microsoft YaHei"/><b/><color rgb="FFFFFFFF"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF4472C4"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color auto="1"/></left><right style="thin"><color auto="1"/></right><top style="thin"><color auto="1"/></top><bottom style="thin"><color auto="1"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="1" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf></cellXfs>
</styleSheet>'''
    ct = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    wbr = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>'''
    wb = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="文献检索结果" sheetId="1" r:id="rId1"/></sheets></workbook>'''
    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", wb)
        zf.writestr("xl/_rels/workbook.xml.rels", wbr)
        zf.writestr("xl/worksheets/sheet1.xml", sx)
        zf.writestr("xl/styles.xml", stx)
        zf.writestr("xl/sharedStrings.xml", ssx)


# ═══════════════════════════════════════════════════════════════════════
#  PIPELINE
# ═══════════════════════════════════════════════════════════════════════
print("=" * 60)
print("  Skin Microbiome Skill — Optimized Shark Search")
print("  Boolean keyword query + Taxonomy expansion + Scoring")
print("=" * 60)

# ── [1] Taxonomy lookup + term expansion ──────────────────────────────
print(f"\n[1/6] NCBI Taxonomy lookup: '{SPECIES_INPUT}'…")

# Search taxonomy
resp = eutils("esearch", {"db": "taxonomy", "term": "sharks[comn]", "retmode": "json"})
taxon_ids = json.loads(resp).get("esearchresult", {}).get("idlist", [])
tid = taxon_ids[0]

# ESummary for details
resp = eutils("esummary", {"db": "taxonomy", "id": tid, "retmode": "json"})
summary = json.loads(resp).get("result", {}).get(tid, {})
species_latin = summary.get("scientificname", "Selachii")
common_name = summary.get("commonname", "sharks")
synonyms = summary.get("synonymlist", [])
if isinstance(synonyms, str):
    synonyms = [synonyms] if synonyms else []
print(f"  → {common_name} → {species_latin}  (taxon={tid})")
if synonyms:
    print(f"  Synonyms: {', '.join(synonyms[:5])}")

# Expand to child genera
print("  Expanding search terms (child genera/species)…")
resp = eutils("esearch", {"db": "taxonomy",
    "term": f"txid{tid}[orgn] AND species[rank]",
    "retmax": "50", "retmode": "json", "sort": "relevance"})
child_ids = json.loads(resp).get("esearchresult", {}).get("idlist", [])[:16]
genera = []
if child_ids:
    resp = eutils("esummary", {"db": "taxonomy", "id": ",".join(child_ids), "retmode": "json"})
    child_data = json.loads(resp).get("result", {})
    seen = set()
    for cid in child_ids:
        s = child_data.get(cid, {})
        sci = s.get("scientificname", "")
        genus = s.get("genus", "")
        if sci and sci not in seen:
            genera.append(sci)
            seen.add(sci)
        if genus and genus not in seen:
            genera.append(genus)
            seen.add(genus)
        if len(genera) >= 8:
            break

# Build all search terms
common_variants = [common_name, common_name.rstrip("s")]
if common_name.endswith("s"):
    common_variants.append(common_name[:-1])
else:
    common_variants.append(common_name + "s")
common_variants = list(dict.fromkeys(common_variants))

all_terms = list(dict.fromkeys(
    common_variants + [species_latin] + synonyms + genera
))
boolean_clause = "(" + " OR ".join(f'"{t}"' for t in all_terms) + ")"
print(f"  Terms ({len(all_terms)}): {', '.join(all_terms[:10])}…")
print(f"  Boolean clause: {boolean_clause[:120]}…")

# ── [2] PubMed search ─────────────────────────────────────────────────
print(f"\n[2/6] PubMed search…")
query = (f'{boolean_clause} AND (skin OR dermal OR cutaneous OR epidermal)'
         f' AND (microbiome OR microbiota OR "microbial community" OR metagenomic)'
         f' NOT human')
print(f"  Query: {query[:150]}…")
resp = eutils("esearch", {"db": "pubmed", "term": query, "retmax": str(MAX_RESULTS),
                          "retmode": "json", "sort": "relevance"})
pmids = json.loads(resp).get("esearchresult", {}).get("idlist", [])
print(f"  → {len(pmids)} articles")

# ── [3] Fetch details ─────────────────────────────────────────────────
print(f"\n[3/6] Fetching article details…")
articles = []
for i in range(0, len(pmids), 20):
    batch = pmids[i:i+20]
    resp = eutils("efetch", {"db": "pubmed", "id": ",".join(batch),
                              "rettype": "xml", "retmode": "xml"})
    root = ET.fromstring(resp)
    for el in root.findall(".//PubmedArticle"):
        medline = el.find(".//MedlineCitation")
        if medline is None: continue
        ae = medline.find("Article")
        if ae is None: continue
        art = {"pmid": medline.findtext("PMID", ""),
               "title": ae.findtext("ArticleTitle", "")}
        authors = []
        for au in ae.findall(".//Author"):
            ln, fn = au.findtext("LastName", ""), au.findtext("ForeName", "")
            if ln: authors.append(f"{ln} {fn}".strip())
        art["authors"] = "; ".join(authors[:10])
        if len(authors) > 10: art["authors"] += " et al."
        j = ae.find("Journal")
        art["journal"] = j.findtext("Title", "") if j is not None else ""
        if j is not None:
            pd = j.find(".//PubDate")
            art["year"] = pd.findtext("Year") or pd.findtext("MedlineDate", "") if pd is not None else ""
        else:
            art["year"] = ""
        art["doi"] = ""
        for eid in ae.findall(".//ELocationID"):
            if eid.get("EIdType") == "doi":
                art["doi"] = eid.text or ""; break
        art["abstract"] = " ".join([t.text or "" for t in ae.findall(".//AbstractText")])
        articles.append(art)
    print(f"  {min(i+20, len(pmids))}/{len(pmids)}…")
print(f"  → {len(articles)} fetched")

# ── [4] Filter + score ────────────────────────────────────────────────
print(f"\n[4/6] Filtering + relevance scoring (Boolean keyword)…")
filtered = []
for art in articles:
    title = (art.get("title") or "").lower()
    abstract = (art.get("abstract") or "").lower()
    text = title + " " + abstract

    # Secondary filter
    if not any(t in text for t in _SKIN_TERMS):
        continue
    if any(t in text for t in _HUMAN_EXCLUSIVE):
        continue

    # Score: species +1.0/+0.3, skin +0.5/+0.2, microbiome +0.5/+0.2
    score = 0.0
    for term in all_terms:
        t = term.lower()
        if t in title: score += 1.0
        if t in abstract: score += 0.3
    for term in _SKIN_TERMS:
        if term in title: score += 0.5
        if term in abstract: score += 0.2
    for term in _MICROBIOME_TERMS:
        if term in title: score += 0.5
        if term in abstract: score += 0.2
    art["relevance_score"] = round(min(score, 100.0), 1)

    # Sampling site
    best, best_len = None, 0
    for pat, site in _SAMPLING_SITE_PATTERNS:
        m = re.findall(pat, text, re.IGNORECASE)
        if m and len(m) > best_len: best_len, best = len(m), site
    art["sampling_site"] = best or "N/A"

    # BioProject
    bp_ids = set()
    for pat in [r"PRJNA\d{4,}", r"PRJEB\d{4,}", r"PRJDB\d{4,}"]:
        bp_ids.update(re.findall(pat, art.get("title", "") + " " + art.get("abstract", "")))
    art["bioproject_ids"] = sorted(bp_ids)
    art["species"] = species_latin
    filtered.append(art)

# Sort by score
filtered.sort(key=lambda a: a.get("relevance_score", 0), reverse=True)
print(f"  → {len(filtered)}/{len(articles)} after filter")

# ── [5] Preview ───────────────────────────────────────────────────────
print(f"\n{'─' * 80}")
print(f"  Preview — top {min(15, len(filtered))} of {len(filtered)}  (score|year|site|bioproject)")
print(f"{'─' * 80}")
for i, art in enumerate(filtered[:15], 1):
    title = (art.get("title") or "")[:75]
    score = art.get("relevance_score", 0)
    year = art.get("year", "?")
    site = art.get("sampling_site", "N/A")
    bp = art.get("bioproject_ids", [])
    print(f"  [{i:2d}] [{score:5.1f}] {title}")
    print(f"       year={year}  site={site}  bioproject={bp[0] if bp else '—'}")
print(f"{'─' * 80}")

# ── [6] Export .xlsx ──────────────────────────────────────────────────
print(f"\n[6/6] Exporting Excel (.xlsx) to desktop…")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
xlsx_path = DESKTOP / f"Shark_Skin_Microbiome_optimized_{ts}.xlsx"

rows = [COLUMNS]
for art in filtered:
    bp_str = "; ".join(art["bioproject_ids"]) if art["bioproject_ids"] else "N/A"
    rows.append([
        art.get("title", "N/A"), art.get("authors", "N/A"),
        art.get("year", "N/A"), art.get("doi", "N/A"),
        species_latin, bp_str, art.get("sampling_site", "N/A"),
    ])

write_xlsx(rows, str(xlsx_path), COL_WIDTHS)

# Also save JSON with metadata
json_path = DESKTOP / f"Shark_Skin_Microbiome_optimized_{ts}.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump({
        "species": {"input": SPECIES_INPUT, "common": common_name,
                    "latin": species_latin, "taxon_id": tid},
        "search_terms": all_terms,
        "boolean_query": query,
        "total_pubmed": len(pmids),
        "after_filter": len(filtered),
        "articles": filtered,
    }, f, ensure_ascii=False, indent=2)

print(f"  Excel → {xlsx_path}")
print(f"  JSON  → {json_path}")
print(f"\nDone! {len(filtered)} articles → desktop as .xlsx (optimized Boolean + scoring).")
