# User documentation

## Batch job file download

You can download all job files using the shell script shown below. First, set the API token environment variable with the value you obtain from the web interface:

```bash
export API_TOKEN=example_ab47c92f509a2da6e3fb1080a2004115

# If you are running in the local development environment,
# you should also set
# CUTOUT_BASE_URL="http://localhost:4000"
```

Then run the script with the job ID to download the job files. A new folder named with the job ID will be created in your working directory.

```bash
bash download_job_files.sh example-20df-458c-9438-f590acb95ec8

$ ls ./example-20df-458c-9438-f590acb95ec8/
config.yaml  DESJ031941.0-192500.0_g.fits ...
```


Source code of `download_job_files.sh`:

```bash
#!/bin/bash

set -euo pipefail

JOB_ID=$1

set +u
# If the "CUTOUT_BASE_URL" environment variable is not set, use
# the default public server.
if [ -z $CUTOUT_BASE_URL ]; then
    CUTOUT_BASE_URL="https://stamps.scimma.org"
fi
set -u

# Use "curl" to query the API to obtain the list of file paths
# by piping the returned job information data object to "jq".
files=($(curl --no-progress-meter --fail \
    -H "Content-Type: application/json" \
    -H "Authorization: Token ${API_TOKEN}" \
    -X GET \
    "${CUTOUT_BASE_URL}/api/job/${JOB_ID}/" \
    | jq --raw-output '.files.[].path'))

# Make the directory to store the downloaded files
mkdir -p "./${JOB_ID}"

# Download each file in the list.
for file in ${files[@]}; do
    echo "Downloading \"${CUTOUT_BASE_URL}/download/${JOB_ID}${file}\"..."
    curl --no-progress-meter -X POST --fail \
        -H "Content-Type: application/json" \
        -H "Authorization: Token ${API_TOKEN}" \
        --output "./${JOB_ID}${file}" \
        "${CUTOUT_BASE_URL}/download/${JOB_ID}${file}"
done
```
