from tom_alerts.brokers.tns import TNSBroker
from django.conf import settings
import json
import requests

import logging

logger = logging.getLogger(__name__)

TNS_BASE_URL = 'https://www.wis-tns.org/'
TNS_OBJECT_URL = f'{TNS_BASE_URL}api/get/object'
TNS_SEARCH_URL = f'{TNS_BASE_URL}api/get/search'

class Custom_TNS(TNSBroker):
    def fetch_tns_name(self, parameters):
        '''
                Modified version of fetch_alert from original TOM Toolkit.
                '''
        broker_feedback = ''

        data = {
            'api_key': settings.BROKERS['TNS']['api_key'],
            'data': json.dumps({
                'ra': parameters['ra'],
                'dec': parameters['dec'],
                'radius': parameters['radius'],
                'units': parameters['units'],
            }
            )
        }
        response = requests.post(TNS_SEARCH_URL, data, headers=self.tns_headers())
        response.raise_for_status()
        transients = response.json()
        names = []
        for transient in transients['data']['reply']:
            tns_name = transient['objname']
            names.append(tns_name)

        return names

    def fetch_tns_class(self, parameters):
        '''
        Modified version of fetch_alert from original TOM Toolkit.
        '''
        broker_feedback = ''

        data = {
            'api_key': settings.BROKERS['TNS']['api_key'],
            'data': json.dumps({
                'objname': parameters['objname'],
                'photometry': 1,
                'spectroscopy': 0,
            }
            )
        }
        response = requests.post(TNS_OBJECT_URL, data, headers=self.tns_headers())
        response.raise_for_status()
        alert = response.json()['data']['reply']
        tns_class = alert['object_type']['name']

        return tns_class
