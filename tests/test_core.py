import copy
import json
from itertools import combinations
from pathlib import Path
import unittest
from src.extract import extract, parse
from src.model import Threshold, valid, shrink, exact_minimum, inclusion_minimal, one_minimal, Clause, horn_close, closed_form_minimum
from src.replay import observations, check_certificate, sat_model, check_derivation, check_horn_certificate
ROOT = Path(__file__).resolve().parents[1]

class CoreTests(unittest.TestCase):
    def test_three_site_trap(self):
        f=(1,2,3); t=Threshold(2,3); pred=lambda s: valid(f,s,t)
        self.assertTrue(one_minimal((0,1,2),pred))
        self.assertFalse(inclusion_minimal((0,1,2),pred))
        self.assertEqual(exact_minimum(range(3),pred),(2,))
        self.assertEqual(shrink(range(3),pred,True),(0,1,2))
    def test_remined_collapse_and_disjoint_boundary(self):
        for a,b in ((1,3),(1,2),(2,3),(1,1)):
            t=Threshold(a,b)
            self.assertEqual(closed_form_minimum((1,1,3),t),(2,))
            self.assertEqual(closed_form_minimum((1,2),t),(0,1) if 2*a<=b else None)
            self.assertIsNone(closed_form_minimum((1,1),t))
            self.assertIsNone(closed_form_minimum((),t))
        self.assertFalse(valid((1,1,3),range(3),Threshold(2,3)))
        f=(3,3,1);pred=lambda s:valid(f,s,Threshold(2,3))
        self.assertFalse(one_minimal(shrink(range(3),pred),pred))
        self.assertTrue(one_minimal(shrink(range(3),pred,True),pred))
    def test_pinned_different_question(self):
        f=(1,2,3);t=Threshold(2,3);pred=lambda s:valid(f,s,t,'pinned')
        self.assertTrue(inclusion_minimal((0,1,2),pred))
        self.assertEqual(exact_minimum(range(3),pred),(0,1,2))
        self.assertFalse(pred((2,)))
    def test_unbounded_family(self):
        for a,b in ((2,3),(3,4),(4,5),(3,5),(7,10)):
            for k in (1,2,3,8):
                f=(1,)*((b-a)*k)+(2,)*((b-a)*k)+(3,)*((2*a-b)*k)
                pred=lambda s:valid(f,s,Threshold(a,b))
                self.assertTrue(one_minimal(tuple(range(len(f))),pred))
                self.assertTrue(pred((len(f)-1,)))
    def test_sharing_cardinality(self):
        f=(3,3,1,1,2,2); t=Threshold(1,3);pred=lambda s:valid(f,s,t,'pinned')
        g=shrink(range(6),pred)
        self.assertEqual(len(g),4)
        self.assertEqual(len(exact_minimum(range(6),pred)),2)
        self.assertTrue(inclusion_minimal(g,pred))
    def test_exact_code_snapshots(self):
        for entry in json.loads((ROOT/'inputs/index.json').read_text()):
            with self.subTest(source=entry['source']):
                text=(ROOT/entry['source']).read_text()
                prod=extract(text); ref=observations(text)
                self.assertEqual({o.name:o.mask for o in prod},ref)
                self.assertEqual([o.mask for o in prod],entry['expected_masks'])
    def test_frontend_rejects_unsupported(self):
        bad=['void f(void){ if (1) touch(); }','void f(void){ unlock(); }',
             'void f(void){ lock(); }','void f(void){ lock(); lock(); unlock(); unlock(); }',
             'void f(void){ arbitrary(); }','void f(void){ touch() }',
             'void f(void){ touch(); } void f(void){ touch(); }',
             'void lock(void){}','void f(void){ touch(); } int x;',
             'vo/**/id f(void){touch();}','void f(void){touch();} /* unterminated',
             'void arbitrary(void);']
        for s in bad:
            for parser in (extract,observations):
                with self.subTest(text=s,parser=parser.__module__), self.assertRaises(ValueError):parser(s)
    def test_frontend_comments_and_empty(self):
        for s in ('','void f(void) {}','void f(void) { /* touch(); */ noop(); }',
                  'void f(void){lock();/* x */touch(); unlock(); // hi\n touch();}'):
            self.assertEqual({o.name:o.mask for o in extract(s)}, observations(s))
    def test_horn_chain(self):
        c=(Clause('a',(),0),Clause('b',(0,),1),Clause('c',(1,),None))
        unsat, trace, closure=horn_close(c,2)
        self.assertTrue(unsat);self.assertIsNone(sat_model(c,2));self.assertTrue(check_derivation(c,trace,2))
        self.assertFalse(check_derivation(c,trace[::-1],2))
        self.assertFalse(check_derivation(c,trace[:-1],2))
    def test_horn_certificate_mutations(self):
        c={'atoms':2,'clauses':[{'name':'a','body':[],'head':0},
            {'name':'b','body':[0],'head':1},{'name':'c','body':[1],'head':None}],
            'trace':['a','b','c'],'deletion_models':[[False,False],[True,False],[True,True]]}
        self.assertTrue(check_horn_certificate(c)['inclusion_minimal'])
        for change in ('trace','model','head','body','count'):
            bad=copy.deepcopy(c)
            if change=='trace':bad['trace'].reverse()
            elif change=='model':bad['deletion_models'][0]=[True,True]
            elif change=='head':bad['clauses'][0]['head']=2
            elif change=='body':bad['clauses'][1]['body']=[-1]
            else:bad['deletion_models'].pop()
            with self.subTest(change=change),self.assertRaises(ValueError):check_horn_certificate(bad)
    def test_empty_and_background_false(self):
        self.assertFalse(horn_close((),0)[0]);self.assertEqual(sat_model((),0),())
        self.assertTrue(horn_close((Clause('bottom',(),None),),0)[0])
    def test_certificate_and_mutations(self):
        text=(ROOT/'inputs/history/state_01.c').read_text()
        c={'kind':'population-selection','snapshot':1,'source':'inputs/history/state_01.c',
           'census':observations(text),'threshold':[2,3],'mode':'remined',
           'selected':['alpha','beta','gamma'],
           'claims':{'valid':True,'one_minimal':True,'inclusion_minimal':False,'minimum_cardinality':False}}
        r=check_certificate(ROOT,c); self.assertEqual(r['minimum_size'],1)
        mutations=[]
        x=copy.deepcopy(c);x['claims']['inclusion_minimal']=True;mutations.append(x)
        x=copy.deepcopy(c);x['census'].pop('beta');mutations.append(x)
        x=copy.deepcopy(c);x['snapshot']=0;mutations.append(x)
        x=copy.deepcopy(c);x['selected'].append('alpha');mutations.append(x)
        x=copy.deepcopy(c);x['threshold']=[2,0];mutations.append(x)
        x=copy.deepcopy(c);x['mode']='unknown';mutations.append(x)
        x=copy.deepcopy(c);x['source']='../README.md';mutations.append(x)
        x=copy.deepcopy(c);x['census']['alpha']=True;mutations.append(x)
        for m in mutations:
            with self.subTest(mutation=m),self.assertRaises(ValueError):check_certificate(ROOT,m)
    def test_domain_validation(self):
        for args in [(0,1),(2,1),(1,0),(True,2),(1,1001)]:
            with self.assertRaises(ValueError):Threshold(*args)
        for s in ((0,0),(-1,),(2,),(True,)):
            with self.assertRaises(ValueError):valid((1,3),s,Threshold(1,2))
        with self.assertRaises(ValueError):valid((0,),(0,),Threshold(1,2))
        with self.assertRaises(ValueError):exact_minimum(range(17),lambda s:True)

if __name__=='__main__':unittest.main()
