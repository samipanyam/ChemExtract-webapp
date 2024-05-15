import boto3

# Replace 'your_bucket_name' and 'your_file_name' with your actual bucket name and file name
bucket_name = 'chemextract'
file_name = 'research.pdf'
s3 = boto3.client('s3')

# Upload the file
s3.upload_file(file_name, bucket_name, file_name)

s3.download_file(bucket_name, file_name, 'downloaded.pdf')