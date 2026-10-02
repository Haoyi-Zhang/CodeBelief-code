#!/usr/bin/env python3
"""Replay retained evidence without importing the producer or its front end.

This is a separately written software check, not an independent human review.
All input bounds are fixed by the feasibility protocol. No source is executed.
"""
import argparse
from collections import Counter
import csv
from itertools import combinations, product
import json
from pathlib import Path
from types import SimpleNamespace
from src.replay import (truth, observations, sat_model, check_derivation,
                        check_certificate, check_horn_certificate)

ROOT = Path(__file__).resolve().parent
THRESHOLDS = ('1/2', '2/3', '3/4', '4/5', '1/1')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def subsets(items):
    return tuple(s for k in range(len(items)+1) for s in combinations(items, k))


def deletion_sequence(items, predicate, repeat):
    retained = list(items)
    while True:
        before = list(retained)
        for index in before:
            other = tuple(x for x in retained if x != index)
            if predicate(other):
                retained.remove(index)
        if not repeat or retained == before:
            return tuple(retained)


def verify_populations(folder):
    totals = Counter()
    for n in range(1, 8):
        choices = subsets(tuple(range(n)))
        seen = set()
        counts = Counter()
        with (folder / f'population-{n}.csv').open(newline='') as stream:
            for row in csv.DictReader(stream):
                features = tuple(int(x) for x in row['population'])
                mode = row['mode']
                threshold = row['threshold']
                require(row['n'] == str(n) and len(features) == n and all(x in (1, 2, 3) for x in features), 'population domain')
                require(mode in ('remined', 'pinned') and threshold in THRESHOLDS, 'protocol domain')
                key = (features, mode, threshold)
                require(key not in seen, 'duplicate population configuration')
                seen.add(key)
                a, b = map(int, threshold.split('/'))
                values = {s: truth(features, s, a, b, mode) for s in choices}
                require(row['truth_vector'] == ''.join('1' if values[s] else '0' for s in choices), 'truth vector mismatch')
                require(int(row['subset_count']) == 2**n and row['oracle_agrees'] == '1', 'oracle count mismatch')
                good = tuple(s for s in choices if values[s])
                optimum = str(len(good[0])) if good else ''
                require(row['optimum_size'] == optimum == row['closed_form_size'], 'optimum mismatch')
                full = choices[-1]
                require(row['full_valid'] == str(int(values[full])), 'full validity mismatch')
                local = lambda s: values[s] and all(not values[tuple(x for x in s if x != y)] for y in s)
                minimal = lambda s: values[s] and all(not values[z] for z in subsets(s) if z != s)
                if values[full]:
                    g1 = deletion_sequence(full, values.__getitem__, False)
                    gr = deletion_sequence(full, values.__getitem__, True)
                    expected = {
                        'singlepass_size': len(g1), 'repeat_size': len(gr),
                        'singlepass_one_minimal': int(local(g1)),
                        'repeat_inclusion_minimal': int(minimal(gr)),
                        'full_one_minimal': int(local(full)),
                        'full_inclusion_minimal': int(minimal(full))}
                    require(all(row[k] == str(v) for k, v in expected.items()), 'minimization record mismatch')
                    counts['full_valid'] += 1
                    if mode == 'remined':
                        counts['remined_repeat_not_inclusion_minimal'] += not minimal(gr)
                        counts['remined_singlepass_not_one_minimal'] += not local(g1)
                    else:
                        counts['pinned_repeat_not_inclusion_minimal'] += not minimal(gr)
                    require(local(gr), 'repeated deletion is not 1-minimal')
                else:
                    require(all(row[k] == '' for k in ('singlepass_size','repeat_size',
                        'singlepass_one_minimal','repeat_inclusion_minimal',
                        'full_one_minimal','full_inclusion_minimal')), 'invalid-start baseline reported')
                counts['rows'] += 1
                counts['subset_truth_checks'] += 2**n
        require(len(seen) == 10*3**n, 'incomplete population coverage')
        summary = json.loads((folder / f'population-{n}-summary.json').read_text())
        require(summary['n'] == n and summary['ordered_populations'] == 3**n, 'population metadata')
        for field in ('rows','subset_truth_checks','full_valid','remined_repeat_not_inclusion_minimal',
                      'remined_singlepass_not_one_minimal','pinned_repeat_not_inclusion_minimal'):
            require(summary[field] == counts[field], 'population summary mismatch: '+field)
        totals.update(counts)
    return dict(totals)


def clause_space(atoms):
    clauses = []
    for body in subsets(tuple(range(atoms))):
        for head in tuple(range(atoms))+(None,):
            if head not in body:
                clauses.append(SimpleNamespace(name=f'c{len(clauses):02}', body=body, head=head))
    return tuple(clauses)


def verify_horn(folder):
    spaces = {n: clause_space(n) for n in (2, 3)}
    seen = {2: set(), 3: set()}
    counts = Counter()
    with (folder/'horn-cases.jsonl').open() as stream:
        for line in stream:
            row = json.loads(line)
            n = row['atoms']
            require(n in spaces, 'Horn atom count')
            chosen = tuple(row['selected_clauses'])
            require(all(type(i) is int and 0 <= i < len(spaces[n]) for i in chosen), 'Horn clause index')
            require(chosen == tuple(sorted(set(chosen))), 'Horn selection ordering')
            require(n != 3 or len(chosen) <= 4, 'Horn formula bound')
            require(chosen not in seen[n], 'duplicate Horn formula')
            seen[n].add(chosen)
            formula = tuple(spaces[n][i] for i in chosen)
            model = sat_model(formula, n)
            require(row['unsatisfiable'] is (model is None), 'Horn truth-table mismatch')
            require(row['model'] == (list(model) if model is not None else None), 'Horn model mismatch')
            if model is None:
                counts[f'unsatisfiable_{n}'] += 1
                require(check_derivation(formula, row['trace'], n), 'Horn trace mismatch')
                require(all(type(i) is int and 0 <= i < len(formula) for i in row['core']) and row['core'] == sorted(set(row['core'])), 'Horn core indices')
                by_name = {c.name:c for c in formula}
                derived = sorted(by_name[name].head for name in row['trace'] if by_name[name].head is not None)
                require(row['closure'] == derived, 'Horn partial closure mismatch')
                core = tuple(formula[i] for i in row['core'])
                require(sat_model(core, n) is None, 'Horn core satisfiable')
                require(len(row['deletion_models']) == len(core), 'deletion model count')
                for dropped, assignment in enumerate(row['deletion_models']):
                    require(len(assignment) == n and all(type(v) is bool for v in assignment), 'deletion model domain')
                    for i, clause in enumerate(core):
                        if i != dropped and all(assignment[j] for j in clause.body):
                            require(clause.head is not None and assignment[clause.head], 'deletion model invalid')
            if model is not None:
                require(row['closure'] == [i for i,v in enumerate(model) if v], 'Horn least model mismatch')
            counts[f'formula_{n}'] += 1
    for n, required in ((2, 256), (3, 6196)):
        require(len(seen[n]) == required, 'incomplete Horn coverage')
    for row in json.loads((folder/'horn.json').read_text()):
        n = row['atoms']
        require(row['formula_count'] == counts[f'formula_{n}'], 'Horn count mismatch')
        require(row['unsatisfiable_count'] == counts[f'unsatisfiable_{n}'], 'Horn unsat count mismatch')
        require(row['discrepancies'] == 0, 'Horn discrepancy reported')
    certificates = json.loads((folder/'horn-certificates.json').read_text())
    for certificate in certificates:
        check_horn_certificate(certificate)
    counts['fixed_formula_certificates'] = len(certificates)
    return dict(counts)


def verify_sources(folder):
    entries = json.loads((ROOT/'inputs/index.json').read_text())
    for entry in entries:
        observed = observations((ROOT/entry['source']).read_text())
        require(list(observed.values()) == entry['expected_masks'], 'source census mismatch')
    replayed = {}
    for mode in ('remined', 'pinned'):
        certificate = json.loads((folder/f'certificate-{mode}.json').read_text())
        replayed[mode] = check_certificate(ROOT, certificate)
    return {'source_files': len(entries), 'certificates': replayed}


def verify_family(folder):
    count = 0
    seen = set()
    maximum = 0
    expected = {(a,b,k) for a,b in ((2,3),(3,4),(4,5),(3,5),(7,10)) for k in (1,2,3,8)}
    with (folder/'family.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            a,b,k = (int(row[x]) for x in ('numerator','denominator','k'))
            require((a,b,k) in expected and (a,b,k) not in seen, 'family coverage identity')
            seen.add((a,b,k))
            features = (1,)*((b-a)*k)+(2,)*((b-a)*k)+(3,)*((2*a-b)*k)
            maximum = max(maximum, len(features))
            require([int(row[x]) for x in ('positive_only','negative_only','both')] == [features.count(x) for x in (1,2,3)], 'family support counts')
            require(int(row['deletion_checks']) == len(features), 'family deletion count')
            require(len(features) == int(row['sites']) == int(row['one_minimal_size']), 'family size')
            full = tuple(range(len(features)))
            require(truth(features,full,a,b,'remined'), 'family full')
            require(all(not truth(features,tuple(j for j in full if j!=i),a,b,'remined') for i in full), 'family local deletion')
            require(truth(features,(len(features)-1,),a,b,'remined') and row['minimum_size']=='1', 'family singleton')
            count += 1
    require(count == 20 and seen == expected, 'family coverage')
    temporal = json.loads((folder/'temporal.json').read_text())
    states = [list(v) for v in product((False,True),repeat=2) if v[0] and not v[1]]
    require(temporal['without_bridge_models'] == states, 'temporal separation')
    require(temporal['with_persistence_bridge_models'] == [v for v in states if v[0]==v[1]], 'temporal bridge')
    return {'family_cases':count,'largest_family_sites':maximum,'temporal_valuations_enumerated':4}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=ROOT/'results')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        report = {'population':verify_populations(args.results), 'horn':verify_horn(args.results),
                  'source':verify_sources(args.results), 'family':verify_family(args.results),
                  'status':'finite_replay_passed','external_independent_review':False}
        text = json.dumps(report,indent=2,sort_keys=True)+'\n'
        if args.report is not None:
            args.report.write_text(text)
        print(text,end='')
    except (ValueError,KeyError,TypeError,IndexError,OSError) as error:
        parser.exit(2,'replay failed: '+str(error)+'\n')


if __name__ == '__main__':
    main()
