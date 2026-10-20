"""Offline contracts for local sources, using reduced structural examples."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta
import json
import unittest

import bootstrap
from live_test.common.models import FetchResult, SourceError, SourceState, validate_projection
from live_test.providers.notices.parsers import (Article,bukulja_next_page,event_items,item,local_works_related,matches_area,municipality_relevant,parse_bukulja_article,
    parse_bukulja_index,parse_feed,parse_manifestations,parse_municipality,parse_museum_listings,parse_traffic,water_notice,water_service_related)
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
    def test_deadline_in_heading_is_not_a_calendar_event(self):
        row=event_items(article(title='Konkurs za prijave do 2.11.2026.'))[0]
        self.assertEqual(row['kind'],'announcement');self.assertNotIn('event_date',row)
    def test_trilogy_presentation_is_a_reading(self):
        row=event_items(article(title='Представљање завршног дела трилогије Бреме',text='15. октобра 2026. од 19 сати'))[0]
        self.assertEqual(row['event_type'],'reading')
        self.assertEqual(row['start_at'],'2026-10-15T19:00:00+02:00')
    def test_numeric_date_only_does_not_invent_midnight(self):
        row=event_items(article(title='Svetski dan turizma 27.09.2026.',image_only=True,text=''))[0]
        self.assertEqual(row['event_date'],'2026-09-27');self.assertIsNone(row['start_at'])
        self.assertEqual(row['status'],'date_only')
    def test_named_date_without_time_is_kept_as_date_only(self):
        row=event_items(article(title='Koncert 2. novembra 2026.'))[0]
        self.assertEqual(row['event_date'],'2026-11-02');self.assertIsNone(row['start_at'])
    def test_calendar_reference_is_not_a_confirmed_year(self):
        raw='<h2>novogodišnji bazar<br>decembar</h2><a href="/bazar/">detaljnije</a><h2>festival</h2><a href="/festival/">detaljnije</a>'
        rows=parse_manifestations(raw,'https://bukovickabanja.rs/manifestacije/')
        self.assertEqual(len(rows),2);self.assertEqual(rows[0]['season_label'],'decembar')
        self.assertFalse(rows[0]['date_confirmed']);self.assertIsNone(rows[0]['published_at'])
        self.assertIsNone(rows[0]['start_at']);self.assertNotIn('event_date',rows[0])
    def test_missing_or_foreign_calendar_links_fail(self):
        for raw in ['<h2>Keine Veranstaltungen</h2>','<h2>Basar</h2><a href="https://evil.test/">detaljnije</a>']:
            with self.subTest(raw=raw),self.assertRaises(SourceError):parse_manifestations(raw,'https://bukovickabanja.rs/manifestacije/')
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
    def test_non_cinema_announcements_survive_full_programme(self):
        movies=tuple(item(replace(article(),id=f'film-{i}'),'event',event_type='cinema',start_at=(NOW+timedelta(hours=i+1)).isoformat()) for i in range(30))
        festival=item(replace(article(),id='festival',title='Pozorisni festival'),'announcement')
        value=self.provider('kultura').project(NoticeSnapshot((*movies,festival),{}),NOW)
        self.assertEqual(value.count,31);self.assertTrue(value.truncated)
        self.assertEqual(value.items[0]['id'],'festival')
    def test_date_only_past_removed_and_future_kept(self):
        rows=tuple(event_items(article(title=title))[0] for title in ['Koncert 27.09.2026.','Koncert 14.10.2026.','Koncert 2.11.2026.'])
        value=self.provider('library').project(NoticeSnapshot(rows,{}),NOW)
        self.assertEqual([r['event_date'] for r in value.items],['2026-10-14','2026-11-02'])
    def test_seasons_remain_undated_outside_news_lookback(self):
        rows=parse_manifestations('<h2>Bazar<br>decembar</h2><a href="/bazar/">detaljnije</a>','https://bukovickabanja.rs/manifestacije/')
        value=self.provider('manifestations').project(NoticeSnapshot(rows,{}),NOW)
        self.assertEqual(value.count,1);self.assertFalse(value.items[0]['date_confirmed'])
        validate_projection(value,self.provider('manifestations').spec)
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


class SustainableNoticeTests(unittest.TestCase):
    def test_repair_completion_is_not_supply_confirmation(self):
        a=article(title='Nakon uspešno izvedenih radova na sanaciji kvarova na magistralnom cevovodu',
                  text='Ekipe su očistile i oprale Bukuljsku ulicu.')
        self.assertEqual(water_notice(a)['status'],'repair_completed')

    def test_future_conditional_and_negative_restoration_are_not_facts(self):
        for text in ['Očekuje se da bude uspostavljeno vodosnabdevanje.',
                     'Planirano je da bude uspostavljeno vodosnabdevanje.',
                     'Ukoliko sve bude po planu, biće uspostavljeno vodosnabdevanje.',
                     'Nije uspostavljeno vodosnabdevanje.']:
            with self.subTest(text=text):self.assertNotEqual(water_notice(article(text=text))['status'],'restored')

    def test_future_completed_repairs_are_not_a_reported_completion(self):
        self.assertNotEqual(water_notice(article(text='Očekuje se da radovi budu završeni.'))['status'],'repair_completed')

    def test_education_does_not_count_as_water_service_news(self):
        a=article(title='Студенти у посети постројењу за пречишћавање отпадних вода у Бањи')
        self.assertFalse(water_service_related(a))
        self.assertTrue(water_service_related(article(title='Radovi na vodovodu u Studentskoj ulici')))

    def test_local_roadworks_and_water_stay_separate(self):
        self.assertTrue(local_works_related(article(title='Niskogradnja popunjava udarne rupe u Tuležima')))
        self.assertFalse(local_works_related(article(title='Niskogradnja zida vodovodne šahte')))

    def test_tax_notice_is_relevant_across_categories(self):
        self.assertTrue(municipality_relevant(article(title='Spisak poreskih rešenja za utvrđivanje poreza na imovinu')))
        self.assertFalse(municipality_relevant(article(title='Odgovori na pitanja JN-24/26')))
        self.assertFalse(municipality_relevant(article(title='Oglas – INTERNI KONKURS')))
        self.assertFalse(municipality_relevant(article(title='Izmena Plana javnih nabavki')))

    def test_alternative_outage_wording_is_not_lost_before_reading(self):
        a=article(title='Obaveštenje',text='Potrošači ostaju bez snabdevanja vodom do završetka radova.')
        self.assertTrue(water_service_related(a))
        self.assertEqual(water_notice(a)['status'],'unconfirmed')

    def test_numeric_water_window_dates_are_parsed(self):
        a=article(title='Planski prekid 15.10.2026.',text='Doci ce do prekida vodosnabdevanja od 8 do 17 casova.')
        self.assertEqual(water_notice(a)['start_at'],'2026-10-15T08:00:00+02:00')

    def test_museum_listings_have_no_invented_date(self):
        rows=parse_museum_listings('<h1>Актуелне изложбе у музеју</h1><h2>„У дијалогу“ ретроспективна изложба</h2><h2>Promocija knjige 1.7.2025.</h2>', 'https://nmar.rs/aktuelne-izlozbe-u-muzeju/')
        self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['published_at'])
        self.assertIsNone(rows[0]['start_at']);self.assertFalse(rows[0]['date_confirmed'])
        value=NoticeProvider('museum',None).project(NoticeSnapshot(rows,{}),NOW)
        self.assertEqual(value.count,1);validate_projection(value,NoticeProvider('museum',None).spec)

    def test_unknown_museum_markup_is_not_a_false_zero(self):
        with self.assertRaises(SourceError):parse_museum_listings('<h1>Maintenance</h1>','https://nmar.rs/')

    def test_archive_next_page_keeps_bounded_same_source_url(self):
        self.assertEqual(bukulja_next_page(index()+'<a href="/vesti?page=2">Следећа</a>',BASE),BASE+'?page=2')
        self.assertIsNone(bukulja_next_page(index(),BASE))
        with self.assertRaises(SourceError):bukulja_next_page(index()+'<a href="/vesti?redirect=evil">Следећа</a>',BASE)

    def test_elapsed_planned_water_window_is_not_silently_removed(self):
        a=article(title='Planski prekid vodosnabdevanja 14. oktobra 2026.',text='Doci ce do prekida vodosnabdevanja od 8 do 12 casova.')
        provider=NoticeProvider('jkp',None)
        result=provider.project(NoticeSnapshot((water_notice(a),),{}),NOW)
        self.assertEqual(result.count,1)
        self.assertEqual(result.items[0]['status'],'planned_end_passed')
        self.assertEqual(result.metadata['outage_notices'],1)

    def test_old_elapsed_window_is_history_not_supply_confirmation(self):
        a=replace(article(title='Planski prekid vodosnabdevanja 7. oktobra 2026.',text='Doci ce do prekida vodosnabdevanja od 8 do 12 casova.'),published=NOW-timedelta(days=7))
        result=NoticeProvider('jkp',None).project(NoticeSnapshot((water_notice(a),),{}),NOW)
        self.assertEqual(result.items[0]['status'],'historical_unconfirmed')
        self.assertEqual(result.metadata['outage_notices'],0)

    def test_open_incident_precedes_newer_information(self):
        incident=water_notice(replace(article(text='Prekid vodosnabdevanja bez kraja.'),id='incident',published=NOW-timedelta(days=1)))
        info=water_notice(article(text='Radovi na cevovodu.'))
        result=NoticeProvider('jkp',None).project(NoticeSnapshot((info,incident),{}),NOW)
        self.assertEqual(result.items[0]['id'],'incident')

    def test_default_traffic_covers_nearby_routes_without_backa_topola(self):
        raw=HEADER+traffic_row(title='Radovi deonica Topola - Bozurnja')+traffic_row(title='Radovi Bačka Topola - Novi Sad',text='Od 8 do 17 radovi.')
        rows=parse_traffic(raw,'https://www.putevi-srbije.rs/',NOW)
        result=NoticeProvider('putevi',None).project(NoticeSnapshot(rows,{}),NOW)
        self.assertEqual(result.count,1)
        self.assertIn('Topola',result.items[0]['matched_areas'])
        custom=NoticeProvider('putevi',None,options={'areas':'Aranđelovac'})
        self.assertEqual(custom.project(NoticeSnapshot(rows,{}),NOW).count,0)


class SustainableFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_museum_supplement_failure_is_visible_without_losing_feed(self):
        class HTTP:
            def clear_observations(self):pass
            async def get_text(self,url,**kwargs):
                return feed(url='https://nmar.rs/example') if url.endswith('/feed/') else '<h1>Maintenance</h1>'
        result=await NoticeProvider('museum',HTTP(),clock=lambda:NOW).async_fetch()
        self.assertEqual(len(result.payload.records),1)
        self.assertFalse(result.payload.metadata['complete_for_window'])
        self.assertEqual(result.payload.metadata['supplement_error']['code'],'exhibition_structure')

    async def test_municipal_default_uses_all_categories_and_pagination(self):
        from urllib.parse import parse_qs,urlsplit
        class HTTP:
            def __init__(self):self.calls=[]
            def clear_observations(self):pass
            async def get_text(self,url,**kwargs):
                self.calls.append(url);page=int(parse_qs(urlsplit(url).query)['page'][0])
                ids=range(1,101) if page==1 else [101]
                return json.dumps([{'id':i,'date_gmt':'2026-10-13T08:00:00','link':f'https://arandjelovac.rs/post-{i}',
                    'title':{'rendered':'Javna nabavka JN-1/26' if i<101 else 'Poreska rešenja'},'content':{'rendered':'Text'}} for i in ids])
        http=HTTP();provider=NoticeProvider('opstina',http,clock=lambda:NOW)
        result=await provider.async_fetch()
        self.assertEqual(len(http.calls),2)
        self.assertNotIn('categories=',http.calls[0]);self.assertIn('after=',http.calls[0])
        self.assertEqual([r['title'] for r in result.payload.records],['Poreska rešenja'])
        self.assertTrue(result.payload.metadata['complete_for_window'])
        self.assertEqual(result.payload.metadata['excluded_articles'],100)
        custom=HTTP();await NoticeProvider('opstina',custom,options={'categories':'47'},clock=lambda:NOW).async_fetch()
        self.assertIn('categories=47',custom.calls[0])

    async def test_bukulja_follows_recent_pages_and_refreshes_changed_articles(self):
        class HTTP:
            def __init__(self):self.calls=[];self.updated=False
            def clear_observations(self):pass
            async def get_text(self,url,**kwargs):
                self.calls.append(url)
                if url==BASE:return index()+'<a href="/vesti?page=2">Следећа</a>'
                if url==BASE+'?page=2':return index(title='Vodovodna mreža',text='13. октобар 2026.').replace('/primer','/drugi')
                text='Vodosnabdevanje je normalizovano.' if self.updated else 'Prekid vodosnabdevanja.'
                return '<h1>Vodovod</h1><div class="page-content"><p>'+text+'</p></div>'
        http=HTTP();clock=[NOW];provider=NoticeProvider('jkp',http,clock=lambda:clock[0])
        first=await provider.async_fetch();self.assertEqual(len(first.payload.records),2)
        self.assertEqual(first.payload.metadata['pages_checked'],2)
        self.assertEqual(first.payload.records[0]['status'],'unconfirmed')
        http.updated=True;clock[0]+=timedelta(minutes=15)
        second=await provider.async_fetch()
        self.assertEqual(second.payload.records[0]['status'],'restored')
        self.assertEqual(http.calls.count(BASE+'/primer'),2)

    async def test_bukulja_repeat_page_fails_instead_of_false_empty(self):
        class HTTP:
            def clear_observations(self):pass
            async def get_text(self,*args,**kwargs):return index()+'<a href="/vesti?page=2">Следећа</a>'
        with self.assertRaises(SourceError):await NoticeProvider('jkp',HTTP(),clock=lambda:NOW).async_fetch()
