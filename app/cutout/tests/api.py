import requests
import random
import os
import sys
import json
import logging
from time import sleep

logging.basicConfig(stream=sys.stdout)
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', logging.WARNING))


class CutoutApi():
    def __init__(self, conf={}):
        # Import credentials and config from environment variables
        self.conf = {
            'api_url_protocol': os.environ.get('CE_API_URL_PROTOCOL', 'http'),
            'api_url_authority': os.environ.get('CE_API_URL_AUTHORITY', 'localhost:8000'),
            'api_url_basepath': os.environ.get('CE_API_URL_BASEPATH', 'api'),
            # Max number of requests per second
            'api_rate_limit': int(os.environ.get('API_RATE_LIMIT_USER', '5')),
        }
        for param in self.conf:
            if param in conf:
                self.conf[param] = conf[param]
        self.conf['url_base'] = f'''{self.conf['api_url_protocol']}://{self.conf['api_url_authority']}'''
        self.conf['api_url_base'] = f'''{self.conf['url_base']}/{self.conf['api_url_basepath']}'''
        self.json_headers = {}
        self.json_headers['Content-Type'] = 'application/json'

    def rate_limiter(self, response):
        rate_limit_status_code = 429
        if response.status_code == rate_limit_status_code:
            logger.debug(f'Response code {rate_limit_status_code} received. Rate limiter engaged.')
            sleep(1.0 / self.conf['api_rate_limit'])
        return response.status_code == rate_limit_status_code

    def display_response(self, response, parse_json=True):
        try:
            assert isinstance(response, requests.Response)
        except Exception as err:
            logger.error(f'''Invalid response object: {err}''')
            return response
        logger.debug(f'''Response code: {response.status_code}''')
        try:
            assert response.status_code in range(200, 300)
            if parse_json:
                data = response.json()
                logger.debug(json.dumps(data, indent=2))
                return data
            else:
                return response
        except Exception:
            try:
                logger.debug(f'''ERROR: {json.dumps(response.text, indent=2)}''')
            except Exception:
                logger.debug(f'''ERROR: {response.text}''')
            return response

    def job_list(self, uuid=''):
        jobs = []
        url = f'''{self.conf['api_url_base']}/job/'''
        if uuid:
            url = f'''{url}{uuid}/'''
        while True:
            response = requests.get(
                url,
                headers=self.json_headers,
            )
            if not self.rate_limiter(response):
                break
        if response.status_code not in range(200, 300):
            return response
        response_data = response.json()
        # If a single job is being requested, return the data
        if uuid:
            return response_data
        # If all job info is being requested, append the result list and then fetch the next page of results
        jobs = response_data['results']
        url = response_data['next']
        # If the URL to the next page of results was included in the response, fetch it
        logger.debug(f'''Next page of results: "{url}"''')
        while url:
            while True:
                response = requests.get(
                    url,
                    headers=self.json_headers,
                )
                if not self.rate_limiter(response):
                    break
            response_data = response.json()
            jobs += response_data['results']
            url = response_data['next']
        return jobs

    def job_create(self, name='', description="", config={}):
        if not name:
            name = f'''test-{random.randrange(10000, 99999)}'''
        while True:
            response = requests.post(
                f'''{self.conf['api_url_base']}/job/''',
                json={
                    'name': name,
                    'config': config,
                    'description': description,
                },
                headers=self.json_headers,
            )
            if not self.rate_limiter(response):
                break
        return self.display_response(response)

    def job_delete(self, uuid=None):
        while True:
            response = requests.delete(
                f'''{self.conf['api_url_base']}/job/{uuid}/''',
                headers=self.json_headers,
            )
            if not self.rate_limiter(response):
                break
        return self.display_response(response, parse_json=False)

    def job_delete_all(self):
        all_jobs = self.job_list()
        for job in all_jobs:
            logger.debug(job)
            while True:
                response = requests.delete(
                    f'''{self.conf['api_url_base']}/job/{job['uuid']}/''',
                    headers=self.json_headers,
                )
                if not self.rate_limiter(response):
                    break
            self.display_response(response, parse_json=False)
