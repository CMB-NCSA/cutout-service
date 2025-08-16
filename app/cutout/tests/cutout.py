from django.test import TestCase
from ..tasks import generate_cutouts
from uuid import uuid4


class GenerateCutout(TestCase):
    def test_generate_cutouts(self):
        import logging
        logging.basicConfig(level=logging.DEBUG)
        job_id = str(uuid4())
        generate_cutouts(job_id=job_id, config={
            'input_coords': '''
                RA,DEC,XSIZE,YSIZE
                49.9208333333, -19.4166666667, 6.6, 6.6
            ''',
            'verbose': True,
            'outdir': f'/tmp/{job_id}',
            'logfile': f'/tmp/{job_id}/cutout.log',
        })
