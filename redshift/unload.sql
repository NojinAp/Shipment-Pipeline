UNLOAD ('SELECT * FROM shipments')
TO 's3://{{BUCKET_NAME}}/extract/raw/shipment_master/shipment_master'
IAM_ROLE '{{IAM_ROLE_ARN}}'
FORMAT AS CSV
HEADER
EXTENSION 'csv'
REGION 'ca-central-1'
ALLOWOVERWRITE;

UNLOAD ('SELECT * FROM billing')
TO 's3://{{BUCKET_NAME}}/extract/raw/billing_extract/billing_extract'
IAM_ROLE '{{IAM_ROLE_ARN}}'
FORMAT AS CSV
HEADER
EXTENSION 'csv'
REGION 'ca-central-1'
ALLOWOVERWRITE;UNLOAD ('SELECT * FROM shipments')
TO 's3://{{BUCKET_NAME}}/extract/raw/shipment_master/shipment_master'
IAM_ROLE '{{IAM_ROLE_ARN}}'
FORMAT AS CSV
HEADER
EXTENSION 'csv'
REGION 'ca-central-1'
ALLOWOVERWRITE;

UNLOAD ('SELECT * FROM billing')
TO 's3://{{BUCKET_NAME}}/extract/raw/billing_extract/billing_extract'
IAM_ROLE '{{IAM_ROLE_ARN}}'
FORMAT AS CSV
HEADER
EXTENSION 'csv'
REGION 'ca-central-1'
ALLOWOVERWRITE;