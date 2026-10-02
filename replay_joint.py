#!/usr/bin/env python3
"""Replay every retained public-host joint certificate without producer imports."""
import argparse
import json
import sys
from pathlib import Path
from src.joint_replay import ReplayError, replay_certificate

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results', type=Path, default=ROOT/'results')
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    try:
        records=[]
        for path in sorted((a.results/'joint-certificates').glob('*.json')):
            records.append(replay_certificate(json.loads(path.read_text()), ROOT))
        if not records:
            raise ReplayError('no joint certificates found')
        report={
            'status':'joint-independent-replay-passed',
            'certificates':len(records),
            'positive_certificates':sum(r['status']=='certificate' for r in records),
            'negative_controls':sum(r['status']=='no-contradiction-certificate' for r in records),
            'records':records,
            'producer_module_imported':'src.joint' in sys.modules,
            'external_independent_review':False,
        }
        text=json.dumps(report,indent=2,sort_keys=True)+'\n'
        if a.report:a.report.write_text(text)
        print(text,end='')
    except (ReplayError,ValueError,KeyError,TypeError,OSError,json.JSONDecodeError) as e:
        p.exit(2,'joint replay failed: '+str(e)+'\n')

if __name__=='__main__':main()
