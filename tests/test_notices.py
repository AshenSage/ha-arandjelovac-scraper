"""Offline contracts for local sources, using reduced structural examples."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta
import json
import unittest

import bootstrap
from live_test.common.models import FetchResult, SourceError, SourceState, validate_projection
from live_test.providers.notices.parsers import (Article,event_items,item,matches_area,parse_bukulja_article,
    parse_bukulja_index,parse_feed,parse_municipality,parse_traffic,water_notice)
from live_test.providers.notices.provider import NoticeProvider,NoticeSnapshot,SOURCES
from live_test.providers.notices.text import TZ,local_time,named_date,normalize,plain,public_link

NOW=datetime(2026,10,14,15,0,tzinfo=TZ)
BASE='https://www.jkpbukulja.rs/vesti'
HEADER='point\ttitle\tdescription\ticonSize\ticonOffset\ticon\n'
def article(title='Мрежа',text='Информација',**kw):
    return Article('example',title,text,BASE+'/primer',NOW.replace(hour=10),**kw)
def traffic_row(title='31.8.2026. Obustava Lazarevac – Darosava',text='Od 31.8.2026. do 26.12.2026. obustava saobracaja.'):
    return '-3301,2386\tOBUSTAVE: '+title+'\t'+text+'\t50,50\t-25,-35\tpin.png\n'
def feed(description='<p>Информација</p>',title='Најава',url='https://centarzakulturuarandjelovac.rs/example',pub='Wed, 14 Oct 2026 08:00:00 GMT'):
    return f'<rss version="2.0"><channel><title>Култура</title><link>https://centarzakulturuarandjelovac.rs/</link><item><guid>1</guid><title>{title}</title><link>{url}</link><pubDate>{pub}</pubDate><description><![CDATA[{description}]]></description></item></channel></rss>'
def index(title='Плански прекид водоснабдевања',text='14. октобар 2026.'):
    return f'<h1>Вести из Аранђеловца.</h1><a href="/vesti/primer"><span>{text}</span><h2>{title}</h2></a>'

class TextTests(unittest.TestCase):
    def test_cyrillic_latin_normalization(self):
        self.assertEqual(normalize('АРАНЂЕЛОВАЦ'),normalize('Aranđelovac'))
        self.assertEqual(normalize('Раниловић'),normalize('Ranilović'))
    def test_html_scripts_removed(self):
        self.assertEqual(plain('<p>A &amp; B</p><script>BAD</script><style>BAD</style><p>C</p>'),'A & B\nC')
    def test_public_links(self):
        self.assertEqual(public_link('/vesti/primer',BASE),BASE+'/primer')
        for bad in ['javascript:alert(1)','https://example.com','https://www.jkpbukulja.rs@evil.com/x']:
            with self.subTest(bad=bad),self.assertRaises(SourceError):public_link(bad,BASE)
    def test_dst_and_impossible_dates(self):
        for values in [(2026,3,29,2,30),(2026,10,25,2,30),(2026,2,30,12,0)]:
            with self.subTest(values=values),self.assertRaises(SourceError):local_time(*values)
    def test_named_month_and_december_year(self):
        self.assertEqual(named_date('4 мин · 14. октобар 2026.',NOW).day,14)
        self.assertEqual(named_date('2. januara',datetime(2026,12,31,tzinfo=TZ)).year,2027)
    def test_location_declension(self):
        for name in ['Аранђеловац','Aranđelovcu','Aranđelovca']:
            self.assertTrue(matches_area(name,('Aranđelovac',)))
    def test_location_false_positives(self):
        self.assertFalse(matches_area('Bačka Topola',('Topola',)))
        self.assertFalse(matches_area('Karan – Trnava',('Aranđelovac',)))
        self.assertFalse(matches_area('Darosavac',('Darosava',)))

class FeedAndNewsTests(unittest.TestCase):
    def test_feed_html_and_utc(self):
        parsed=parse_feed(feed(), 'https://centarzakulturuarandjelovac.rs/rss')
        self.assertEqual(parsed[0].published.hour,10)
        self.assertEqual(parsed[0].text,'Информација')
    def test_feed_duplicate(self):
        raw=feed();node=raw[raw.index('<item>'):raw.index('</item>')+7]
        self.assertEqual(len(parse_feed(raw.replace('</channel>',node+'</channel>'),'https://centarzakulturuarandjelovac.rs/rss')),1)
    def test_feed_rejects_non_feed(self):
        for value in ['<html>Maintenance</html>','<rss><channel></rss>','<!DOCTYPE rss><rss/>','<rss><channel/></rss>']:
            with self.subTest(value=value),self.assertRaises(SourceError):parse_feed(value,'https://centarzakulturuarandjelovac.rs/rss')
    def test_feed_rejects_bad_link_and_date(self):
        for value in [feed(url='https://evil.example/x'),feed(pub='tomorrow')]:
            with self.subTest(value=value),self.assertRaises(SourceError):parse_feed(value,'https://centarzakulturuarandjelovac.rs/rss')
    def test_valid_empty_feed(self):
        self.assertEqual(parse_feed('<rss><channel><title>News</title><link>https://arandjelovac.rs/</link></channel></rss>','https://arandjelovac.rs/'),())
    def test_wp_prefers_utc_not_naive_date(self):
        record={'id':1,'date':'2026-10-14T09:00:00','date_gmt':'2026-10-14T08:00:00','modified_gmt':'2026-10-14T08:30:00','link':'https://arandjelovac.rs/example','title':{'rendered':'News &amp; Info'},'content':{'rendered':'<p>Text</p>'}}
        result=parse_municipality(json.dumps([record]),'https://arandjelovac.rs/')[0]
        self.assertEqual(result.published.hour,10);self.assertEqual(result.modified.minute,30)
        self.assertEqual(result.title,'News & Info')
    def test_wp_invalid_and_empty(self):
        self.assertEqual(parse_municipality('[]','https://arandjelovac.rs/'),())
        for raw in ['{}','not json','[{"id":1}]']:
            with self.subTest(raw=raw),self.assertRaises(SourceError):parse_municipality(raw,'https://arandjelovac.rs/')

class WaterTests(unittest.TestCase):
    def test_index_uses_content_not_only_category(self):
        rows=parse_bukulja_index(index(text='Квалитет воде · 14. октобар 2026.'),BASE,NOW)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0].published.date(),NOW.date())
    def test_index_rejects_maintenance_and_wrong_date(self):
        for raw in ['<h1>Maintenance</h1>',index(text='kein Datum')]:
            with self.subTest(raw=raw),self.assertRaises(SourceError):parse_bukulja_index(raw,BASE,NOW)
    def test_article_reads_scoped_body(self):
        raw='<h1>Прекид</h1><div class="page-content mt-6"><div><p>Прекид водоснабдевања.</p></div></div><aside>IGNORE</aside>'
        parsed=parse_bukulja_article(raw,article())
        self.assertNotIn('IGNORE',parsed.text);self.assertIn('Прекид',parsed.text)
    def test_image_only_is_explicitly_unknown(self):
        parsed=parse_bukulja_article('<h1>Вода</h1><div class="page-content"><img src="x.jpg"/></div>',article())
        self.assertTrue(parsed.image_only);self.assertEqual(water_notice(parsed)['status'],'image_only')
    def test_missing_article_content_fails(self):
        for raw in ['<h1>Вода</h1>','<h1>Вода</h1><div class="page-content"></div>']:
            with self.subTest(raw=raw),self.assertRaises(SourceError):parse_bukulja_article(raw,article())
    def test_construction_is_not_outage(self):
        self.assertEqual(water_notice(article(text='Radovi na rekonstrukciji cevovoda.'))['kind'],'water_info')
    def test_outage_without_end_not_active_measurement(self):
        row=water_notice(article(text='Prekid vodosnabdevanja. Stabilizacija tokom noci.'))
        self.assertEqual(row['status'],'unconfirmed');self.assertIsNone(row['end_at'])
    def test_street_cleaning_not_supply_restoration(self):
        self.assertNotEqual(water_notice(article(text='Radovi zavrseni, ulica je ociscena.'))['status'],'restored')
    def test_explicit_restoration(self):
        self.assertEqual(water_notice(article(text='Vodosnabdevanje je normalizovano.'))['status'],'restored')
    def test_planned_window(self):
        row=water_notice(article(title='Planski prekid vodosnabdevanja 15. oktobra 2026.',text='Doci ce do prekida vodosnabdevanja od 8 do 17 casova.'))
        self.assertEqual(row['status'],'scheduled');self.assertEqual(row['start_at'],'2026-10-15T08:00:00+02:00')
    def test_invalid_window_fails(self):
        with self.assertRaises(SourceError):water_notice(article(title='Planski prekid vodosnabdevanja 15. oktobra 2026.',text='Prekid vodosnabdevanja od 17 do 8 casova.'))

class TrafficTests(unittest.TestCase):
    def test_route_place_and_deadline_preserve_source_names(self):
        title='31.8.2026.Obustava na putu, deonica Lazarevac – Darosava (Belanovica), mesto Кruševica'
        row=parse_traffic(HEADER+traffic_row(title=title),'https://www.putevi-srbije.rs/',NOW)[0]
        self.assertEqual(row['route'],'Lazarevac – Darosava (Belanovica)')
        self.assertEqual(row['place'],'Кruševica')
        self.assertEqual(row['title'],title)
        self.assertEqual(row['deadline_date'],'2026-12-26')
    def test_cyrillic_route_and_description_fallback(self):
        row=parse_traffic(HEADER+traffic_row(title='Радови',text='Деоница Аранђеловац – Топола, место Бања.'),'https://www.putevi-srbije.rs/',NOW)[0]
        self.assertEqual(row['route'],'Аранђеловац – Топола')
        self.assertEqual(row['place'],'Бања')
    def test_missing_route_is_not_invented_from_place(self):
        row=parse_traffic(HEADER+traffic_row(),'https://www.putevi-srbije.rs/',NOW)[0]
        self.assertNotIn('route',row);self.assertNotIn('place',row)
    def test_category_deadline_and_no_fake_geolocation(self):
        row=parse_traffic(HEADER+traffic_row(),'https://www.putevi-srbije.rs/stanje/novamapa/textfile.txt',NOW)[0]
        self.assertEqual(row['kind'],'closure');self.assertEqual(row['end_at'],'2026-12-27T00:00:00+01:00')
        self.assertIsNone(row['geolocation'])
    def test_duplicate_and_distinct_same_title(self):
        rows=parse_traffic(HEADER+traffic_row()+traffic_row()+traffic_row(text='Drugi deo puta, isti naslov.'),'https://www.putevi-srbije.rs/stanje/novamapa/textfile.txt',NOW)
        self.assertEqual(len(rows),2)
    def test_deadline_passed_keeps_notice(self):
        rows=parse_traffic(HEADER+traffic_row(text='Radovi do 12.10.2026.'),'https://www.putevi-srbije.rs/stanje/novamapa/textfile.txt',NOW)
        self.assertEqual(rows[0]['status'],'deadline_passed')
    def test_bad_shape_and_unknown_category_fail(self):
        for raw in ['bad\tcolumns\n',HEADER+'one\ttwo\n',(HEADER+traffic_row()).replace('OBUSTAVE:','UNKNOWN:')]:
            with self.subTest(raw=raw),self.assertRaises(SourceError):parse_traffic(raw,'https://www.putevi-srbije.rs/stanje/novamapa/textfile.txt',NOW)
    def test_old_permanent_restriction_is_kept(self):
        row=traffic_row(title='24.10.2005. Darosava',text='Zabrana za kamione.').replace('OBUSTAVE:','ZABRANE:')
        self.assertIsNone(parse_traffic(HEADER+row,'https://www.putevi-srbije.rs/stanje/novamapa/textfile.txt',NOW)[0]['end_at'])

class EventTests(unittest.TestCase):
    def test_split_program_has_individual_titles_and_original_link(self):
        source=article(title='Филмски програм',text='14.10.\n18:00 – Film A\n20:00 - Film B')
        rows=event_items(source)
        self.assertEqual([row['title'] for row in rows],['Film A','Film B'])
        for row in rows:
            self.assertEqual(row['description'],'')
            self.assertTrue(row['program_split'])
            self.assertEqual(row['program_title'],source.title)
            self.assertEqual(row['source_url'],source.url)
            self.assertEqual(row['event_type'],'cinema')
    def test_single_event_keeps_description_and_explicit_type(self):
        row=event_items(article(title='Predstava 15. oktobra od 20 sati',text='Gostuje poznato pozoriste.'))[0]
        self.assertEqual(row['event_type'],'theatre')
        self.assertEqual(row['description'],'Gostuje poznato pozoriste.')
        self.assertNotIn('program_split',row)
    def test_body_mention_does_not_classify_unknown_event(self):
        row=event_items(article(title='Susret 15. oktobra od 20 sati',text='Bioskop radi vikendom.'))[0]
        self.assertNotIn('event_type',row)
    def test_program_splits_days_and_times(self):
        rows=event_items(article(title='Filmski program',text='14.10.\n18:00 – Film A\n20:00 - Film B\n15.10.\n18:00 – Film C'))
        self.assertEqual(len(rows),3);self.assertEqual(rows[2]['start_at'],'2026-10-15T18:00:00+02:00')
        self.assertEqual(len({r['id'] for r in rows}),3)
    def test_title_event_date_different_from_publication(self):
        row=event_items(article(title='Predstava 15. oktobra od 20 sati'))[0]
        self.assertEqual(row['start_at'],'2026-10-15T20:00:00+02:00')
    def test_ticket_sale_date_is_not_event_date(self):
        row=event_items(article(title='19. pozorisni festival',text='Rezervacija karata od 2. novembra u 10 sati.'))[0]
        self.assertEqual(row['kind'],'announcement');self.assertIsNone(row['start_at'])
    def test_bad_clock_not_silently_changed(self):
        with self.assertRaises(SourceError):event_items(article(text='14.10.\n25:00 - Film'))
    def test_no_invented_end(self):
        row=event_items(article(title='Predstava 15. oktobra od 20 sati'))[0];self.assertIsNone(row['end_at'])

class ProjectionTests(unittest.TestCase):
    def provider(self,key='jkp',**options):return NoticeProvider(key,None,options=options,clock=lambda:NOW)
    def test_unknown_old_water_notice_is_historical(self):
        row=water_notice(replace(article(text='Prekid vodosnabdevanja'),published=NOW-timedelta(days=7)))
        value=self.provider().project(NoticeSnapshot((row,),{}),NOW)
        self.assertEqual(value.items[0]['status'],'historical_unconfirmed');self.assertEqual(value.metadata['outage_notices'],0)
    def test_source_failure_is_not_empty(self):
        provider=self.provider();state=SourceState();state.accept(FetchResult(NoticeSnapshot((),{})),NOW)
        self.assertEqual(state.render(provider,NOW)['count'],0)
        state.reject(SourceError('timeout','Offline'),NOW)
        self.assertIsNone(state.render(provider,NOW)['count'])
    def test_source_frische_independent_of_old_articles(self):
        provider=self.provider('opstina');state=SourceState();state.accept(FetchResult(NoticeSnapshot((),{})),NOW)
        self.assertTrue(state.render(provider,NOW)['available']);self.assertFalse(state.render(provider,NOW+timedelta(hours=3))['available'])
    def test_traffic_filtered_and_payload_not_mutated(self):
        rows=parse_traffic(HEADER+traffic_row()+traffic_row(title='Novi Sad',text='Radovi.'),'https://www.putevi-srbije.rs/stanje/novamapa/textfile.txt',NOW)
        value=self.provider('putevi').project(NoticeSnapshot(rows,{}),NOW)
        self.assertEqual(value.count,1);self.assertIn('_match_text',rows[0]);self.assertNotIn('_match_text',value.items[0])
    def test_event_past_and_horizon_filter(self):
        rows=event_items(article(text='13.10.\n18:00 - Past\n14.10.\n18:00 - Today\n15.10.\n18:00 - Next'))
        value=self.provider('kultura').project(NoticeSnapshot(rows,{}),NOW)
        self.assertEqual(value.count,2)
    def test_count_budget_and_truncation_are_consistent(self):
        rows=tuple(item(replace(article(),id=str(i),text='x'*1200),'news') for i in range(40))
        value=self.provider('opstina').project(NoticeSnapshot(rows,{}),NOW)
        self.assertEqual(value.count,40);self.assertTrue(value.truncated);self.assertLessEqual(len(value.items),20)
        validate_projection(value,self.provider('opstina').spec)
    def test_unreasonable_future_publication_fails(self):
        row=item(replace(article(),published=NOW+timedelta(days=2)),'news')
        with self.assertRaises(SourceError):self.provider('opstina').project(NoticeSnapshot((row,),{}),NOW)

class FetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_water_cache_and_no_api_or_pagination(self):
        class HTTP:
            observations=[]
            def __init__(self):self.calls=[]
            def clear_observations(self):pass
            async def get_text(self,url,**kwargs):
                self.calls.append(url)
                return index() if url==BASE else '<h1>Прекид</h1><div class="page-content"><p>Prekid vodosnabdevanja.</p></div>'
        http=HTTP();provider=NoticeProvider('jkp',http,clock=lambda:NOW)
        await provider.async_fetch();await provider.async_fetch()
        self.assertEqual(http.calls,[BASE,BASE+'/primer',BASE])
    async def test_json_error_propagates(self):
        class HTTP:
            observations=[]
            def clear_observations(self):pass
            async def get_text(self,*args,**kwargs):return 'not json'
        with self.assertRaises(SourceError):await NoticeProvider('opstina',HTTP()).async_fetch()
