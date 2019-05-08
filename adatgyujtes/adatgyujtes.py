#!/usr/bin/env python

import datetime
from dateutil import tz
import json
import math
import operator
import optparse
import os
import re
import shutil
import sys
import threading
import time
import webbrowser
from collections import namedtuple, OrderedDict
from functools import wraps
from getpass import getpass

import pdb

# Py3k compat.
if sys.version_info[0] == 3:
    binary_types = (bytes, bytearray)
    decode_handler = 'backslashreplace'
    numeric = (int, float)
    unicode_type = str
    from io import StringIO
else:
    binary_types = (buffer, bytes, bytearray)
    decode_handler = 'replace'
    numeric = (int, long, float)
    unicode_type = unicode
    from StringIO import StringIO

try:
    from flask import (
        Flask, abort, escape, flash, jsonify, make_response, Markup, redirect,
        render_template, request, session, url_for, Response)
except ImportError:
    raise RuntimeError('Unable to import flask module. Install by running '
                       'pip install flask')

try:
    from pygments import formatters, highlight, lexers
except ImportError:
    import warnings
    warnings.warn('pygments library not found.', ImportWarning)
    syntax_highlight = lambda data: '<pre>%s</pre>' % data
else:
    def syntax_highlight(data):
        if not data:
            return ''
        lexer = lexers.get_lexer_by_name('sql')
        formatter = formatters.HtmlFormatter(linenos=False)
        return highlight(data, lexer, formatter)

try:
    from peewee import __version__
    peewee_version = tuple([int(p) for p in __version__.split('.')])
except ImportError:
    raise RuntimeError('Unable to import peewee module. Install by running '
                       'pip install peewee')
else:
    if peewee_version <= (3, 0, 0):
        raise RuntimeError('Peewee >= 3.0.0 is required. Found version %s. '
                           'Please update by running pip install --update '
                           'peewee' % __version__)

from peewee import *
from peewee import IndexMetadata
from peewee import sqlite3
from playhouse.dataset import DataSet
from playhouse.migrate import migrate


CUR_DIR = os.path.realpath(os.path.dirname(__file__))
DEBUG = False
MAX_RESULT_SIZE = 1000
ROWS_PER_PAGE = 50
SECRET_KEY = 'sqlite-database-browser-0.1.0'

import config

ADATGYUJTES_CONFIG = config.CONFIG_TEST

app = Flask(
    __name__,
    static_folder=os.path.join(CUR_DIR, 'static'),
    template_folder=os.path.join(CUR_DIR, 'templates'))
app.config.from_object(__name__)
dataset = None
live_dataset = None
migrator = None
timezone_offset = 0
#
# Database metadata objects.
#

TriggerMetadata = namedtuple('TriggerMetadata', ('name', 'sql'))

ViewMetadata = namedtuple('ViewMetadata', ('name', 'sql'))

#
# Database helpers.
#

class SqliteDataSet(DataSet):
    @property
    def filename(self):
        db_file = dataset._database.database
        if db_file.startswith('file:'):
            db_file = db_file[5:]
        return os.path.realpath(db_file.rsplit('?', 1)[0])

    @property
    def is_readonly(self):
        db_file = dataset._database.database
        return db_file.endswith('?mode=ro')

    @property
    def base_name(self):
        return os.path.basename(self.filename)

    @property
    def created(self):
        stat = os.stat(self.filename)
        return datetime.datetime.fromtimestamp(stat.st_ctime)

    @property
    def modified(self):
        stat = os.stat(self.filename)
        return datetime.datetime.fromtimestamp(stat.st_mtime)

    @property
    def size_on_disk(self):
        stat = os.stat(self.filename)
        return stat.st_size

    def get_indexes(self, table):
        return dataset._database.get_indexes(table)

    def get_all_indexes(self):
        cursor = self.query(
            'SELECT name, sql FROM sqlite_master '
            'WHERE type = ? ORDER BY name',
            ('index',))
        return [IndexMetadata(row[0], row[1], None, None, None)
                for row in cursor.fetchall()]

    def get_columns(self, table):
        return dataset._database.get_columns(table)

    def get_foreign_keys(self, table):
        return dataset._database.get_foreign_keys(table)

    def get_triggers(self, table):
        cursor = self.query(
            'SELECT name, sql FROM sqlite_master '
            'WHERE type = ? AND tbl_name = ?',
            ('trigger', table))
        return [TriggerMetadata(*row) for row in cursor.fetchall()]

    def get_all_triggers(self):
        cursor = self.query(
            'SELECT name, sql FROM sqlite_master '
            'WHERE type = ? ORDER BY name',
            ('trigger',))
        return [TriggerMetadata(*row) for row in cursor.fetchall()]

    def get_all_views(self):
        cursor = self.query(
            'SELECT name, sql FROM sqlite_master '
            'WHERE type = ? ORDER BY name',
            ('view',))
        return [ViewMetadata(*row) for row in cursor.fetchall()]

    def get_virtual_tables(self):
        cursor = self.query(
            'SELECT name FROM sqlite_master '
            'WHERE type = ? AND sql LIKE ? '
            'ORDER BY name',
            ('table', 'CREATE VIRTUAL TABLE%'))
        return set([row[0] for row in cursor.fetchall()])

    def get_corollary_virtual_tables(self):
        virtual_tables = self.get_virtual_tables()
        suffixes = ['content', 'docsize', 'segdir', 'segments', 'stat']
        return set(
            '%s_%s' % (virtual_table, suffix) for suffix in suffixes
            for virtual_table in virtual_tables)

#
# Flask views.
#

@app.route('/')
def index():
    return render_template('index.html', sqlite=sqlite3)

@app.route('/thanks/')
def thanks():
    return render_template('thanks.html')

@app.route('/faq/')
def faq():
    return render_template('faq.html')

@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == app.config['PASSWORD']:
            session['authorized'] = True
            return redirect(session.get('next_url') or url_for('index'))
        flash('A megadott jelszó helytelen.', 'danger')
    return render_template('login.html')

@app.route('/logout/', methods=['GET'])
def logout():
    session.pop('authorized', None)
    return redirect(url_for('login'))

def require_table(fn):
    @wraps(fn)
    def inner(table, *args, **kwargs):
        if table not in dataset.tables:
            abort(404)
        return fn(table, *args, **kwargs)
    return inner

def get_request_data():
    if request.method == 'POST':
        return request.form
    return request.args

@app.route('/stop_collecting/')
def stop_collecting():
    return render_template('stop_collecting.html')

@app.route('/copy/')
def create_copy_queries():
    global dataset
    shutil.copy(ADATGYUJTES_CONFIG["DATABASE_PATH"], ADATGYUJTES_CONFIG["COPIED_DATABASE_PATH"])
    dataset = SqliteDataSet('sqlite:///{path}'.format(path=ADATGYUJTES_CONFIG["COPIED_DATABASE_PATH"]), bare_fields=True)
    return redirect(url_for('table_domains'), code=302)

@app.route('/domains/')
def table_domains():
    table = "queries"

    page_number = request.args.get('page') or ''
    page_number = int(page_number) if page_number.isdigit() else 1

    dataset.update_cache(table)
    ds_table = dataset[table]

    rows_per_page = app.config['ROWS_PER_PAGE']

    dom_field = None
    if ('domain' in ds_table.model_class._meta.fields):
        dom_field = ds_table.model_class._meta.fields['domain']

    delete_domain = request.args.get('delete')
    if delete_domain:
        ds_table.delete(domain=delete_domain)
        open_live_dataset_table(table).delete(domain=delete_domain)

    search = request.args.get('search')
    if search:
        query = ds_table.model_class.select(dom_field, fn.COUNT(dom_field).alias('ct')).group_by(dom_field).where(dom_field.contains(search)).order_by(fn.COUNT(dom_field).desc())
    else:
        query = ds_table.model_class.select(dom_field, fn.COUNT(dom_field).alias('ct')).group_by(dom_field).order_by(fn.COUNT(dom_field).desc())

    #pdb.set_trace()

    total_rows = query.count()
    total_pages = int(math.ceil(total_rows / float(rows_per_page)))
    # Restrict bounds.
    page_number = min(page_number, total_pages)
    page_number = max(page_number, 1)

    previous_page = page_number - 1 if page_number > 1 else None
    next_page = page_number + 1 if page_number < total_pages else None



    query = query.paginate(page_number, rows_per_page)

    ordering = request.args.get('ordering')
    if ordering:
        field = ds_table.model_class._meta.columns[ordering.lstrip('-')]
        if ordering.startswith('-'):
            field = field.desc()
        query = query.order_by(field)

    field_names = ds_table.columns
    columns = [f.column_name for f in ds_table.model_class._meta.sorted_fields]

    table_sql = dataset.query(
        'SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type = ?',
        [table, 'table']).fetchone()[0]

    return render_template(
        'table_domains.html',
        columns=columns,
        ds_table=ds_table,
        field_names=field_names,
        next_page=next_page,
        ordering=ordering,
        page=page_number,
        previous_page=previous_page,
        query=query,
        total_pages=total_pages,
        total_rows=total_rows,
        search=search,
        true_content=None)


import azure.storage.blob as blob
import azure.storage.common as common

@app.route('/upload/')
def upload_page():
    return render_template(
        "upload.html",
        upload_path="example.path")

import threading
import requests
import queue
import encryption
import zipfile
from event import QueueEvent

progress_queue = queue.Queue()

global_lock = threading.Lock()

def queue_event_data(data):
    """Queue an SSE with dictionary data"""
    print("Queuing {}".format(data), file=sys.stderr)
    progress_queue.put(QueueEvent(json.dumps(data)))
    time.sleep(0)

def progress_callback(current, total):
    """Put the Azure upload progress into the inter-thread queue"""
    print("Progress callback.", file=sys.stderr)
    queue_event_data({
        "type": "upload_progress",
        "progress_data": {
            "current": current,
            "total": total,
            "finished": total <= current
        }
    })

def get_azure_credentials():
    """Get the Azure credentials for the storage account"""
    # Get the credentials from the Azure API endpoint
    credentials = requests.post(url=ADATGYUJTES_CONFIG["SAS_URL"], json={"id": ADATGYUJTES_CONFIG["ADATGYUJTES_ID"]}).json()
    # In case of a server error the API responds with a JSON with an error field in it
    if "error" in credentials:
        raise Exception("Nem tudtuk hitelesíteni az eszközt: " + credentials["error"])
    return credentials

def zip_database():
    """Zip up the database"""
    with zipfile.ZipFile(ADATGYUJTES_CONFIG["ZIPPED_DB_NAME"], 'w', zipfile.ZIP_DEFLATED) as dbzip:
        dbzip.write(ADATGYUJTES_CONFIG["DATABASE_PATH"])

def init_key_resolver(credentials):
    """Load the key resolver from the received credentials"""
    # The encode method must be called on the key, since it is a string and we need bytes here
    key = credentials["rsaPublicKey"].replace(r'\n','\n').encode()
    print("KEY is: ", key)
    kek = encryption.PublicRSAKeyWrapper(public_key=key)

    key_resolver = encryption.KeyResolver()
    key_resolver.put_key(key=kek)
    return kek, key_resolver.resolve_key

def init_blob_service(credentials):
    # Initialize the blob service from the Azure SDK
    blobService = blob.BlockBlobService(account_name=credentials["accountName"], account_key=None, sas_token=credentials["sasToken"])
    # Load the public key for the encryption. The key resolver object implements a specific interface defined by the Azure SDK
    # This would be an unnecessary overhead since we only have the one public key, but there's no way around it
    blobService.key_encryption_key, blobService.key_resolver_function = init_key_resolver(credentials=credentials)
    # Change the upload parameters, so that the progress callback gets called more frequently, this might also raise the robustness of the upload
    blobService.MAX_SINGLE_PUT_SIZE = 4*1024*1024
    blobService.MAX_BLOCK_SIZE = 4*1024*1024
    return blobService

def upload_task():
    """Start the database upload."""
    try:
        # Acquire global lock.
        if not global_lock.acquire(False):
            raise AssertionError("Couldn't acquire global lock.")
        # Zip database
        print("Zipping database...", file=sys.stderr)
        queue_event_data({
            "type": "started",
            "subject": "compress"
        })
        zip_database()
        queue_event_data({
            "type": "completed",
            "subject": "compress"
        })
        # Get Azure credentials
        print("Getting credentials...", file=sys.stderr)
        queue_event_data({
            "type": "started",
            "subject": "authenticate"
        })
        credentials = get_azure_credentials()
        if all(s in credentials for s in ('accountName', 'sasToken', 'containerName', 'id', 'rsaPublicKey')):
            # Initialize the Azure blob service
            print("Initializing Azure blob service...", file=sys.stderr)
            blobService = init_blob_service(credentials=credentials)
            queue_event_data({
                "type": "completed",
                "subject": "authenticate"
            })
            queue_event_data({
                "type": "started",
                "subject": "upload"
            })
            # Create the blob
            blobService.create_blob_from_path(
                container_name=credentials["containerName"],
                blob_name=credentials["id"]+ "_" + str(datetime.datetime.utcnow().isoformat()) + ".zip",
                file_path=ADATGYUJTES_CONFIG["ZIPPED_DB_NAME"],
                progress_callback=progress_callback,
                timeout=200)
            queue_event_data({
                "type": "completed",
                "subject": "upload"
            })
        else:
            raise AssertionError("Incorrect Azure credentials received.")
        # Release global lock
        global_lock.release()
        print("Upload finished.", file=sys.stderr)
    except Exception as e:
        print(e, file=sys.stderr)
        queue_event_data({
            "type": "error",
            "message": str(e)
        })
    finally:
        # We absolutely have to release the lock, even if an error occurs
        if global_lock.locked():
            global_lock.release()

def start_upload():
    """Upload the database to an Azure blob container."""
    # Lock object so a duplicate upload can't be started
    global global_lock
    try:
        # Check if the lock is open
        if global_lock.locked():
            raise AssertionError("Global lock is locked. Upload probably already underway.")
        # Start the upload in a separate thread
        print("Starting upload thread...", file=sys.stderr)
        threading.Thread(target=upload_task).start()
    except AssertionError as ae:
        print(ae, file=sys.stderr)
        raise ae

@app.route('/upload_database/')
def upload_database():
    """Simple endpoint that starts the upload in a separate thread."""
    try:
        print("Trying to start upload thread...", file=sys.stderr)
        start_upload()
        # If the upload started successfully, notify the client about it
        return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 
    except Exception as ex:
        print(ex, file=sys.stderr)
        return json.dumps({'success':False, 'error_message': str(ex)}), 409, {'ContentType':'application/json'}

@app.route('/upload_progress/')
def upload_progress():
    """Keep the client up to date about the progress of the upload."""
    try:
        def upload_event_stream():
            """Async event stream callback."""
            try:
                stream_active = True
                while stream_active:
                    print("Event stream callback.", file=sys.stderr)
                    # Get upload progress from inter-thread queue
                    progress_data = progress_queue.get(block=True, timeout=30)
                    print("Yielding: {}".format(progress_data.message()), file=sys.stderr)
                    # Send the progress to the client
                    yield progress_data.message()
                    if ("error" in progress_data.message() or '"type": "completed", "subject": "upload"' in progress_data.message()):
                        stream_active = False
            except Exception as ex:
                print("Event stream encountered an error." + str(ex), file=sys.stderr)
                stream_active = False
        return Response(upload_event_stream(), mimetype='text/event-stream')
    except Exception as ex:
        print(ex, file=sys.stderr)
        return str(ex), 500, {'ContentType':'application/json'}

@app.route('/timezone/')
def timezone_information():
    global offset
    offset = request.args.get('offset') or 0
    offset = int(offset)
    print("Offset is: ", offset)
    # If the upload started successfully, notify the client about it
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 


def open_live_dataset_table(table):
    # Opening live dataset for delete to remain persistent
    live_dataset.connect()
    live_dataset.update_cache(table)
    return live_dataset[table]

@app.route('/queries/')
def table_queries():
    table="queries"

    page_number = request.args.get('page') or ''
    page_number = int(page_number) if page_number.isdigit() else 1

    dataset.update_cache(table)
    ds_table = dataset[table]

    rows_per_page = app.config['ROWS_PER_PAGE']

    delete_index = request.args.get('delete')
    if delete_index:
        ds_table.delete(id=delete_index)
        open_live_dataset_table(table).delete(id=delete_index)

    search = request.args.get('search')
    if search:
        query = ds_table.model_class.select().where(ds_table.model_class._meta.fields['domain'].contains(search))
    else:
        query = ds_table.all()

    total_rows = query.count()
    total_pages = int(math.ceil(total_rows / float(rows_per_page)))
    # Restrict bounds.
    page_number = min(page_number, total_pages)
    page_number = max(page_number, 1)

    previous_page = page_number - 1 if page_number > 1 else None
    next_page = page_number + 1 if page_number < total_pages else None

    

    query = query.paginate(page_number, rows_per_page)

    ordering = request.args.get('ordering')
    if ordering:
        field = ds_table.model_class._meta.columns[ordering.lstrip('-')]
        if ordering.startswith('-'):
            field = field.desc()
        query = query.order_by(field)

    field_names = ds_table.columns
    columns = [f.column_name for f in ds_table.model_class._meta.sorted_fields]

    table_sql = dataset.query(
        'SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type = ?',
        [table, 'table']).fetchone()[0]
    
    return render_template(
        'table_queries.html',
        columns=columns,
        ds_table=ds_table,
        field_names=field_names,
        next_page=next_page,
        ordering=ordering,
        page=page_number,
        previous_page=previous_page,
        query=query,
        total_pages=total_pages,
        total_rows=total_rows,
        search=search,
        true_content=True)

@app.route('/full/')
def table_full():
    live_dataset.connect()
    dataset = live_dataset # Doesnt override global instance, variable is local.
    table = "queries"

    page_number = request.args.get('page') or ''
    page_number = int(page_number) if page_number.isdigit() else 1

    dataset.update_cache(table)
    ds_table = dataset[table]

    rows_per_page = app.config['ROWS_PER_PAGE']

    search = request.args.get('search')
    if search:
        query = ds_table.model_class.select().where(ds_table.model_class._meta.fields['domain'].contains(search))
    else:
        query = ds_table.all()

    total_rows = query.count()
    total_pages = int(math.ceil(total_rows / float(rows_per_page)))
    # Restrict bounds.
    page_number = min(page_number, total_pages)
    page_number = max(page_number, 1)

    previous_page = page_number - 1 if page_number > 1 else None
    next_page = page_number + 1 if page_number < total_pages else None

    delete_index = request.args.get('delete')
    if delete_index:
        ds_table.delete(id=delete_index)

    query = query.paginate(page_number, rows_per_page)

    ordering = request.args.get('ordering')
    if ordering:
        field = ds_table.model_class._meta.columns[ordering.lstrip('-')]
        if ordering.startswith('-'):
            field = field.desc()
        query = query.order_by(field)

    field_names = ds_table.columns
    columns = [f.column_name for f in ds_table.model_class._meta.sorted_fields]

    table_sql = dataset.query(
        'SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type = ?',
        [table, 'table']).fetchone()[0]

    return render_template(
        'table_queries_full.html',
        columns=columns,
        ds_table=ds_table,
        field_names=field_names,
        next_page=next_page,
        ordering=ordering,
        page=page_number,
        previous_page=previous_page,
        query=query,
        total_pages=total_pages,
        total_rows=total_rows,
        search=search,
        true_content=True)

@app.route('/delete_databases/')
def delete_databases():
    path =  ADATGYUJTES_CONFIG["COPIED_DATABASE_PATH"]
    origin_path = ADATGYUJTES_CONFIG["DATABASE_PATH"]
    if os.path.exists(path):
        if not dataset._database.is_closed():
            dataset.close()
        os.remove(path) #TODO
    else:
        print("The file does not exist at location: ", path)
    return redirect(url_for('thanks'), code=302)



@app.template_filter('format_index')
def format_index(index_sql):
    split_regex = re.compile(r'\bon\b', re.I)
    if not split_regex.search(index_sql):
        return index_sql

    create, definition = split_regex.split(index_sql)
    return '\nON '.join((create.strip(), definition.strip()))

@app.template_filter('value_filter')
def value_filter(value, max_length=50, field=None):
    if field is not None:
        if field == "timestamp":
            localts = value - offset*60
            localtime = datetime.datetime.fromtimestamp(localts)
            return localtime

    if isinstance(value, numeric):
        return value

    if isinstance(value, binary_types):
        if not isinstance(value, (bytes, bytearray)):
            value = bytes(value)  # Handle `buffer` type.
        value = value.decode('utf-8', decode_handler)
    if isinstance(value, unicode_type):
        value = escape(value)
        if len(value) > max_length:
            return ('<span class="truncated">%s</span> '
                    '<span class="full" style="display:none;">%s</span>'
                    '<a class="toggle-value" href="#">...</a>') % (
                        value[:max_length],
                        value)
    return value

@app.template_filter('column_filter_display')
def column_filter_display(column):
    nameDict = {"id":"ID", "timestamp":"Időbélyeg", "domain":"Domain", "client":"Kliens", "realIP":"Feloldott IP"}
    return nameDict[column]

@app.template_filter('column_filter')
def column_filter(columns):
    newColumns =  [column for column in columns if column in ["id", "domain", "timestamp", "client", "realIP"]]
    return newColumns

column_re = re.compile('(.+?)\((.+)\)', re.S)
column_split_re = re.compile(r'(?:[^,(]|\([^)]*\))+')

def _format_create_table(sql):
    create_table, column_list = column_re.search(sql).groups()
    columns = ['  %s' % column.strip()
               for column in column_split_re.findall(column_list)
               if column.strip()]
    return '%s (\n%s\n)' % (
        create_table,
        ',\n'.join(columns))

@app.template_filter()
def format_create_table(sql):
    try:
        return _format_create_table(sql)
    except:
        return sql

@app.template_filter('highlight')
def highlight_filter(data):
    return Markup(syntax_highlight(data))

def get_query_images():
    accum = []
    image_dir = os.path.join(app.static_folder, 'img')
    if not os.path.exists(image_dir):
        return accum
    for filename in sorted(os.listdir(image_dir)):
        basename = os.path.splitext(os.path.basename(filename))[0]
        parts = basename.split('-')
        accum.append((parts, 'img/' + filename))
    return accum

#
# Flask application helpers.
#

@app.context_processor
def _general():
    return {
        'dataset': dataset,
        'login_required': bool(app.config.get('PASSWORD')),
    }

@app.context_processor
def _now():
    return {'now': datetime.datetime.now()}

@app.before_request
def _connect_db():
    dataset.connect()

@app.teardown_request
def _close_db(exc):
    if not dataset._database.is_closed():
        dataset.close()
    if not live_dataset._database.is_closed():
        live_dataset.close()


class PrefixMiddleware(object):
    def __init__(self, app, prefix):
        self.app = app
        self.prefix = '/%s' % prefix.strip('/')
        self.prefix_len = len(self.prefix)

    def __call__(self, environ, start_response):
        if environ['PATH_INFO'].startswith(self.prefix):
            environ['PATH_INFO'] = environ['PATH_INFO'][self.prefix_len:]
            environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)
        else:
            start_response('404', [('Content-Type', 'text/plain')])
            return ['URL does not match application prefix.'.encode()]

#
# Script options.
#

def get_option_parser():
    parser = optparse.OptionParser()
    parser.add_option(
        '-p',
        '--port',
        default=8080,
        help='Port for web interface, default=8080',
        type='int')
    parser.add_option(
        '-H',
        '--host',
        default='127.0.0.1',
        help='Host for web interface, default=127.0.0.1')
    parser.add_option(
        '-d',
        '--debug',
        action='store_true',
        help='Run server in debug mode')
    parser.add_option(
        '-x',
        '--no-browser',
        action='store_false',
        default=True,
        dest='browser',
        help='Do not automatically open browser page.')
    parser.add_option(
        '-P',
        '--password',
        action='store_true',
        dest='prompt_password',
        help='Prompt for password to access database browser.')
    parser.add_option(
        '-r',
        '--read-only',
        action='store_true',
        dest='read_only',
        help='Open database in read-only mode.')
    parser.add_option(
        '-u',
        '--url-prefix',
        dest='url_prefix',
        help='URL prefix for application.')
    return parser

def die(msg, exit_code=1):
    sys.stderr.write('%s\n' % msg)
    sys.stderr.flush()
    sys.exit(exit_code)

def open_browser_tab(host, port):
    url = 'http://%s:%s/' % (host, port)

    def _open_tab(url):
        time.sleep(1.5)
        webbrowser.open_new_tab(url)

    thread = threading.Thread(target=_open_tab, args=(url,))
    thread.daemon = True
    thread.start()

def install_auth_handler(password):
    app.config['PASSWORD'] = password

    @app.before_request
    def check_password():
        if not session.get('authorized') and request.path != '/login/' and \
           not request.path.startswith(('/static/', '/favicon')):
            flash('Az adatbázis csak bejelentkezés után tekinthető meg.', 'danger')
            session['next_url'] = request.base_url
            return redirect(url_for('login'))

# TODO REMOVE - it is only test purpose, configure will set this
# Getting privadome.db location if it uses same interpreter as this script
PYTHON_DIR_PATH = os.path.dirname(sys.executable)
DATABASE_PATH = os.path.join(PYTHON_DIR_PATH, "Lib", "site-packages", "privadome", "database", "privadome.db")
print("PRIVADOME DB_PATH - : ", DATABASE_PATH)


def initialize_app(password=None, url_prefix=None):
    global dataset
    global live_dataset
    global migrator

    if password:
        install_auth_handler(password)
    print("OK2")
    try:
        print("Copydb: ", ADATGYUJTES_CONFIG["COPIED_DATABASE_PATH"])
        shutil.copy(ADATGYUJTES_CONFIG["DATABASE_PATH"], ADATGYUJTES_CONFIG["COPIED_DATABASE_PATH"])
        dataset = SqliteDataSet('sqlite:///{path}'.format(path=ADATGYUJTES_CONFIG["COPIED_DATABASE_PATH"]), bare_fields=True)
        live_dataset = SqliteDataSet('sqlite:///{path}'.format(path=ADATGYUJTES_CONFIG["DATABASE_PATH"]), bare_fields=True)
    except Exception as identifier:
        print(identifier)
    

    if url_prefix:
        app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix=url_prefix)

    migrator = dataset._migrator
    dataset.close()
    live_dataset.close()

def main():
    # This function exists to act as a console script entry-point.
    parser = get_option_parser()
    options, args = parser.parse_args()
    #if not args:
    #    die('Error: missing required path to database file.')

    password = None
    if options.prompt_password:
        password = ADATGYUJTES_CONFIG["PASSWORD"]
        print(password)
    # Initialize the dataset instance and (optionally) authentication handler.
    initialize_app(password, options.url_prefix)

    if options.browser:
        open_browser_tab(options.host, options.port)
    app.run(host=options.host, port=options.port, debug=options.debug)


if __name__ == '__main__':
    main()
