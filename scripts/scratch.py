import yaml
import sys
import os
from pathlib import Path
# Append the calculation_engine_api module to the Python path for import
sys.path.append(os.path.join(str(Path(__file__).resolve().parent.parent), 'app'))
from cutout.tests.api import CutoutApi  # pyright: ignore[reportMissingImports]

api = CutoutApi()


def delete_all():
    jobs = api.job_delete_all()
    jobs = api.job_list()
    print(yaml.dump(jobs))


def job_list():
    jobs = api.job_list()
    print(yaml.dump(jobs))


if __name__ == "__main__":
    job_list()
    # delete_all()
