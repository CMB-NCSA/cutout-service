# Cutout Service

## Data bridge

For convenience, a pod can be spawned by setting `data.bridge.enabled=true` that is 
configured to read the source data and write to the initial application data S3 bucket.

```bash
$ kubectl exec -it -n descut data-bridge-0 -- bash

app@data-bridge-0:/opt/app$ mc cp \
    /taiga-bbfl/des/dblib/a0ea5cb06b0ea74d0a56eac5f3efaed6/desdecade_lite_metadata.duckdb \
    osn-des/phy240006-bucket01/descutter/db/a0ea5cb06b0ea74d0a56eac5f3efaed6/desdecade_lite_metadata.duckdb
```
