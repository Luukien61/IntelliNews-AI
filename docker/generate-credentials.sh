#!/bin/bash

# Script tạo S3 credentials mạnh cho SeaweedFS

echo "🔐 SeaweedFS S3 Credentials Generator"
echo "======================================"
echo ""

# Function tạo access key (20 ký tự)
generate_access_key() {
    openssl rand -base64 15 | tr -d '/+=' | head -c 20
}

# Function tạo secret key (40 ký tự)
generate_secret_key() {
    openssl rand -base64 30 | tr -d '/+=' | head -c 40
}

# Tạo credentials cho admin
echo "📝 ADMIN Credentials:"
ADMIN_ACCESS=$(generate_access_key)
ADMIN_SECRET=$(generate_secret_key)
echo "   Access Key: $ADMIN_ACCESS"
echo "   Secret Key: $ADMIN_SECRET"
echo ""

# Tạo credentials cho uploader
echo "📝 AUDIO UPLOADER Credentials:"
UPLOADER_ACCESS=$(generate_access_key)
UPLOADER_SECRET=$(generate_secret_key)
echo "   Access Key: $UPLOADER_ACCESS"
echo "   Secret Key: $UPLOADER_SECRET"
echo ""

# Tạo credentials cho readonly
echo "📝 READONLY Credentials:"
READONLY_ACCESS=$(generate_access_key)
READONLY_SECRET=$(generate_secret_key)
echo "   Access Key: $READONLY_ACCESS"
echo "   Secret Key: $READONLY_SECRET"
echo ""

# Tạo file s3.json mới
cat > config/s3.json << EOF
{
  "identities": [
    {
      "name": "admin",
      "credentials": [
        {
          "accessKey": "$ADMIN_ACCESS",
          "secretKey": "$ADMIN_SECRET"
        }
      ],
      "actions": [
        "Admin",
        "Read",
        "List",
        "Tagging",
        "Write"
      ]
    },
    {
      "name": "audio_uploader",
      "credentials": [
        {
          "accessKey": "$UPLOADER_ACCESS",
          "secretKey": "$UPLOADER_SECRET"
        }
      ],
      "actions": [
        "Read",
        "Write",
        "List"
      ]
    },
    {
      "name": "readonly_user",
      "credentials": [
        {
          "accessKey": "$READONLY_ACCESS",
          "secretKey": "$READONLY_SECRET"
        }
      ],
      "actions": [
        "Read",
        "List"
      ]
    }
  ]
}
EOF

echo "✅ File config/s3.json đã được tạo với credentials mới!"
echo ""
echo "⚠️  LƯU Ý: Hãy backup các credentials này ở nơi an toàn!"
echo "    Bạn sẽ cần chúng để configure AWS CLI hoặc SDK"
echo ""
echo "📋 Để sử dụng với AWS CLI:"
echo "    aws configure set aws_access_key_id $UPLOADER_ACCESS"
echo "    aws configure set aws_secret_access_key $UPLOADER_SECRET"
echo ""
