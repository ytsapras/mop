from django.core.management.base import BaseCommand
from tom_alerts.brokers import gaia
from astropy.coordinates import SkyCoord
import astropy.units as unit
from tom_targets.models import Target
from mop.brokers import gaia as gaia_mop
from astropy.time import Time
import requests
from requests.exceptions import HTTPError

from tom_alerts.alerts import GenericAlert, GenericBroker, GenericQueryForm
from tom_dataproducts.models import ReducedDatum

from astropy.time import Time, TimezoneInfo
from mop.toolbox import TAP, utilities


BASE_BROKER_URL = gaia.BASE_BROKER_URL


class MOPGaia(gaia.GaiaBroker):

    def process_reduced_data(self, target, alert=None):
        if not alert:
            try:
                alert = self.fetch_alert(target.name)

            except HTTPError:
                raise Exception('Unable to retrieve alert information from broker')

        if alert:
            alert_name = alert['name']
            alert_link = alert.get('per_alert', {})['link']
            lc_url = f'{BASE_BROKER_URL}/alerts/alert/{alert_name}/lightcurve.csv'
            alert_url = f'{BASE_BROKER_URL}/{alert_link}'
        elif target:
            lc_url = f'{BASE_BROKER_URL}/{target.name}/lightcurve.csv'
            alert_url = f'{BASE_BROKER_URL}/alerts/alert/{target.name}/'
        else:
            return

        try:
            response = requests.get(lc_url)
            response.raise_for_status()
            html_data = response.text.split('\n')

            try:
                times = [Time(i.timestamp).jd for i in ReducedDatum.objects.filter(target=target) if i.data_type == 'photometry']
            except:
                times = []

            for entry in html_data[2:]:
                phot_data = entry.split(',')

                if len(phot_data) == 3:

                    jd = Time(float(phot_data[1]), format='jd', scale='utc')
                    jd.to_datetime(timezone=TimezoneInfo())

                    if ('untrusted' not in phot_data[2]) and ('null' not in phot_data[2]) and (jd.value not in times):

                        value = {
                        'magnitude': float(phot_data[2]),
                        'filter': 'G'
                        }

                        rd, _ = ReducedDatum.objects.get_or_create(
                                timestamp=jd.to_datetime(timezone=TimezoneInfo()),
                                value=value,
                                source_name=self.name,
                                source_location=alert_url,
                                data_type='photometry',
                                target=target)

                        rd.save()

            (t_last_jd, t_last_date) = TAP.TAP_time_last_datapoint(target)
            extras = {'Latest_data_HJD': t_last_jd, 'Latest_data_UTC': t_last_date}
            target.save(extras=extras)
        except requests.exceptions.HTTPError:
            pass

        return



class Command(BaseCommand):

    help = 'Downloads Gaia data for all events marked as microlensing candidate'
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):

        Gaia = MOPGaia()

        (list_of_alerts, broker_feedback) = Gaia.fetch_alerts({'target_name':None,'cone':None})

        new_alerts = []
        for alert in list_of_alerts:

            # As of Oct 2022, Gaia alerts will no longer be providing the
            # microlensing class as a comment in the alert.  We therefore
            # switched to downloading all Gaia alerts
            # if 'microlensing' in alert['comment']:

            #Create or load
            clean_alert = Gaia.to_generic_alert(alert)
            try:
               target, created = Target.objects.get_or_create(name=clean_alert.name,ra=clean_alert.ra,dec=clean_alert.dec,type='SIDEREAL',epoch=2000)
            #seems to bug with the ra,dec if exists
            except:
                  target, created = Target.objects.get_or_create(name=clean_alert.name)

            if created:
                new_alerts.append(target)

            utilities.add_gal_coords(target)
            TAP.set_target_sky_location(target)
            Gaia.process_reduced_data(target, alert=alert)
            gaia_mop.update_gaia_errors(target)
            gaia_mop.fetch_gaia_dr3_entry(target)

        # For all new alerts, set the permissions on the targets so all OMEGA users can see them
        utilities.open_targets_to_OMEGA_team(new_alerts)