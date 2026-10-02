"""Transcribe basic deductions and brackets from Rev Proc 2025-32 section 4."""
import json
from pathlib import Path
import re

def main():
    path=Path(__file__).resolve().parents[1]/'ha/rules/federal.json'
    source=path.read_text();data=json.loads(source);year=data['years']['2026']
    year['status']='partial';year['bracket_status']='final';year['citation']='https://www.irs.gov/irb/2025-45_IRB (Rev. Proc. 2025-32, sections 4.01 and 4.14; basic brackets and deductions only)'
    year['warnings']=['Basic ordinary brackets and standard deductions are final published references. Other components remain incomplete or projected; full calculations are planning estimates only.','Full statutory changes and independent verification remain incomplete. Return preparation is blocked.']
    year['standard_deduction']={'single':16100,'mfj':32200,'mfs':16100,'hoh':24150,'qss':32200}
    cuts={'single':[12400,50400,105700,201775,256225,640600],
          'mfj':[24800,100800,211400,403550,512450,768700],
          'mfs':[12400,50400,105700,201775,256225,384350],
          'hoh':[17700,67450,105700,201750,256200,640600]}
    cuts['qss']=cuts['mfj']
    year['brackets']={status:[[lo,hi,rate] for lo,hi,rate in zip([0]+bands,bands+[None],[.1,.12,.22,.24,.32,.35,.37])] for status,bands in cuts.items()}
    if 'note' in year:year['note']='Final published basic brackets and deductions; full return coverage and independent verification remain incomplete.'
    match=re.search(r'"2026":\s*',source);start=match.end();_,length=json.JSONDecoder().raw_decode(source[start:])
    replacement=json.dumps(year,indent=2).replace('\n','\n    ')
    path.write_text(source[:start]+replacement+source[start+length:])

if __name__=='__main__':main()
