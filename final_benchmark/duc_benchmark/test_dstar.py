"""D* Lite integration regressions; randomized dynamics use positive costs."""
import copy
import math
import random
import unittest
from unittest.mock import patch
from benchmark_common import oracle, validate, resolve, run_isolated
from cases import fingerprint, numeric_problem
from dstar_adapter import create_planner
from dynamic_runner import prepare, episode
from solvers import astar_to_dstarlite as member
from solvers import dfs_2_idastar as dfs
from solvers import ucs_biucs_benchmark as ucs


class DStarIntegrationTests(unittest.TestCase):
    def problem(self):
        return {'graph':{'s':{'a':1,'t':6},'a':{'t':1},'t':{}},'start':'s','goal':'t'}

    def test_retained_tables_no_search_in_update_and_phase_counts(self):
        p=self.problem();adapter=create_planner(p);planner=adapter.planner
        tables=(id(planner),id(planner.g),id(planner.rhs),id(planner.U))
        with patch.object(planner,'compute_shortest_path',side_effect=AssertionError('eager search')):
            adapter.update([{'u':'s','v':'t','cost':7}])
            adapter.move_start('s')
        first=adapter.plan();second=adapter.plan()
        self.assertEqual(first['cost'],2);self.assertEqual(second['expanded'],0)
        self.assertEqual(tables,(id(adapter.planner),id(planner.g),id(planner.rhs),id(planner.U)))
        self.assertEqual(first['expanded']+second['expanded'],planner.expanded)
        self.assertEqual(p,self.problem())

    def test_block_reopen_and_directed_update(self):
        p=self.problem();p['graph']['t']['a']=9
        adapter=create_planner(p);adapter.plan()
        for changes in ([{'u':'a','v':'t','cost':'inf'},{'u':'s','v':'t','cost':'inf'}],
                        [{'u':'a','v':'t','cost':1},{'u':'s','v':'t','cost':6}]):
            adapter.update(changes)
            for e in changes:p['graph'][e['u']][e['v']]=math.inf if e['cost']=='inf' else e['cost']
            validate(adapter.plan(),p,oracle(p),True)
            self.assertEqual(adapter.planner.problem.graph['t']['a'],9)

    def test_move_start_accumulates_km(self):
        p=self.problem();p['locations']={'s':(0,0),'a':(1,0),'t':(2,0)}
        adapter=create_planner(p);adapter.plan();adapter.move_start('a');p['start']='a'
        self.assertEqual(adapter.planner.km,1);validate(adapter.plan(),p,1,True)
        adapter.move_start('t');p['start']='t';self.assertEqual(adapter.planner.km,2)
        validate(adapter.plan(),p,0,True)

    def test_existing_nodes_new_directed_arc(self):
        p=self.problem();del p['graph']['a']['t']
        adapter=create_planner(p);self.assertEqual(adapter.plan()['cost'],6)
        adapter.update([{'u':'a','v':'t','cost':1}]);p['graph']['a']['t']=1
        self.assertIn('a',adapter.planner.preds['t']);validate(adapter.plan(),p,2,True)

    def test_dynamic_zero_cost_guard_and_atomic_validation(self):
        p=self.problem();adapter=create_planner(p);adapter.plan()
        for value in (0,-1,math.nan,True):
            with self.assertRaises(ValueError):
                adapter.update([{'u':'s','v':'t','cost':3},{'u':'a','v':'t','cost':value}])
            self.assertEqual(adapter.planner.problem.graph['s']['t'],6)
        p['graph']['s']['a']=0
        with self.assertRaises(ValueError):create_planner(p)

    def test_300_random_directed_dynamic_episodes(self):
        rnd=random.Random(18102026)
        for index in range(300):
            n=rnd.randint(2,9);g={u:{} for u in range(n)}
            for u in g:
                for v in g:
                    if u!=v and rnd.random()<.3:g[u][v]=rnd.choice([.1,1,2.5,math.inf])
            p={'graph':g,'start':0,'goal':n-1};adapter=create_planner(p)
            for phase in range(10):
                with self.subTest(index=index,phase=phase):validate(adapter.plan(),p,oracle(p),True)
                u,v=rnd.sample(list(g),2);w=rnd.choice([.1,1,2.5,math.inf]);g[u][v]=w
                adapter.update([{'u':u,'v':v,'cost':w}]);p['start']=rnd.randrange(n);adapter.move_start(p['start'])

    def test_all_original_member_scenarios_each_phase_and_final_api(self):
        for test in member.get_tests(full=True):
            if not test['dynamic_updates']:continue
            with self.subTest(test=test['test_id']):
                snapshots,changes=prepare({'member_test_id':test['test_id']})
                before=[fingerprint(p) for p in snapshots]
                rows=episode(create_planner,snapshots,changes,measured=False)
                baseline=episode(None,snapshots,changes,True,member.solve_astar,measured=False)
                self.assertEqual([r['cost'] for r in rows],[r['cost'] for r in baseline])
                self.assertEqual(before,[fingerprint(p) for p in snapshots])
                raw=member.solve(copy.deepcopy(test))
                self.assertAlmostEqual(rows[-1]['cost'],raw['cost'])

    def test_three_romania_maps_and_static_flood_compilation(self):
        self.assertEqual(member.romania_map,dfs.romania_map)
        self.assertEqual(member.romania_map,ucs.romania_map)
        for test in member.get_tests(full=True):
            if test['dynamic_updates']:continue
            p=numeric_problem(test)
            for fn in (member.solve_astar,member.solve):
                raw,compiled=fn(copy.deepcopy(test)),fn(p)
                self.assertEqual((raw['cost'],raw['expanded']),(compiled['cost'],compiled['expanded']))
                validate(compiled,p,oracle(p),True)

    def test_dynamic_timeout_keeps_failure_without_fake_metrics(self):
        p=self.problem()
        result=run_isolated('dynamic_runner:_episode_job',('dstar_adapter:create_planner','test_common:slow',[p],[[]],1),.2)
        self.assertEqual(result['status'],'FAILED');self.assertIn('TIMEOUT',result['reason'])
        self.assertNotIn('time_ms',result)


if __name__=='__main__':unittest.main(verbosity=2)