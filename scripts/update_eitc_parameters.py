"""Reproducible transcription of IRC32 and IRS revenue-procedure EITC parameters."""
import json
import re
from pathlib import Path

def main():
    path = Path(__file__).resolve().parents[1]/'ha/rules/federal.json'
    source = path.read_text()
    data = json.loads(source)
    # Entries are ordered none, one, two, three-plus qualifying children.
    values = {
        '2024': ([632,4213,6960,7830], [10330,22720,22720,22720],
                 [17250,29640,29640,29640], [18591,49084,55768,59899],
                 [25511,56004,62688,66819],11600,'2023-48'),
        '2025': ([649,4328,7152,8046], [10620,23350,23350,23350],
                 [17730,30470,30470,30470], [19104,50434,57310,61555],
                 [26214,57554,64430,68675],11950,'2024-45'),
        '2026': ([664,4427,7316,8231], [10860,23890,23890,23890],
                 [18140,31160,31160,31160], [19540,51593,58629,62974],
                 [26820,58863,65899,70244],12200,'2025-45'),
    }
    keyed = lambda items: {str(i):value for i,value in enumerate(items)}
    for year,(maximum,single_start,joint_start,single_end,joint_end,limit,bulletin) in values.items():
        rule = data['years'][year]['eitc']
        rule.update(max_credit=keyed(maximum),phasein_rate=keyed([0.0765,0.34,0.40,0.45]),
                    phaseout_rate=keyed([0.0765,0.1598,0.2106,0.2106]),
                    phaseout_start_income={'single':keyed(single_start),'mfj':keyed(joint_start)},
                    phaseout_end_income={'single':keyed(single_end),'mfj':keyed(joint_end)},
                    earned_income_and_agi_ceiling={'single':keyed(single_end),'mfj':keyed(joint_end)},
                    investment_income_limit={'single':limit,'mfj':limit},verified=False,
                    citation=f'https://www.irs.gov/irb/{bulletin}_IRB section 3.06; IRC 32(b)')
        rule['note']='Parameters transcribed from primary sources. Formula scenario only; official EIC table and full eligibility unimplemented.'
    # Preserve unrelated rule formatting; replace only each year's EITC object.
    decoder = json.JSONDecoder()
    matches = list(re.finditer(r'"eitc":\s*',source))
    if len(matches) != len(values):
        raise ValueError('Unexpected EITC block count')
    for match,year in reversed(list(zip(matches,values))):
        start = match.end()
        _,length = decoder.raw_decode(source[start:])
        line_start = source.rfind('\n',0,match.start())+1
        indent = source[line_start:match.start()]
        replacement = json.dumps(data['years'][year]['eitc'],indent=2).replace('\n','\n'+indent)
        source = source[:start]+replacement+source[start+length:]
    path.write_text(source)

if __name__ == '__main__':
    main()
