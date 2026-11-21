setup


```python
import re
import sys
import statistics
from collections import Counter
from pathlib import Path

import pymupdf

ROOT = Path.cwd().parent                 # notebook runs inside notebooks/
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
code_pdf = RAW / "labor_code_2022.pdf"
hb_pdf = RAW / "workers_handbook_2024.pdf"

sys.path.append(str(ROOT / "src"))

%load_ext autoreload
%autoreload 2

from shared import labor_code_parser as lcp

print(code_pdf.exists(), hb_pdf.exists())
```

    The autoreload extension is already loaded. To reload it, use:
      %reload_ext autoreload
    True True
    

Parse the Labor Code


```python
raw = lcp.read_pdf_text(code_pdf)
clean = lcp.clean_text(raw)
articles = lcp.split_articles(clean)

print("characters read:", len(raw), "| after cleaning:", len(clean))
print("articles:", len(articles))
print(articles[86]["id"], "-", articles[86]["heading"])     # should be art_87 - Overtime Work
```

    characters read: 284957 | after cleaning: 273317
    articles: 317
    art_87 - Overtime Work
    

Verify the parse


```python
foot = re.compile(r"^\d{1,3}\s+\S")
cap = re.compile(r"^[A-Z0-9 ,\-–&'’/().]{4,}$")

footnote_like = [(a["id"], l[:60]) for a in articles for l in a["text"].split("\n") if foot.match(l)]
stray_caps = [(a["id"], l) for a in articles for l in a["text"].split("\n")
              if cap.match(l) and not re.fullmatch(r"[IVX]+", l)]
all_labels = {a["book"] for a in articles} | {a["title"] for a in articles} | {a["chapter"] for a in articles}

print("unique article numbers:", len({a["article"] for a in articles}))
print("footnote-like lines left:", len(footnote_like), footnote_like[:5])
print("stray all-caps lines left:", len(stray_caps), stray_caps[:5])
print("headings ending in a digit:", [a["id"] for a in articles if a["heading"][-1:].isdigit()])
print("labels ending in a digit:", [x for x in all_labels if x[-1:].isdigit()])
print("texts starting with a dash:", [a["id"] for a in articles if a["text"].startswith("–")])
print()
for b in sorted({a["book"] for a in articles}):
    print(b)
```

    unique article numbers: 317
    footnote-like lines left: 0 []
    stray all-caps lines left: 0 []
    headings ending in a digit: []
    labels ending in a digit: []
    texts starting with a dash: []
    
    Book Five – LABOR RELATIONS
    Book Four – HEALTH, SAFETY AND SOCIAL WELFARE BENEFITS
    Book One - PRE-EMPLOYMENT
    Book Seven – TRANSITORY AND FINAL PROVISIONS
    Book Six – POST-EMPLOYMENT
    Book Three – CONDITIONS OF EMPLOYMENT
    Book Two – HUMAN RESOURCES DEVELOPMENT PROGRAM
    PRELIMINARY TITLE
    

Spot-check articles


```python
for k in ("art_6", "art_87", "art_130", "art_297"):
    a = next(x for x in articles if x["id"] == k)
    print(k, "| old:", a["old_article"] or "-", "|", a["heading"])
    print("   ", a["book"], ">", a["title"] or "-", ">", a["chapter"] or "-")
    print("   ", a["text"][:150].replace("\n", " "), "\n")
```

    art_6 | old: - | Applicability
        PRELIMINARY TITLE > - > Chapter I - GENERAL PROVISIONS
        All rights and benefits granted to workers under this Code shall, except as may otherwise be provided herein, apply alike to all workers, whether agri 
    
    art_87 | old: - | Overtime Work
        Book Three – CONDITIONS OF EMPLOYMENT > Title I – WORKING CONDITIONS AND REST PERIODS > Chapter I – HOURS OF WORK
        Work may be performed beyond eight (8) hours a day provided that the employee is paid for the overtime work, an additional compensation equivalent to  
    
    art_130 | old: 132 | Facilities for Women
        Book Three – CONDITIONS OF EMPLOYMENT > Title III – WORKING CONDITIONS FOR SPECIAL GROUPS OF EMPLOYEES > Chapter I – EMPLOYMENT OF WOMEN
        The Secretary of Labor and Employment shall establish standards that will ensure the safety and health of women employees. In appropriate cases, he sh 
    
    art_297 | old: 282 | Termination by Employer
        Book Six – POST-EMPLOYMENT > Title I – TERMINATION OF EMPLOYMENT > -
        An employer may terminate an employment for any of the following causes: (a) Serious misconduct or willful disobedience by the employee of the lawful  
    
    

Length check


```python
lens = [len(a["text"]) for a in articles]
print("min / median / max chars:", min(lens), statistics.median(lens), max(lens))
print("articles over 1500 chars:", sum(1 for n in lens if n > 1500))

print("\nlongest articles:")
for a in sorted(articles, key=lambda a: len(a["text"]), reverse=True)[:8]:
    print(" ", a["id"], "|", a["heading"], "|", len(a["text"]), "chars")

print("\nno book:   ", sum(1 for a in articles if not a["book"]))
print("no chapter:", sum(1 for a in articles if not a["chapter"]))
print("very short:", [(a["id"], a["text"][:40]) for a in articles if len(a["text"]) < 40])
```

    min / median / max chars: 66 485 7600
    articles over 1500 chars: 44
    
    longest articles:
      art_250 | Rights and Conditions of Membership in a Labor Organization | 7600 chars
      art_225 | Powers of the Commission | 7368 chars
      art_173 | Definition of Terms | 7071 chars
      art_278 | Strikes, Picketing, and Lockouts | 6462 chars
      art_292 | Miscellaneous Provisions | 5643 chars
      art_219 | Definitions | 4629 chars
      art_220 | National Labor Relations Commission | 4558 chars
      art_124 | Standards/Criteria for Minimum Wage Fixing | 4217 chars
    
    no book:    0
    no chapter: 66
    very short: []
    

Save


```python
out = PROCESSED / "labor_code_articles.jsonl"
lcp.save_jsonl(articles, out)
print(out, out.stat().st_size, "bytes")
```

    C:\Users\Gerome\Documents\GitHub\ai3-rag-labor-code\data\processed\labor_code_articles.jsonl 344746 bytes
    

Appendix: why we filter by font size


```python
sizes = Counter()
dropped = Counter()

with pymupdf.open(code_pdf) as doc:
    for p in doc:
        for b in p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    sz = round(s["size"], 1)
                    sizes[sz] += len(s["text"])
                    if 6.5 <= s["size"] < lcp.MIN_BODY_SIZE and s["text"].strip():
                        dropped[(sz, s["text"].strip()[:40])] += 1

print("characters by font size:", sizes.most_common(8))
print("dropped mid-size text:", dropped.most_common(10))
```

    characters by font size: [(9.5, 272355), (5.5, 85943), (9.0, 6610), (10.0, 2300), (8.0, 1935), (12.0, 1892), (14.0, 1166), (3.5, 934)]
    dropped mid-size text: [((7.0, 'ITLE'), 26), ((8.0, '4'), 2), ((8.0, '65'), 2), ((8.0, '67'), 2), ((8.0, '94'), 2), ((8.0, '95'), 2), ((8.0, '104'), 2), ((8.0, '112'), 2), ((8.0, 'This is published and distributed FOR FR'), 1), ((8.0, 'Copyright © 2022 by DOLE'), 1)]
    

Handbook table test (work in progress)


```python
import pymupdf4llm

md = pymupdf4llm.to_markdown(hb_pdf, pages=[12, 13])
print(md[:3000])
```

    
    === Document parser messages ===
    Warning: RapidOCR is missing. Install for much improved OCR results.
    3 
    
    Special (non-working) day, rest day, night 1.5 x 1.1 x 1.3 = 2.145 or **214.5%** shift, OT Double special (non-working) day, night 1.5 x 1.1 x 1.3 = 2.145 or **214.5%** shift, OT Double special (non-working) day, rest 1.95 x 1.1 x 1.3 = 2.7885 or **278.85%** day, night shift, OT Regular holiday, night shift, OT 2 x 1.1 x 1.3 = 2.86 or **286%** Reg. holiday, rest day, night shift, OT 2.6 x 1.1 x 1.3 = 3.718 or **371.8%** Double holiday, night shift, OT 3 x 1.1 x 1.3 = 4.29 or **429%** Double holiday, rest day, night shift, OT 3.9 x 1.1 x 1.3 = 5.577 or **557.7%** 
    
    # **B. Summary of Statutory Leave Benefits** 
    
    |**Type of Leave**<br>**Benefit**|**Conditions of Entitlement**|**Duration of Paid**<br>**Leave**|
    |---|---|---|
    |1. Service<br>Incentive Leave|• The employee has rendered at least<br>oneyear of service.<br>|five days|
    |2. Maternity<br>Leave|• The female employee has at least<br>three monthly contributions to the<br>SSS<br>in<br>the<br>12-month<br>period<br>immediately<br>preceding<br>the<br>semester of childbirth, miscarriage,<br>or<br>emergency<br>termination<br>of<br>pregnancy;  and<br>• The female employee has notified<br>her employer about her pregnancy<br>and the probable date of her<br>childbirth.|If live childbirth:<br>105 days; an<br>additional 15 days<br>or a total of 120<br>days if the female<br>employee is a<br>qualified solo<br>parent<br>If miscarriage or<br>emergency<br>termination of<br>pregnancy:<br>60 days|
    |3. Paternity Leave|<sup>• The married male is an employee at</sup><br>the time of the delivery of his child;<br>• The married male employee is<br>cohabiting with his spouse at the<br>time that the latter gives birth or<br>suffers a miscarriage;<br>• The married male employee has<br>applied for paternity leave with his<br>employer within a reasonable<br>period of time from the expected<br>date of delivery by his pregnant<br>spouse, or within such period as<br>may be provided by company rules<br>and regulations or by collective<br>bargaining agreement, provided<br>that prior application for leave shall|seven days|
    
    
    
    4 
    
    |**Type of Leave**<br>**Benefit**|**Conditions of Entitlement**|**Duration of Paid**<br>**Leave**|
    |---|---|---|
    ||not be required in case of<br>miscarriage; and<br>• Thewifeof themarried male<br>employee has given birth or<br>suffered a miscarriage.||
    |4. Parental Leave|• The employee has rendered at least<br>six months of service, whether<br>continuous or broken, at the time<br>of the effectivity of Republic Act<br>No. 11861;<br>• The employee has notified his/her<br>employer of the availment thereof<br>within a reasonable time; and<br>• The employee haspresented a valid<br>Solo Parent Identification Card<br>(SPIC).|seven days|
    |5. Leave for<br>VAWC|• The victim-employee presents to her<br>employer a certification from the<br>barangay<br>chairman<br>(_punong_<br>_barangay_),<br>barangay<br>councilor<br>(_barangay kagawad_), prosecutor,<br>or Clerk of Court, as the case may<br>be, that an action rela
    
