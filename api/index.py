import os
import sys
import base64
from io import BytesIO
from urllib.parse import urlencode

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

def _bootstrap_site_packages():
    """Try hard to find where Vercel pip-installed Django & friends live."""
    py_ver = f'{sys.version_info.major}.{sys.version_info.minor}'
    candidates = [
        os.path.join(os.environ.get('PYTHONUSERBASE', '/vercel/.local'),
                     'lib', f'python{py_ver}', 'site-packages'),
        '/var/task/python_modules',
        f'/vercel/path0/venv/lib/python{py_ver}/site-packages',
        f'/vercel/path0/.venv/lib/python{py_ver}/site-packages',
        '/vercel/path1/python_modules',
        '/vercel/output/python_modules',
        f'/vercel/cache/.venv/lib/python{py_ver}/site-packages',
        f'/tmp/.venv/lib/python{py_ver}/site-packages',
        os.path.join(os.environ.get('VIRTUAL_ENV', ''), 'lib',
                     f'python{py_ver}', 'site-packages'),
    ]
    for p in candidates:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
_bootstrap_site_packages()

try:
    from django.core.wsgi import get_wsgi_application
except ImportError:
    sys.stderr.write('ERROR: Django could not be imported. sys.path=' + repr(sys.path) + '\n')
    raise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'documate.settings')
os.environ.setdefault('RUNNING_ON_VERCEL', 'True')

application = get_wsgi_application()
app = application

# Ensure database tables exist if running on Vercel with fresh SQLite in /tmp
if not os.getenv('DATABASE_URL') and not os.getenv('POSTGRES_URL'):
    try:
        from django.core.management import call_command
        from pathlib import Path
        tmp_db = Path('/tmp/db.sqlite3')
        if not tmp_db.exists() or tmp_db.stat().st_size < 10000:
            call_command('migrate', interactive=False)
            call_command('create_superuser', interactive=False)
    except Exception as e:
        sys.stderr.write(f'Auto-migration note: {e}\n')


def handler(event, context):
    headers = event.get('headers', {}) or {}
    method = event.get('method') or event.get('httpMethod') or 'GET'
    path = event.get('path', '/')

    query = event.get('query') or event.get('queryStringParameters') or {}
    if isinstance(query, dict):
        query_string = urlencode(query, doseq=True)
    else:
        query_string = ''

    raw_body = event.get('body', '') or b''
    if event.get('encoding') == 'base64' and isinstance(raw_body, str):
        try:
            raw_body = base64.b64decode(raw_body)
        except Exception:
            raw_body = raw_body.encode('utf-8')
    elif isinstance(raw_body, str):
        raw_body = raw_body.encode('utf-8')

    content_length = str(len(raw_body)) if raw_body else '0'

    def _h(name):
        return headers.get(name) or headers.get(name.lower()) or headers.get(name.title()) or ''

    host = _h('host') or _h('Host')
    xff = _h('x-forwarded-for')
    proto = (_h('x-forwarded-proto') or 'https').split(',')[0].strip()

    environ = {
        'REQUEST_METHOD': method.upper(),
        'SCRIPT_NAME': '',
        'PATH_INFO': path,
        'QUERY_STRING': query_string,
        'CONTENT_TYPE': _h('content-type') or '',
        'CONTENT_LENGTH': content_length,
        'SERVER_NAME': host or 'vercel.app',
        'SERVER_PORT': _h('x-forwarded-port') or ('443' if proto == 'https' else '80'),
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'REMOTE_ADDR': (xff.split(',')[0].strip() if xff else '127.0.0.1'),
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': proto,
        'wsgi.input': BytesIO(raw_body),
        'wsgi.errors': sys.stderr,
        'wsgi.multiprocess': False,
        'wsgi.multithread': False,
        'wsgi.run_once': False,
    }

    for key, value in headers.items():
        key_upper = key.upper().replace('-', '_')
        if key_upper in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            continue
        env_key = 'HTTP_' + key_upper
        if env_key not in environ:
            environ[env_key] = str(value) if value else ''

    response_status = []
    response_headers = []

    def start_response(status, headers, exc_info=None):
        response_status.clear()
        response_headers.clear()
        response_status.append(status)
        for h in headers:
            response_headers.append(h)

    try:
        result = application(environ, start_response)
        try:
            body_parts = []
            for data in result:
                if data:
                    if isinstance(data, str):
                        data = data.encode('utf-8')
                    body_parts.append(data)
            body = b''.join(body_parts)
        finally:
            if hasattr(result, 'close'):
                try:
                    result.close()
                except Exception:
                    pass
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/plain; charset=utf-8'},
            'body': '500 Internal Server Error\n\n' + str(exc),
        }

    status_code = 200
    if response_status:
        try:
            status_code = int(response_status[0].split(' ', 1)[0])
        except (ValueError, IndexError):
            pass

    out_headers = {}
    content_type = None
    cookies = []
    for k, v in response_headers:
        kl = k.lower()
        if kl == 'content-type':
            content_type = v
        if kl == 'set-cookie':
            cookies.append(v)
        else:
            out_headers[k] = v

    if 'Content-Type' not in out_headers and content_type:
        out_headers['Content-Type'] = content_type
    if 'Content-Type' not in out_headers:
        out_headers['Content-Type'] = 'text/html; charset=utf-8'

    ct = out_headers.get('Content-Type', '').lower()
    is_binary = not (
        ct.startswith(('text/', 'application/json', 'application/javascript',
                       'application/xml', 'application/xhtml', 'image/svg'))
    )

    payload = {
        'statusCode': status_code,
        'headers': out_headers,
    }
    if cookies:
        payload['cookies'] = cookies
        payload['multiValueHeaders'] = {'Set-Cookie': cookies}

    if is_binary:
        payload['body'] = base64.b64encode(body).decode('ascii')
        payload['encoding'] = 'base64'
    else:
        payload['body'] = body.decode('utf-8', errors='replace')

    return payload
