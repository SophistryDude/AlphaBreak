#!/bin/bash
# =============================================================================
# CloudFront CDN Setup for AlphaBreak
# =============================================================================
# Prerequisites:
#   - AWS CLI v2 installed and configured (aws configure)
#   - ACM certificate for alphabreak.vip in us-east-1 (required for CloudFront)
#   - EC2 instance public IP or domain known
#
# Usage: bash setup-cloudfront.sh
# =============================================================================

set -euo pipefail

DOMAIN="alphabreak.vip"
ALT_DOMAIN="www.alphabreak.vip"
ORIGIN_DOMAIN="${ORIGIN_DOMAIN:-alphabreak.vip}"  # EC2 public DNS or IP
COMMENT="AlphaBreak CDN"

# Step 1: Check for ACM certificate in us-east-1
echo "Looking for ACM certificate for ${DOMAIN} in us-east-1..."
CERT_ARN=$(aws acm list-certificates \
  --region us-east-1 \
  --query "CertificateSummaryList[?DomainName=='${DOMAIN}'].CertificateArn | [0]" \
  --output text)

if [ "$CERT_ARN" = "None" ] || [ -z "$CERT_ARN" ]; then
  echo "No ACM certificate found. Requesting one..."
  CERT_ARN=$(aws acm request-certificate \
    --region us-east-1 \
    --domain-name "${DOMAIN}" \
    --subject-alternative-names "${ALT_DOMAIN}" \
    --validation-method DNS \
    --query 'CertificateArn' \
    --output text)
  echo "Certificate requested: ${CERT_ARN}"
  echo ">>> You must validate this certificate via DNS before continuing."
  echo ">>> Run: aws acm describe-certificate --certificate-arn ${CERT_ARN} --region us-east-1"
  echo ">>> Add the CNAME records shown to your DNS, then re-run this script."
  exit 1
fi
echo "Using certificate: ${CERT_ARN}"

# Step 2: Create CloudFront distribution config
cat > /tmp/cloudfront-config.json <<EOF
{
  "CallerReference": "alphabreak-$(date +%s)",
  "Comment": "${COMMENT}",
  "Enabled": true,
  "Aliases": {
    "Quantity": 2,
    "Items": ["${DOMAIN}", "${ALT_DOMAIN}"]
  },
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "alphabreak-origin",
        "DomainName": "${ORIGIN_DOMAIN}",
        "CustomOriginConfig": {
          "HTTPPort": 80,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "https-only",
          "OriginSslProtocols": { "Quantity": 1, "Items": ["TLSv1.2"] }
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "alphabreak-origin",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] },
    "CachedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] },
    "Compress": true,
    "ForwardedValues": {
      "QueryString": false,
      "Cookies": { "Forward": "none" }
    },
    "DefaultTTL": 3600,
    "MinTTL": 0,
    "MaxTTL": 86400
  },
  "CacheBehaviors": {
    "Quantity": 4,
    "Items": [
      {
        "PathPattern": "/api/*",
        "TargetOriginId": "alphabreak-origin",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": { "Quantity": 7, "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"] },
        "CachedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] },
        "Compress": true,
        "ForwardedValues": {
          "QueryString": true,
          "Headers": { "Quantity": 3, "Items": ["Authorization", "Accept", "Origin"] },
          "Cookies": { "Forward": "all" }
        },
        "DefaultTTL": 0,
        "MinTTL": 0,
        "MaxTTL": 0
      },
      {
        "PathPattern": "*.js",
        "TargetOriginId": "alphabreak-origin",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] },
        "CachedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] },
        "Compress": true,
        "ForwardedValues": {
          "QueryString": false,
          "Cookies": { "Forward": "none" }
        },
        "DefaultTTL": 86400,
        "MinTTL": 86400,
        "MaxTTL": 604800
      },
      {
        "PathPattern": "*.css",
        "TargetOriginId": "alphabreak-origin",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] },
        "CachedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] },
        "Compress": true,
        "ForwardedValues": {
          "QueryString": false,
          "Cookies": { "Forward": "none" }
        },
        "DefaultTTL": 86400,
        "MinTTL": 86400,
        "MaxTTL": 604800
      },
      {
        "PathPattern": "*.png",
        "TargetOriginId": "alphabreak-origin",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] },
        "CachedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] },
        "Compress": false,
        "ForwardedValues": {
          "QueryString": false,
          "Cookies": { "Forward": "none" }
        },
        "DefaultTTL": 604800,
        "MinTTL": 604800,
        "MaxTTL": 2592000
      }
    ]
  },
  "ViewerCertificate": {
    "ACMCertificateArn": "${CERT_ARN}",
    "SSLSupportMethod": "sni-only",
    "MinimumProtocolVersion": "TLSv1.2_2021"
  },
  "HttpVersion": "http2and3",
  "PriceClass": "PriceClass_100"
}
EOF

# Step 3: Create the distribution
echo "Creating CloudFront distribution..."
DIST_ID=$(aws cloudfront create-distribution \
  --distribution-config file:///tmp/cloudfront-config.json \
  --query 'Distribution.Id' \
  --output text)

DIST_DOMAIN=$(aws cloudfront get-distribution \
  --id "$DIST_ID" \
  --query 'Distribution.DomainName' \
  --output text)

echo ""
echo "========================================="
echo "CloudFront distribution created!"
echo "  Distribution ID: ${DIST_ID}"
echo "  Domain: ${DIST_DOMAIN}"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Update DNS: CNAME ${DOMAIN} -> ${DIST_DOMAIN}"
echo "  2. Update DNS: CNAME ${ALT_DOMAIN} -> ${DIST_DOMAIN}"
echo "  3. Wait for distribution to deploy (~10-15 minutes)"
echo "  4. Run setup-waf.sh to add WAF protection"

rm /tmp/cloudfront-config.json
