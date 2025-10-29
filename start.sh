#!/usr/bin/env bash
set -e
mkdir -p /var/data
if [ ! -f /var/data/data.json ]; then
  if [ -f "./data.json" ]; then
    cp ./data.json /var/data/data.json
  else
    echo "{}" > /var/data/data.json
  fi
fi
python NTH_v1.py
