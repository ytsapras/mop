from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.exceptions import FieldError
from tom_targets.models import Target,TargetExtra
from astropy.time import Time
from mop.brokers import gaia as gaia_mop
import random
import datetime
from mop.management.commands.fit_need_events_PSPL import run_fit
import os

import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = 'Fit a specific selection of events with PSPL and parallax, then ingest fit parameters in the db'

    def add_arguments(self, parser):

        parser.add_argument('events_to_fit', help='all, alive, need or [years]')
        parser.add_argument('--cores', help='Number of workers to use', default=os.cpu_count(), type=int)


    def handle(self, *args, **options):

        logger.info('Running fit_all_events')

        # Avoid (unlikely but possible) clashing processes hitting the DB at the same time
        with transaction.atomic():

            # Create a QuerySet which allows us to lock DB rows to avoid clashes
            qs = Target.objects.select_for_update(skip_locked=True)

            # Apply the configured selection of events
            all_events = options['events_to_fit']

            # Fit all available events
            if all_events == 'all':
                list_of_targets = qs.filter()

            # Select all events close to their peaks
            if all_events == 'alive':
                qs = qs.filter()

                list_of_targets = []

                for t in qs:
                    if t.extra_fields['Alive']:
                        list_of_targets.append(t)

            # Select only those events with existing fits that are more than the
            # threshold time span old, but this TargetExtra entry may not exist for all events,
            # e.g. if they have not been fit recently
            if all_events == 'need':

                qs = qs.filter()
                four_hours_ago = Time(datetime.datetime.utcnow() - datetime.timedelta(hours=4)).jd
                list_of_targets = []

                for t in qs:
                    if t.extra_fields['Last_fit'] > four_hours_ago:
                        list_of_targets.append(t)

            if all_events[0] == '[':

                years = all_events[1:-1].split(',')
                events = qs.filter()
                list_of_targets = []
                for year in years:

                    list_of_targets =  [i for i in events if year in i.name]

                    list_of_targets = list(list_of_targets)
                    random.shuffle(list_of_targets)


            logger.info('Found '+str(len(list_of_targets))+' targets to fit')

            for target in list_of_targets:
                # if the previous job has not been started by another worker yet, claim it

                logger.info('Fitting data for '+target.name)
                try:
                    if 'Gaia' in target.name:
                        gaia_mop.update_gaia_errors(target)


                    if 'Microlensing' not in target.extra_fields['Classification']:
                        alive = False

                        extras = {'Alive':alive}
                        target.save(extras = extras)
                        logger.info(target.name+' not classified as microlensing')

                    else:
                        result = run_fit(target, cores=options['cores'])

                except:
                    logger.warning('Fitting event '+target.name+' hit an exception')
