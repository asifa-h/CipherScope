#!/bin/sh

set -e

echo "Waiting for MinIO..."

until mc alias set cipherscope http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
do
    sleep 2
done

echo "Creating bucket..."

mc mb --ignore-existing cipherscope/$S3_BUCKET

echo "Verifying bucket..."

mc stat cipherscope/$S3_BUCKET

echo "MinIO initialization complete."