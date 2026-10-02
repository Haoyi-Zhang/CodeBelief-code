"""Bounded deterministic pilot tasks; invoked by reproduce.py, one task per process."""
import argparse
import csv
from itertools import combinations, product
import json
from pathlib import Path
from src.model import Threshold, valid, shrink, one_minimal, inclusion_minimal, exact_minimum, horn_close, horn_universe, closed_form_minimum
from src.extract import extract
from src.replay import truth, check_certificate, sat_model, check_derivation

ROOT=Path(__file__).resolve().parents[1]
THRESHOLDS=((1,2),(2,3),(3,4),(4,5),(1,1))

def write_json(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')

def pilot(out):
    census=extract((ROOT/'inputs/history/state_01.c').read_text())
    f=tuple(o.mask for o in census)
    rows=[]
    for mode in ('remined','pinned'):
        pred=lambda s:valid(f,s,Threshold(2,3),mode)
        g=shrink(range(3),pred,True);opt=exact_minimum(range(3),pred)
        c={'kind':'population-selection','source':'inputs/history/state_01.c','snapshot':1,
           'census':{o.name:o.mask for o in census},'mode':mode,'threshold':[2,3],
           'selected':[census[i].name for i in g],
           'claims':{'valid':True,'one_minimal':True,'inclusion_minimal':inclusion_minimal(g,pred),
                     'minimum_cardinality':len(g)==len(opt)}}
        checked=check_certificate(ROOT,c)
        write_json(out/f'certificate-{mode}.json',c)
        rows.append({'mode':mode,'greedy':g,'minimum':opt,'replay':checked,
                     'subsets':[{'indices':s,'valid':pred(s)} for k in range(4) for s in combinations(range(3),k)]})
    write_json(out/'pilot.json',{'features':f,'results':rows})

def populations(out,n):
    names=('population','n','threshold','mode','full_valid','optimum_size','singlepass_size',
           'repeat_size','singlepass_one_minimal','repeat_inclusion_minimal','full_one_minimal',
           'full_inclusion_minimal','subset_count','oracle_agrees','closed_form_size','truth_vector')
    counts={'n':n,'ordered_populations':3**n,'rows':0,'subset_truth_checks':0,'full_valid':0,
            'remined_repeat_not_inclusion_minimal':0,'remined_singlepass_not_one_minimal':0,
            'pinned_repeat_not_inclusion_minimal':0}
    with (out/f'population-{n}.csv').open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=names);w.writeheader()
        ids=tuple(range(n)); subsets=tuple(s for k in range(n+1) for s in combinations(ids,k))
        for f in product((1,2,3),repeat=n):
            for a,b in THRESHOLDS:
                for mode in ('remined','pinned'):
                    table={s:valid(f,s,Threshold(a,b),mode) for s in subsets}
                    for s,v in table.items():
                        if truth(f,s,a,b,mode) != v:raise AssertionError('predicate-oracle discrepancy')
                    counts['subset_truth_checks']+=len(subsets)
                    pred=table.__getitem__
                    full=pred(ids)
                    opt=next((s for s in subsets if pred(s)),None)
                    formula=closed_form_minimum(f,Threshold(a,b),mode)
                    if (opt is None) != (formula is None):raise AssertionError('closed form existence')
                    if formula is not None and (not pred(formula) or len(formula)!=len(opt)):
                        raise AssertionError('closed form optimality')
                    g1=shrink(ids,pred,False) if full else None
                    gr=shrink(ids,pred,True) if full else None
                    local=lambda s:one_minimal(s,pred)
                    incl=lambda s:inclusion_minimal(s,pred)
                    # Full invalid may still contain valid subsets under re-mining. Do not silently exclude them.
                    row=dict(population=''.join(map(str,f)),n=n,threshold=f'{a}/{b}',mode=mode,
                        full_valid=int(full),optimum_size=len(opt) if opt is not None else '',
                        singlepass_size=len(g1) if g1 is not None else '',repeat_size=len(gr) if gr is not None else '',
                        singlepass_one_minimal=int(local(g1)) if full else '',
                        repeat_inclusion_minimal=int(incl(gr)) if full else '',
                        full_one_minimal=int(local(ids)) if full else '',
                        full_inclusion_minimal=int(incl(ids)) if full else '',
                        subset_count=len(subsets),oracle_agrees=1,
                        closed_form_size=len(formula) if formula is not None else '',
                        truth_vector=''.join('1' if table[s] else '0' for s in subsets))
                    w.writerow(row);counts['rows']+=1
                    if full:
                        counts['full_valid']+=1
                        if mode=='remined' and not incl(gr):counts['remined_repeat_not_inclusion_minimal']+=1
                        if mode=='remined' and not local(g1):counts['remined_singlepass_not_one_minimal']+=1
                        if mode=='pinned' and not incl(gr):counts['pinned_repeat_not_inclusion_minimal']+=1
                        if not local(gr):raise AssertionError('repeat baseline not 1-minimal')
                        if mode=='pinned' and not incl(gr):raise AssertionError('monotone theorem violated')
                        # The two-support closed form is validated for the full-valid pinned case.
                        if mode=='pinned':
                            K=(a*n+b-1)//b;c=f.count(3)
                            if len(opt) != 2*K-min(c,K):raise AssertionError('pinned optimum formula')
    write_json(out/f'population-{n}-summary.json',counts)

def horn(out):
    rows=[];certificates=[];raw=[]
    for atoms,maxclauses in ((2,None),(3,4)):
        universe=horn_universe(atoms);total=unsat_count=0
        for k in range((len(universe) if maxclauses is None else maxclauses)+1):
            for selected in combinations(range(len(universe)),k):
                c=tuple(universe[i] for i in selected)
                unsat,trace,closure=horn_close(c,atoms)
                model=sat_model(c,atoms)
                record={'atoms':atoms,'selected_clauses':selected,'unsatisfiable':unsat,
                        'model':model,'trace':trace,'closure':closure}
                if unsat != (model is None):raise AssertionError('Horn/truth-table discrepancy')
                if unsat:
                    unsat_count+=1
                    if not check_derivation(c,trace,atoms):raise AssertionError('trace does not replay')
                    pred=lambda s:horn_close(tuple(c[i] for i in s),atoms)[0]
                    minimal=shrink(range(len(c)),pred)
                    if not inclusion_minimal(minimal,pred):raise AssertionError('Horn core not inclusion-minimal')
                    core=tuple(c[i] for i in minimal)
                    witnesses=[sat_model(tuple(x for j,x in enumerate(core) if j!=i),atoms) for i in range(len(core))]
                    if any(x is None for x in witnesses):raise AssertionError('missing deletion model')
                    record.update({'core':minimal,'deletion_models':witnesses})
                    if len(certificates)<12:
                        certificates.append({'atoms':atoms,'clauses':[{'name':x.name,'body':x.body,'head':x.head} for x in core],
                          'trace':horn_close(core,atoms)[1],'deletion_models':witnesses})
                raw.append(record)
                total+=1
        rows.append({'atoms':atoms,'universe_clauses':len(universe),'maximum_subset_size':maxclauses,
                     'formula_count':total,'unsatisfiable_count':unsat_count,'discrepancies':0})
    # Add a nontrivial implication chain explicitly; the first cases include bottom units.
    from src.model import Clause
    core=(Clause('premise',(),0),Clause('implication',(0,),1),Clause('denial',(1,),None))
    certificates.append({'atoms':2,'clauses':[{'name':c.name,'body':c.body,'head':c.head} for c in core],
        'trace':horn_close(core,2)[1],
        'deletion_models':[sat_model(tuple(c for j,c in enumerate(core) if i!=j),2) for i in range(3)]})
    write_json(out/'horn.json',rows);write_json(out/'horn-certificates.json',certificates)
    (out/'horn-cases.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in raw))

def family(out):
    rows=[]
    for a,b in ((2,3),(3,4),(4,5),(3,5),(7,10)):
        for k in (1,2,3,8):
            f=(1,)*((b-a)*k)+(2,)*((b-a)*k)+(3,)*((2*a-b)*k)
            allids=tuple(range(len(f)));pred=lambda s:valid(f,s,Threshold(a,b))
            if not one_minimal(allids,pred) or not pred((len(f)-1,)):raise AssertionError('family theorem violation')
            rows.append({'numerator':a,'denominator':b,'k':k,'sites':len(f),
                         'positive_only':f.count(1),'negative_only':f.count(2),'both':f.count(3),
                         'one_minimal_size':len(f),'minimum_size':1,'deletion_checks':len(f),
                         'method':'all immediate deletions and one singleton; no full enumeration'})
    with (out/'family.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    # Time scoping: x at old snapshot and not-x at new snapshot are consistent until bridged.
    models=[v for v in product((False,True),repeat=2) if v[0] and not v[1]]
    bridged=[v for v in models if v[0]==v[1]]
    write_json(out/'temporal.json',{'without_bridge_models':models,'with_persistence_bridge_models':bridged})

def main():
    p=argparse.ArgumentParser();p.add_argument('task',choices=['pilot','populations','horn','family']);p.add_argument('--n',type=int);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if a.task=='populations':
        if a.n is None or not 1<=a.n<=7:p.error('population size must be 1..7')
        populations(a.out,a.n)
    else:globals()[a.task](a.out)
if __name__=='__main__':main()
