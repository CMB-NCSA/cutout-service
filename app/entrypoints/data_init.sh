#!/usr/bin/env bash

set -euo pipefail

if mc --version; then
    mc alias set osn-des-anon https://ncsa.osn.xsede.org/ anonymous ''
    mc mirror --json osn-des-anon/phy240006-bucket01/descutter/db/ /data/db/
    mc mirror --json osn-des-anon/phy240006-bucket01/descutter/files/des_archive/ /des_archive/
else
    echo "Please install MinIO client \"mc\"."
    exit 1
fi
