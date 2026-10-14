"""Generic health/budget tests with no EDS or HA dependency."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

import bootstrap
from live_test.common.models import FetchResult, Projection, SourceError, SourceSpec, SourceState

NOW = datetime(2026,10,7,12,tzinfo=timezone.utc)


class FakeProvider:
    spec = SourceSpec('fake','town','Test','fake','fake','https://example.com','mdi:water',
                      timedelta(minutes=15),timedelta(minutes=35))
    def project(self, payload, now):
        return Projection(len(payload),tuple(payload))


class CommonTests(unittest.TestCase):
    def setUp(self):
        self.provider = FakeProvider()
        self.state = SourceState()

    def test_initial_unavailable(self):
        view = self.state.render(self.provider,NOW)
        self.assertFalse(view['available'])
        self.assertIsNone(view['count'])
        self.assertIsNone(view['items'])

    def test_empty_success_is_zero(self):
        self.state.accept(FetchResult([]),NOW)
        view = self.state.render(self.provider,NOW)
        self.assertEqual(view['count'],0)
        self.assertTrue(view['available'])
        self.assertEqual(view['items'],[])

    def test_failure_after_success_never_serves_stale_items(self):
        self.state.accept(FetchResult([{'arbitrary_provider_field':42}]),NOW)
        self.state.reject(SourceError('network','Offline'),NOW+timedelta(minutes=15))
        view=self.state.render(self.provider,NOW+timedelta(minutes=15))
        self.assertFalse(view['available'])
        self.assertIsNone(view['items'])
        self.assertEqual(view['last_success'],NOW.isoformat())
        self.assertNotEqual(view['last_attempt'],view['last_success'])

    def test_recovery(self):
        self.state.reject(SourceError('network','Offline'),NOW)
        self.state.accept(FetchResult([]),NOW+timedelta(minutes=15))
        self.assertTrue(self.state.render(self.provider,NOW+timedelta(minutes=15))['available'])

    def test_independent_sources(self):
        other = SourceState()
        self.state.accept(FetchResult([]),NOW)
        other.reject(SourceError('timeout','Offline'),NOW)
        self.assertTrue(self.state.render(self.provider,NOW)['available'])
        self.assertFalse(other.render(self.provider,NOW)['available'])

    def test_stale_and_clock_rollback(self):
        self.state.accept(FetchResult([]),NOW)
        for clock in (NOW+timedelta(minutes=36),NOW-timedelta(minutes=6)):
            view=self.state.render(self.provider,clock)
            self.assertEqual(view['error']['code'],'stale')
            self.assertIsNone(view['count'])

    def test_limits_fail_not_silent_truncate(self):
        for payload in ([{}]*51,[{'text':'x'*2001}],[{'many':['x'*1999]*20}]):
            self.state.accept(FetchResult(payload),NOW)
            view=self.state.render(self.provider,NOW)
            self.assertEqual(view['error']['code'],'attribute_limit')
            self.assertIsNone(view['count'])

    def test_non_json_value(self):
        self.state.accept(FetchResult([{'value':float('nan')}]),NOW)
        self.assertEqual(self.state.render(self.provider,NOW)['error']['code'],'invalid_projection')

    def test_explicit_preview_allowed(self):
        class PreviewProvider(FakeProvider):
            def project(self,payload,now): return Projection(100,({'title':'Preview'},),truncated=True)
        self.state.accept(FetchResult([]),NOW)
        view=self.state.render(PreviewProvider(),NOW)
        self.assertEqual(view['count'],100)
        self.assertTrue(view['items_truncated'])
        self.assertEqual(view['items_count'],1)

    def test_unmarked_partial_list_rejected(self):
        class BadProvider(FakeProvider):
            def project(self,payload,now): return Projection(100,())
        self.state.accept(FetchResult([]),NOW)
        self.assertEqual(self.state.render(BadProvider(),NOW)['error']['code'],'invalid_projection')

    def test_mutable_defaults_are_independent(self):
        a,b=FetchResult([]),FetchResult([])
        a.diagnostics['x']=1
        self.assertEqual(b.diagnostics,{})

    def test_error_scope_and_bounded_message(self):
        self.state.reject(SourceError('date_mismatch','x'*1000,scope='provider'),NOW)
        error=self.state.render(self.provider,NOW)['error']
        self.assertEqual(error['scope'],'provider')
        self.assertEqual(len(error['message']),300)

    def test_partial_or_invalid_coverage_fields_rejected(self):
        class CoverageProvider(FakeProvider):
            def project(self,payload,now): return payload
        for coverage in (
            {'coverage_start':'2026-10-07'},
            {'coverage_start':'2026-10-07','coverage_end':'2026-10-08',
             'coverage_days':1,'coverage_complete':False},
            {'coverage_start':'2026-10-07','coverage_end':'2026-10-07',
             'coverage_days':True,'coverage_complete':False},
        ):
            with self.subTest(coverage=coverage):
                self.state.accept(FetchResult(Projection(0,(),**coverage)),NOW)
                view=self.state.render(CoverageProvider(),NOW)
                self.assertEqual(view['error']['code'],'invalid_projection')
                self.assertIsNone(view['coverage_end'])

    def test_attribute_budget_failure_clears_valid_coverage(self):
        class CoverageProvider(FakeProvider):
            def project(self,payload,now):
                return Projection(0,(),metadata={'large':['x'*1999]*20},
                                  coverage_start='2026-10-07',coverage_end='2026-10-07',
                                  coverage_days=1,coverage_complete=False)
        self.state.accept(FetchResult([]),NOW)
        view=self.state.render(CoverageProvider(),NOW)
        self.assertEqual(view['error']['code'],'attribute_limit')
        self.assertFalse(view['available'])
        self.assertIsNone(view['coverage_days'])
        self.assertIsNone(view['coverage_complete'])
