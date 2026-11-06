#!/usr/bin/env bash
# Push album images to Cloudflare R2 (bucket served at img.sadh.studio).
#   ./run.sh sync   uploads albums/<slug>/img/*.jpg to r2:<bucket>/albums/<slug>/. The first run installs
#                   rclone (brew) and asks for the R2 token's keys, saved in ~/src/.config/rclone/rclone.conf
# Once the images are up, put the public base in albums/IMG_BASE, e.g.
#   echo https://img.sadh.studio/albums/ > albums/IMG_BASE
# and the build points album pages there and stops deploying img/.
set -euo pipefail
cd "$(dirname "$0")/.."
BUCKET="${R2_BUCKET:-sadh-studio}"
ACCOUNT=b404bedb1195032ed85340a9cfa87d11
# first run: install rclone and set up the "r2" remote (asks for the token's two keys once)
if ! command -v rclone >/dev/null; then
  command -v brew >/dev/null || { echo "install rclone first: https://rclone.org/install/"; exit 1; }
  brew install rclone
fi
if [ -z "${RCLONE_CONFIG:-}" ] && ! rclone listremotes 2>/dev/null | grep -qx "r2:"; then
  # keys live beside the repos, outside any of them: ~/src/.config/rclone/rclone.conf
  export RCLONE_CONFIG="$(cd .. && pwd)/.config/rclone/rclone.conf"
  mkdir -p "$(dirname "$RCLONE_CONFIG")"
fi
if ! rclone listremotes | grep -qx "r2:"; then
  : "${RCLONE_CONFIG:=$(cd .. && pwd)/.config/rclone/rclone.conf}"
  export RCLONE_CONFIG
  mkdir -p "$(dirname "$RCLONE_CONFIG")"
  echo "R2 > Manage API tokens > Create Account API token (Object Read & Write, bucket $BUCKET)"
  read -rp "Access Key ID: " KEY_ID
  read -rsp "Secret Access Key (hidden): " KEY_SECRET; echo
  rclone config create r2 s3 provider=Cloudflare access_key_id="$KEY_ID" secret_access_key="$KEY_SECRET" \
    endpoint="https://$ACCOUNT.r2.cloudflarestorage.com" acl=private no_check_bucket=true >/dev/null
  unset KEY_SECRET
  chmod 600 "$RCLONE_CONFIG"
  echo "saved remote r2 in $RCLONE_CONFIG"
fi
for d in albums/*/img; do
  slug=$(basename "$(dirname "$d")")
  rclone sync "$d" "r2:$BUCKET/albums/$slug" --include "*.jpg" \
    --header-upload "Cache-Control: public, max-age=31536000, immutable" --progress
done
