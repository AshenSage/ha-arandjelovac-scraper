"""EDS regression tests retained from eds_arandjelovac 1.0.0."""
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
import bootstrap
from live_test.providers.eds import parser as p
from live_test.common.http import decode_text
from live_test.providers.eds.provider import EDSProvider
from live_test.providers.eds.models import EDSSnapshot
D = date(2026, 10, 6)
URL = 'https://www.elektrodistribucija.rs/planirana-iskljucenja-srbija/Kraljevo_Dan_0_Iskljucenja.htm'
FIXTURES = bootstrap.ROOT / 'tests/fixtures/eds'

def row(municipality='Аранђеловац', times='09:00 - 13:00', area='Мисача', branch='Аранђеловац'):
    return '<tr>' + ''.join(f'<td>{v}</td>' for v in (branch, municipality, times, area)) + '</tr>'


def document(rows='', day='06.10.2026.', headers=('Огранак','Општина','Време','Улице')):
    return ('<html><body><table><tr><td>КРАЉЕВО - Планирана искључења за датум: '
            + day + '</td></tr></table><table><tr>'
            + ''.join(f'<td><b>{h}</b></td>' for h in headers)
            + '</tr>' + rows + '</table></body></html>')


class ParserTests(unittest.TestCase):
    def parse(self, html):
        return p.parse_page(html, URL)


    def assertCode(self, code, function, *args):
        with self.assertRaises(p.EDSError) as cm:
            function(*args)
        self.assertEqual(cm.exception.code, code)


    def test_exact_municipality_not_branch(self):
        result = self.parse(document(row('Топола') + row('Aranđelovac') + row('Novi Arandjelovac')))
        self.assertEqual(len(result['outages']), 1)


    def test_latin_cyrillic_case_and_diacritics(self):
        for name in ('Аранђеловац', 'АРАНЂЕЛОВАЦ', 'Aranđelovac', 'Arandjelovac', ' Aranđelovac\u00a0'):
            with self.subTest(name=name):
                self.assertEqual(len(self.parse(document(row(name)))['outages']), 1)


    def test_multiple_rows_and_deduplication(self):
        result = self.parse(document(row() + row() + row(area='Друго село') + row(times='14:00-16:00')))
        self.assertEqual(result['matched_rows'], 4)
        self.assertEqual(len(result['outages']), 3)


    def test_entities_whitespace_and_inline_markup(self):
        result = self.parse(document(row(area='  Мисача&nbsp; &amp; <b>Раниловић</b><br> Вуковићи\n ')))
        self.assertEqual(result['outages'][0]['area'], 'Мисача & Раниловић Вуковићи')


    def test_header_only_is_valid_empty(self):
        result = self.parse(document())
        self.assertEqual(result['outages'], [])
        self.assertEqual(result['rows'], 0)


    def test_missing_tables(self):
        self.assertCode('table_count', self.parse, '<html>maintenance</html>')


    def test_changed_headers(self):
        self.assertCode('table_headers', self.parse, document(row(), headers=('Огранак','Регион','Време','Улице')))


    def test_latin_headers(self):
        self.assertEqual(len(self.parse(document(row(), headers=('Ogranak','Opština','Vreme','Ulice')))['outages']), 1)


    def test_reordered_columns(self):
        html = document(headers=('Ulice','Vreme','Opština','Ogranak')).replace('</table></body>',
            '<tr><td>Мисача</td><td>09:00-13:00</td><td>Arandjelovac</td><td>Arandjelovac</td></tr></table></body>')
        self.assertEqual(len(self.parse(html)['outages']), 1)


    def test_old_page_not_relabelled(self):
        page = self.parse(document(row(), day='05.10.2026.'))
        self.assertEqual(page['date'], '2026-10-05')
        self.assertEqual(page['outages'][0]['start_at'], '2026-10-05T09:00:00+02:00')


    def test_missing_date(self):
        self.assertCode('date_missing', self.parse, document().replace('06.10.2026.', ''))


    def test_invalid_date(self):
        self.assertCode('date_invalid', self.parse, document(day='31.02.2026.'))


    def test_truncated_html(self):
        self.assertCode('truncated_html', self.parse, document(row()).split('</table>')[0])


    def test_missing_cell_even_in_foreign_municipality(self):
        self.assertCode('row_shape', self.parse, document('<tr><td>Topola</td></tr>'))


    def test_blank_municipality(self):
        self.assertCode('row_identity', self.parse, document(row(municipality='')))


    def test_empty_row_not_valid_empty_table(self):
        self.assertCode('row_identity', self.parse, document(row('', '', '', '')))


    def test_missing_area(self):
        self.assertCode('area_missing', self.parse, document(row(area='')))


    def test_rowspan_rejected(self):
        self.assertCode('table_shape', self.parse, document(row()).replace('<td>', '<td rowspan="2">', 1))


    def test_time_variants(self):
        for value in ('9:00-13:00','09.00 – 13.00','09:00 — 13:00'):
            self.assertEqual(self.parse(document(row(times=value)))['outages'][0]['start'], '09:00')


    def test_unknown_time_never_becomes_zero(self):
        for value in ('', 'nach Bedarf', '09:00', '9-13', '25:00-26:00', '09:00-24:01'):
            with self.subTest(value=value):
                self.assertCode('time_format', self.parse, document(row(times=value)))


    def test_cross_midnight_not_guessed(self):
        self.assertCode('time_ambiguous', self.parse, document(row(times='22:00-02:00')))
        self.assertCode('time_ambiguous', self.parse, document(row(times='09:00-09:00')))


    def test_explicit_24_hour_end(self):
        item = self.parse(document(row(times='22:00-24:00')))['outages'][0]
        self.assertEqual(item['end_at'], '2026-10-07T00:00:00+02:00')
        self.assertEqual(item['end'], '24:00')


    def test_dst_ambiguous_and_nonexistent(self):
        self.assertCode('time_ambiguous', p.parse_times, '02:00-04:00', date(2026, 10, 25))
        self.assertCode('time_ambiguous', p.parse_times, '02:30-04:00', date(2026, 3, 29))
        start, _ = p.parse_times('09:00-13:00', date(2026, 12, 6))
        self.assertEqual(start.utcoffset(), timedelta(hours=1))


    def test_missing_link(self):
        self.assertCode('links_missing', p.discover_pages, '<a href="/test">test</a>')



    def test_official_snapshots_old_and_new(self):
        for stamp in ('2026-10-06', '2026-10-07'):
            folder = FIXTURES/stamp
            links = p.discover_pages(decode_text((folder/'index.html').read_bytes()))
            pages = tuple(p.parse_page(decode_text((folder/f'day{i}.html').read_bytes()), links[i]) for i in range(4))
            self.assertEqual([page['matched_rows'] for page in pages], [1,0,0,0])
            provider = EDSProvider(None)
            early = provider.project(EDSSnapshot(pages), datetime(2026,10,6,10,tzinfo=p.TZ))
            late = provider.project(EDSSnapshot(pages), datetime(2026,10,6,22,tzinfo=p.TZ))
            self.assertEqual(early.count, 1)
            self.assertEqual(late.count, 0)

    def test_morning_snapshot_has_real_stale_date(self):
        html = decode_text((FIXTURES/'2026-10-07/day0.html').read_bytes())
        self.assertEqual(p.parse_page(html, URL)['date'], '2026-10-06')

    def test_unofficial_url(self):
        self.assertCode('unsafe_url', p.validate_eds_url, 'https://example.com/foo')
        self.assertCode('unsafe_url', p.validate_eds_url, 'https://www.elektrodistribucija.rs:bad/foo')
