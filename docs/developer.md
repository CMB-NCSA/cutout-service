# Developer documentation

## Requirements

- Docker with Compose plugin "docker compose"
- MinIO CLI client "mc"

## Launch local deployment

If you wish to override any of the environment variables, create a `.env` file in the `/docker` directory:

```bash
echo 'DEV_MODE = true' >> docker/.env
```

Launch the local deployment by navigating to the root directory of your repo clone and executing:

```bash
docker compose -f docker/docker-compose.yaml up -d --build
```


## Testing

## Unit tests

Run the unit tests using commands similar to the one below after launching the dev deployment.

```bash
docker compose -f docker/docker-compose.yaml up -d --build 
docker exec -it cutout-api-server-1 bash -c 'python manage.py test cutout.tests.cutout'
```

## Interact via HTTP API

Create a Python script `test.py` under `/scripts/`, using the `CutoutApi` class to launch a cutout job following the example below:

```python
from pathlib import Path
# Append the calculation_engine_api module to the Python path for import
sys.path.append(os.path.join(str(Path(__file__).resolve().parent.parent), 'app'))
from cutout.tests.api import CutoutApi  # pyright: ignore[reportMissingImports]

# Create an API object
api = CutoutApi()
# List all jobs
jobs = api.job_list()
print(yaml.dump(jobs))
# Delete all jobs
jobs = api.job_delete_all()
```

## Launch jobs using the job cannon

Use the `/scripts/job_cannon.py` script to stress test concurrent job processing.

```bash
python scripts/job_cannon.py 10
```
