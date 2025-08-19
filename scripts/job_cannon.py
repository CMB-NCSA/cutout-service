import yaml
import sys
import os
from pathlib import Path
from multiprocessing import Process
import time
from datetime import datetime
import random
# Append the Cutout API module to the Python path for import
sys.path.append(os.path.join(str(Path(__file__).resolve().parent.parent), 'app'))
from cutout.tests.api import CutoutApi  # pyright: ignore[reportMissingImports]

api = CutoutApi()


def delete_all():
    jobs = api.job_delete_all()
    jobs = api.job_list()
    print(yaml.dump(jobs))


def run_workflow():
    response = api.job_create(name=f'''cutout-{random.randrange(10000, 99999)}''', config={
        'input_csv': '''RA,DEC,XSIZE,YSIZE\n#0.29782658,0.029086056,3,3\n49.9208333333,-19.4166666667,6.6,6.6\n'''
    })
    job_id = response['uuid']
    time_sleep = 5  # seconds
    time_start = time.time()
    response = api.job_list(uuid=job_id)
    while 60 > time.time() - time_start and response['status'] not in ['SUCCESS', 'FAILURE']:
        time.sleep(time_sleep)
        response = api.job_list(uuid=job_id)
    print(response['status'])
    assert response['status'] == 'SUCCESS'


def launch_jobs(num_cycles=1):
    procs = []
    for cycle in range(1, num_cycles + 1):
        proc = Process(target=run_workflow, name=f'''{run_workflow.__name__}-{cycle}''')
        proc.start()
        # proc.join()
        procs.append(proc)
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Process started: {proc.name}''')
    running_procs = ['init']
    finished_procs = []
    while procs:
        time.sleep(5)
        running_procs = []
        for proc in procs:
            if proc.is_alive():
                running_procs.append(proc)
            else:
                finished_procs.append(proc)
                print(f'[{datetime.now().strftime("%H:%M:%S")}] Process finished: {proc.name}''')
                if proc.exitcode:
                    print(f'[{datetime.now().strftime("%H:%M:%S")}] PROCESS ERROR: {proc}''')
                # print(f'[{datetime.now().strftime("%H:%M:%S")}] Process running: {proc.name}''')
        procs = running_procs
    for proc in finished_procs:
        if proc.exitcode:
            print(f'[{datetime.now().strftime("%H:%M:%S")}] PROCESS ERROR: {proc}''')


if __name__ == "__main__":
    num_cycles = 1
    if len(sys.argv) > 1:
        num_cycles = int(sys.argv[1])
    launch_jobs(num_cycles=num_cycles)
