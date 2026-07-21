TRUNCATE TABLE shipments;
TRUNCATE TABLE billing;

COPY shipments
FROM 's3://{{BUCKET_NAME}}/redshift/staging/shipment_master.csv'
IAM_ROLE '{{IAM_ROLE_ARN}}'
FORMAT AS CSV
IGNOREHEADER 1
TIMEFORMAT 'auto'
REGION 'ca-central-1';

COPY billing
FROM 's3://{{BUCKET_NAME}}/redshift/staging/billing_extract.csv'
IAM_ROLE '{{IAM_ROLE_ARN}}'
FORMAT AS CSV
IGNOREHEADER 1
DATEFORMAT 'auto'
REGION 'ca-central-1';