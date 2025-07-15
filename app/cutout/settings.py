from pathlib import Path
import logging.config
import os
from corsheaders.defaults import default_headers

django_base_dir = Path(__file__).resolve().parent.parent

APP_VERSION = '0.0.1'
APP_ROOT_DIR = os.environ.get('APP_ROOT_DIR', '/opt')
assert os.path.isabs(APP_ROOT_DIR)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-dummy-secret')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

# API_SERVER_HOST is the internal service name
API_SERVER_HOST = os.environ.get("API_SERVER_HOST", "api-server")
# API_SERVER_PORT is the port associated with the Django webserver itself
API_SERVER_PORT = os.environ.get("API_SERVER_PORT", "8000")
# API_PROXY_PORT is the port associated with the proxy webserver
API_PROXY_PORT = os.environ.get("API_PROXY_PORT", "4000")
# HOSTNAMES is the list of domains associated with the ingress
HOSTNAMES = os.environ.get("DJANGO_HOSTNAMES", "localhost").split(",")
for hostname in ['localhost', '127.0.0.1', 'api-proxy']:
    if hostname not in HOSTNAMES:
        HOSTNAMES.append(hostname)
ALLOWED_HOSTS = HOSTNAMES
if API_SERVER_HOST:
    ALLOWED_HOSTS.append(API_SERVER_HOST)

# Cross Site Request Forgery protection (https://docs.djangoproject.com/en/4.2/ref/csrf/)
CSRF_TRUSTED_ORIGINS = [f"http://localhost:{API_PROXY_PORT}", f"http://localhost:{API_SERVER_PORT}"]
for hostname in ALLOWED_HOSTS:
    CSRF_TRUSTED_ORIGINS.append(f'''http://{hostname}''')
    CSRF_TRUSTED_ORIGINS.append(f'''https://{hostname}''')
CSRF_COOKIE_SECURE = True

# CORS configuration (https://pypi.org/project/django-cors-headers/)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
# CORS_ALLOWED_ORIGINS = ["*"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + [
    # add custom headers here
]

# Application definition

SITE_ID = 1

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_filters',
    'django_bootstrap5',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'django_celery_results',
    'django_celery_beat',
    'storages',
    'cutout',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'cutout.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(django_base_dir, 'cutout/templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ASGI_APPLICATION = 'cutout.asgi.application'

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DATABASE_DB', 'postgres'),
        'USER': os.getenv('DATABASE_USER', 'postgres'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD', 'postgres'),
        'HOST': os.getenv('DATABASE_HOST', '127.0.0.1'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    },
    'sqlite': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(APP_ROOT_DIR, 'db.sqlite3'),
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)


# SESSION_ENGINE
# ref: https://github.com/mozilla/mozilla-django-oidc/issues/435#issuecomment-1036372844
# ref: https://docs.djangoproject.com/en/4.0/topics/http/sessions/
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = False

USE_TZ = True

DATETIME_FORMAT = 'Y-m-d H:m:s'
DATE_FORMAT = 'Y-m-d'


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

STATIC_URL = '/static/'
# STATIC_ROOT tells collectstatic where to copy all the static files that it collects.
STATIC_ROOT = os.path.join(APP_ROOT_DIR, 'static')

MEDIA_URL = '/uploads/'
MEDIA_ROOT = os.path.join(APP_ROOT_DIR, 'uploads')

# Caching
# https://docs.djangoproject.com/en/dev/topics/cache/#filesystem-caching

REDIS_SERVICE = os.environ.get('REDIS_SERVICE', 'redis')
CACHES = {
    'default': {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{REDIS_SERVICE}:6379",
    }
}

API_RATE_LIMIT_ANON = int(os.getenv('API_RATE_LIMIT_ANON', '30'))
API_RATE_LIMIT_USER = int(os.getenv('API_RATE_LIMIT_USER', '2'))
API_RATE_LIMIT_DOWNLOAD = int(os.getenv('API_RATE_LIMIT_DOWNLOAD', '10'))

REST_FRAMEWORK = {
    'DEFAULT_METADATA_CLASS': 'rest_framework.metadata.SimpleMetadata',
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': f'''{API_RATE_LIMIT_ANON}/minute''',
        'user': f'''{API_RATE_LIMIT_USER}/second''',
        'download': f'''{API_RATE_LIMIT_DOWNLOAD}/second''',
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'INFO'
        }
    }
}
logging.config.dictConfig(LOGGING)
