import pytest
from bson import ObjectId


@pytest.fixture(scope='module')
def make_beat_crontab():
    def _make_beat_crontab(minute='*', hour='*', day_of_week='*', day_of_month='*', month_of_year='*') -> dict:
        return {
            'type': 'crontab',
            'config': {
                'minute': minute,
                'hour': hour,
                'day_of_week': day_of_week,
                'day_of_month': day_of_month,
                'month_of_year': month_of_year
            }
        }
    return _make_beat_crontab


@pytest.fixture(scope='module')
def make_language():
    def _make_language(code: str = 'en', name_en: str = 'language_en', name_native: str = 'language_native') -> dict:
        return {
            'code': code,
            'name_en': name_en,
            'name_native': name_native
        }
    return _make_language


@pytest.fixture(scope='module')
def make_config():
    def _make_config(sub_domain: str = 'en', format: str = 'nopic',
                     queue: str = 'offliner_default') -> dict:
        return {
            'task_name': 'offliner.mwoffliner',
            'queue': queue,
            'image': {
                'name': 'openzim/mwoffliner',
                'tag': 'latest'
            },
            'flags': {
                'mwUrl': 'https://{}.wikipedia.org'.format(sub_domain),
                'adminEmail': 'test@kiwix.org',
                'format': format,
                'withZimFullTextIndex': True
            },
            'warehouse_path': '/wikipedia'
        }
    return _make_config


@pytest.fixture(scope='module')
def make_schedule(database, make_beat_crontab, make_language, make_config):
    schedule_ids = []

    def _make_schedule(name: str = 'schedule_name', category: str = 'wikipedia',
                       beat: dict = None, tags: list = ['nopic'],
                       language: dict = None, config: dict = None) -> dict:
        document = {
            '_id': ObjectId(),
            'name': name,
            'category': category,
            'enabled': True,
            'beat': beat or make_beat_crontab(),
            'language': language or make_language(),
            'tags': tags,
            'config': config or make_config()
        }
        schedule_id = database.schedules.insert_one(document).inserted_id
        schedule_ids.append(schedule_id)
        return document

    yield _make_schedule

    database.schedules.delete_many({'_id': {'$in': schedule_ids}})


@pytest.fixture(scope='module')
def schedule(make_schedule, make_beat_crontab):
    return make_schedule()


@pytest.fixture(scope='module')
def schedules(make_schedule, make_config, make_beat_crontab, make_language):
    schedules = []
    for index in range(38):
        name = 'schedule_{}'.format(index)
        schedule = make_schedule(name)
        schedules.append(schedule)

    # custom schedules for query lookup
    schedules.append(make_schedule(name="wikipedia_fr_all_maxi"))
    schedules.append(make_schedule(name="wikipedia_fr_all_nopic"))
    schedules.append(make_schedule(name="wikipedia_bm_all_nopic"))
    schedules.append(make_schedule(language=make_language(code="fr"),
                                   name="schedule_43"))
    schedules.append(make_schedule(language=make_language(code="bm"),
                                   name="schedule_44"))
    schedules.append(make_schedule(category="phet", name="schedule_45"))
    schedules.append(make_schedule(category="wikibooks", name="schedule_46"))
    schedules.append(make_schedule(tags=["all"], name="schedule_47"))
    schedules.append(make_schedule(tags=["all", "mini"], name="schedule_48"))
    schedules.append(make_schedule(tags=["mini", "nopic"], name="schedule_49"))
    schedules.append(make_schedule(config=make_config(queue='small')))
    schedules.append(make_schedule(config=make_config(queue='small'),
                                   name="youtube_fr_all_novid",
                                   language=make_language(code="fr"),
                                   category="other", tags=["nopic", "novid"]))
    return schedules
