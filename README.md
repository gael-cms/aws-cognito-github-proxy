# AWS Cognito Github API Proxy

This repo contains code and examples needed to create a proxy of the Github HTTP API using AWS API Gateway, Lambda and Cognito.

This is a cost-effective way of controlling API access to Github while managing user authorization and accounts in AWS Cognito. 

# Deploying the solution

In order to deploy the solution in your own account, you can simply deploy the `cloudformation.yaml` template directly.

You will need to create a Github App, and provide an app ID and installation ID to be used as env variables.

Once you generate a private key for your Github app you can upload it using:
```shell
aws secretsmanager create-secret \
  --name YourSecretName \
  --secret-binary "fileb:///path/to/your/secret.pem"
```

The configuration values for DecapCMS backend are available as outputs from the cloudformation template and are:
- `OauthAppID`: `app_id` backend configuration field.
- `OauthHostName`: `base_url` backend configuration field.
- `GithubAPIProxyUrl`: `api_root` backend configuration field.

An example AWS Certificate Manager Certificate is given in `certificate.yaml`. 
You must deploy this in the `us-east-1` (this is a specific Cloudfront requirement).
This is in a separate file to allow you to deploy all other resources in any region you choose. 

The template references a public version of the Lambda function and dependency layer stored in S3 in the `eu-west-1` region.
If you would like to build and use your own S3 artifacts (and it is strongly recommended that you do so), see the section below.

# Deploying your own Lambda artifacts to S3

## Creating customised Lambda Function artifact for AWS Lambda

1. Make any desired adjustments to the Lambda function and then create the `.zip` file of our requirements layer:
    ```shell
    zip proxy-lambda.zip proxy-lambda.py 
    ```
2. If you introduce any new pip dependencies you will need to add it to the layer artifact (as described below). 
3. Upload the zip artifact to S3 so that it's available for use by your Lambda resource definition.
    ```shell
    S3_BUCKET_NAME="aws-cognito-github-proxy-lambda-resources" aws s3 cp ./proxy-lambda.zip "s3://${S3_BUCKET_NAME}/aws-cognito-github-proxy/proxy-lambda.zip"
    ```
4. Update your Cloudformation deployment to reference your new S3 bucket and object keys for the Lambda function zipfile.

## Creating python dependencies Layer artifact For AWS Lambda:

1. Install existing requirements:
    ```shell
    pip3.11 install -r requirements-deps-layer.txt -t proxy-lambda-deps-layer/python
    ```
2. (Optional) install any additional requirements and freeze using:
   ```shell
   pip3.11 install {dependency} -t proxy-lambda-deps-layer/python
   pip3.11 freeze --path proxy-lambda-deps-layer/python > requirements-deps-layer.txt      
   ```
3. Create the `.zip` file of our requirements layer:
   ```shell
   cd proxy-lambda-deps-layer/
   zip ../proxy-lambda-deps-layer.zip -r python -x **/__pycache__/**/* -x **/__pycache__/
   cd ..
   ```
4. Upload the zip artifact to S3 so that it's available for use by your Lambda resource definition.
   ```shell
   S3_BUCKET_NAME="aws-cognito-github-proxy-lambda-resources" && aws s3 cp ./proxy-lambda-deps-layer.zip "s3://${S3_BUCKET_NAME}/aws-cognito-github-proxy/proxy-lambda-deps-layer.zip"
   ```
5. Update your Cloudformation deployment to reference your new S3 bucket and object keys for the Lambda dependency layer zipfile.
