from celery import shared_task
from dotmap import DotMap
import numpy as np
import pandas
import duckdb
import os
import math
import time
import multiprocessing as mp
from des_cutter import fitsfinder
from des_cutter import thumbslib
from des_cutter import color_radec
import logging
import json
import io
from .object_store import ObjectStore
from .models import Job, JobFile, JobMetric, FileMetric
from .models import update_job_state
from django.conf import settings
from celery.signals import task_failure
# from celery.signals import task_postrun
# from celery.signals import task_revoked
from .log import get_logger
logger = get_logger(__name__)

s3 = ObjectStore()


def create_job_file_objects(job_id):
    # logger.debug('Creating JobFile database records...')
    s3_basepath = os.path.join(settings.S3_BASE_DIR, f'''jobs/{job_id}''')
    paths = s3.list_directory(s3_basepath)
    for path in paths:
        file_size = s3.object_info(path).size
        if not JobFile.objects.filter(
            job=Job.objects.get(uuid__exact=job_id),
            path=path.replace(s3_basepath, '', 1),
        ):
            job = Job.objects.get(uuid__exact=job_id)
            JobFile.objects.create(
                job=job,
                path=path.replace(s3_basepath, '', 1),
                size=file_size,
            )
            # Record the job file metadata for metrics collection
            FileMetric.objects.create(
                size=file_size,
                owner=job.owner,
                file_type=FileMetric.FileType.JOB,
            )


def upload_job_files(job_id):
    # Upload all job output files
    s3_basepath = os.path.join(settings.S3_BASE_DIR, f'''jobs/{job_id}''')
    src_dir = os.path.join('/scratch', job_id)
    s3.store_folder(
        src_dir=src_dir,
        bucket_root_path=s3_basepath,
    )


def validate_cutout_size_from_table(df):
    '''Determine if the cutout size spec, if present, in the input DataFrame is valid.'''
    err_msg = ''
    try:
        # If cutout size is not specified in table, it is valid
        if 'XSIZE' not in df or 'YSIZE' not in df:
            return 'no size spec'
        if ('XSIZE' in df and 'YSIZE' not in df) or ('YSIZE' in df and 'XSIZE' not in df):
            return 'only one size spec'
        xsizes = df.XSIZE.values
        ysizes = df.YSIZE.values
        err_msg = 'Unequal number of cutout size values'
        assert len(xsizes) == len(ysizes)
        err_msg = 'Non-numeric value'
        assert np.issubdtype(xsizes.dtype, np.number)
        assert np.issubdtype(ysizes.dtype, np.number)
        for val in np.concatenate((xsizes, ysizes)):
            err_msg = 'NaN detected'
            assert not math.isnan(val)
            err_msg = 'Value must be greater than zero'
            assert val > 0
        err_msg = ''
    except Exception as err:
        logger.warning(f'Invalid cutout size specification: {err}, {err_msg}')
    return err_msg


def validate_config(config):
    '''Validate configuration. Return empty string if valid; return error message if not.'''
    try:
        assert config['input_csv']
    except Exception:
        return 'Coordinate table cannot be empty'
    try:
        df = pandas.read_csv(io.StringIO(config['input_csv']), comment='#', skipinitialspace=True)
        df.to_csv(index=False)
        logger.debug(df)
    except Exception as err:
        return f'Coordinate table parsing error: {err}'
    try:
        logger.debug(df.RA)
        logger.debug(df.DEC)
        assert len(df.RA.values)
        assert len(df.DEC.values)
    except Exception as err:
        return f'Coordinate table must have one or more RA and DEC values: {err}'
    try:
        assert len(df.RA.values) == len(df.DEC.values)
    except Exception as err:
        return f'Coordinate table must have the same number of RA and DEC values: {err}'
    try:
        for val in df.RA.values + df.DEC.values:
            assert isinstance(val, float)
            assert not math.isnan(val)
    except Exception as err:
        return f'Coordinate table RA and DEC values must be numeric values: {err}'
    for param in ['xsize', 'ysize']:
        if param in config:
            try:
                assert isinstance(config[param], int)
            except Exception:
                return f'{param} must be an integer'
            try:
                assert config[param] > 0
            except Exception:
                return f'{param} must be greater than zero'
    err_msg = validate_cutout_size_from_table(df)
    if err_msg and err_msg != 'no size spec':
        return f'Invalid cutout size specification in coordinate table: {err_msg}'
    # TODO: Complete the validation logic for other config parameters.
    return ''


def process_config(config):
    default_config = settings.DEFAULT_CONFIG
    processed_config = {}
    for key, value in default_config.items():
        if key in config:
            processed_config[key] = config[key]
        else:
            processed_config[key] = value
    if processed_config['input_csv']:
        df = pandas.read_csv(io.StringIO(processed_config['input_csv']), comment='#', skipinitialspace=True)
        processed_config['coords'] = df.to_csv(index=False)
    else:
        logger.warning('No input coordinates provided.')
        return processed_config

    # If the cutout size parameters are provided per-coordinate in the CSV text,
    # validate the values and ignore the global values.
    err_msg = validate_cutout_size_from_table(df)
    if not err_msg or err_msg == 'no size spec':
        # Remove the size overrides
        processed_config.pop('xsize')
        processed_config.pop('ysize')
        # If the user also specified global values, ignore them.
        if 'xsize' in config or 'ysize' in config:
            logger.info('Ignoring global cutout size parameters because per-coordinate sizes are specified.')
    else:
        logger.info('Using global cutout size parameters.')
    err_msg = validate_config(processed_config)
    if err_msg:
        logger.error(f'Invalid config: {err_msg}')
    return processed_config, err_msg


@shared_task(name="Generate cutouts")
def generate_cutouts(job_id, config={}):
    config = DotMap(config)

    # Make sure that outdir exists
    config.outdir = f'/scratch/{job_id}'
    config.logfile = os.path.join(config.outdir, 'cutout.log')
    os.makedirs(config.outdir, exist_ok=True)

    # Configure logging
    cutter_log = logging.getLogger('cutter')
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(fmt='%(asctime)s [%(name)s] %(levelname)-8s %(message)s'))
    stream_handler.setLevel(os.getenv('LOG_LEVEL', logging.INFO))
    file_handler = logging.FileHandler(config.logfile)
    file_handler.setFormatter(logging.Formatter(fmt='%(asctime)s [%(name)-s] %(levelname)-8s %(message)s'))
    if config.verbose:
        file_handler.setLevel(logging.DEBUG)
        sout = open(config.logfile, 'a', encoding="utf-8")
        fitsfinder.SOUT = sout
        thumbslib.SOUT = sout
    else:
        file_handler.setLevel(os.getenv('LOG_LEVEL', logging.INFO))
    cutter_log.handlers.clear()
    cutter_log.addHandler(stream_handler)
    cutter_log.addHandler(file_handler)
    cutter_log.propagate = False

    # Print processed config
    cutter_log.debug(json.dumps(config.toDict(), indent=2))

    # Read in CSV file with pandas
    df = pandas.read_csv(io.StringIO(config.input_csv), comment='#', skipinitialspace=True)
    cutter_log.debug(f'''Input table DataFrame:\n{df}''')
    ra = df.RA.values  # if you only want the values otherwise use df.RA
    dec = df.DEC.values
    assert len(ra) == len(dec)
    nobj = len(ra)
    req_cols = ['RA', 'DEC']

    # Check columns for consistency
    fitsfinder.check_columns(df.columns, req_cols)

    # Check the xsize and ysizes
    xsize, ysize = fitsfinder.check_xysize(df, config, nobj)
    # connect to the DuckDB database -- via filename
    dbh = duckdb.connect(settings.CUTOUT_DATA_DB_PATH, read_only=True)

    # Get archive_root
    archive_root = fitsfinder.get_archive_root(verb=False)

    cutter_log.debug('Finding tilename for each input position...')
    tilenames, indices, tilenames_matched = fitsfinder.find_tilenames_radec(ra, dec, dbh)

    # Add them back to pandas dataframe and write a file
    df['TILENAME'] = tilenames_matched
    # Get the thumbname base names and the them the pandas dataframe too
    df['THUMBNAME'] = thumbslib.get_base_names(tilenames_matched, ra, dec, prefix=config.prefix)
    matched_list = os.path.join(config.outdir, 'matched.csv')
    cutter_log.debug(f'''Matched tilenames DataFrame:\n{df}''')
    df.to_csv(matched_list, index=False)
    cutter_log.info(f"Wrote matched tilenames list to: {matched_list}")

    # Store the files used
    files_used = []

    # Loop over all of the tilenames
    t0 = time.time()
    Ntile = 0
    for tilename in tilenames:
        t1 = time.time()
        Ntile = Ntile + 1
        cutter_log.info("# ----------------------------------------------------")
        cutter_log.info(f"# Processing: {tilename} [{Ntile}/{len(tilenames)}]")
        cutter_log.info("# ----------------------------------------------------")

        # 1. Get all of the filenames for a given tilename
        filenames = fitsfinder.get_coaddfiles_tilename(tilename, dbh, bands=config.bands)

        if filenames is False:
            cutter_log.info(f"# Skipping: {tilename} -- not in TABLE ")
            continue
        # Fix compression for SV1/Y2A1/Y3A1 releases
        else:
            filenames = fitsfinder.fix_compression(filenames)

        indx = indices[tilename]

        avail_bands = filenames.BAND

        # 2. Loop over all of the filename -- We could use multi-processing
        p = {}
        n_filenames = len(avail_bands)
        for k in range(n_filenames):

            # Rebuild the full filename with COMPRESSION if present
            filename = os.path.join(archive_root, filenames.PATH[k])
            cutter_log.debug(f''' full filename before COMPRESSION check: "{filename}"''')
            if 'COMPRESSION' in filenames.dtype.names:
                filename = os.path.join(filename, f'{filenames.FILENAME[k]}{filenames.COMPRESSION[k]}')
            cutter_log.debug(f''' full filename: "{filename}"''')
            # Write them to a file
            files_used.append(filename)

            ar = (filename, ra[indx], dec[indx])
            kw = {'xsize': xsize[indx], 'ysize': ysize[indx],
                  'units': 'arcmin', 'prefix': config.prefix, 'outdir': config.outdir,
                  'tilename': tilename, 'verb': config.verb}
            if config.verb:
                sout.write(f"# Cutting: {filename}")
            if config.MP:
                NP = len(avail_bands)
                p[filename] = mp.Process(target=thumbslib.fitscutter, args=ar, kwargs=kw)
                p[filename].start()
            else:
                NP = 1
                thumbslib.fitscutter(*ar, **kw)

        # Make sure all process are closed before proceeding
        if config.MP:
            for filename, value in p.items():
                value.join()

        # 3. Create color images using stiff for each ra,dec and loop over (ra,dec)
        for k in range(len(ra[indx])):
            color_radec(ra[indx][k], dec[indx][k], avail_bands,
                        prefix=config.prefix,
                        colorset=config.colorset,
                        outdir=config.outdir,
                        verb=config.verb,
                        stiff_parameters={'NTHREADS': NP})

        cutter_log.debug(f"# Time {tilename}: {thumbslib.elapsed_time(t1)}")
    cutter_log.debug(f"\n*** Grand Total time:{thumbslib.elapsed_time(t0)} ***")

    with open(os.path.join(config.outdir, 'files_used.csv'), 'w') as used_files:
        used_files.write('\n'.join(files_used))

    # Upload all job files to the object store
    upload_job_files(job_id)
    # Update the known job files in the database
    create_job_file_objects(job_id)


@task_failure.connect()
def task_failed(task_id=None, exception=None, args=None, traceback=None, einfo=None, **kwargs):
    logger.error("from task_failed ==> task_id: " + str(task_id))
    logger.error("from task_failed ==> args: " + str(args))
    logger.error("from task_failed ==> exception: " + str(exception))
    logger.error("from task_failed ==> einfo: " + str(einfo))
    try:
        job_id = kwargs['kwargs']['job_id']
        job = Job.objects.get(uuid__exact=job_id)
        # Record the job metadata for metrics collection
        JobMetric.objects.create(
            status=Job.JobStatus.FAILURE,
            owner=job.owner,
            config=job.config,
        )
        if not job.error_info:
            err_msg = f"System Error: {str(einfo)}"
            update_job_state(job_id, Job.JobStatus.FAILURE, error_info=err_msg)
        else:
            logger.error("from task_failed ==> job.error_info: " + str(job.error_info))
    except KeyError:
        logger.info(f"From task_failed ==> KeyError: {kwargs['kwargs']}")
        pass
