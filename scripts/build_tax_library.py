"""Download allowlisted public IRS PDFs and build an ignored local search index."""
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.request import urlopen
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]/'.connected-local/tax-library'
SOURCES=[('Publication 17','https://www.irs.gov/pub/irs-prior/p17--2025.pdf'),
         ('Publication 334','https://www.irs.gov/pub/irs-prior/p334--2025.pdf'),
         ('Publication 527','https://www.irs.gov/pub/irs-prior/p527--2025.pdf'),
         ('Form 1040 instructions','https://www.irs.gov/pub/irs-prior/i1040gi--2025.pdf')]

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    temporary=ROOT/'library-building.sqlite3';records=[]
    with sqlite3.connect(temporary) as conn:
        conn.execute('DROP TABLE IF EXISTS passages')
        conn.execute('CREATE VIRTUAL TABLE passages USING fts5(id UNINDEXED,title UNINDEXED,url UNINDEXED,page UNINDEXED,year UNINDEXED,text)')
        for title,url in SOURCES:
            filename=url.rsplit('/',1)[-1];path=ROOT/filename
            with urlopen(url,timeout=45) as response:data=response.read(30*1024*1024+1)
            if len(data)>30*1024*1024 or not data.startswith(b'%PDF-'):raise ValueError('Invalid public PDF')
            path.write_bytes(data);digest=hashlib.sha256(data).hexdigest();reader=PdfReader(path)
            for page_number,page in enumerate(reader.pages,1):
                text=' '.join((page.extract_text() or '').split())
                for start in range(0,len(text),1600):
                    passage=text[start:start+1900]
                    identifier=filename+':'+str(page_number)+':'+str(start)
                    conn.execute('INSERT INTO passages VALUES (?,?,?,?,?,?)',(identifier,title,url,page_number,'2025',passage))
            records.append({'title':title,'url':url,'tax_year':'2025','sha256':digest,'pages':len(reader.pages)})
            print(title+' indexed',flush=True)
    conn.close()
    temporary.replace(ROOT/'library.sqlite3')
    (ROOT/'manifest.json').write_text(json.dumps(records,indent=2))

if __name__=='__main__':main()
