#!/usr/bin/env sh
DIR="$( cd "$( dirname "$0" )" && pwd -P )"
mkdir -p "$DIR/Logs"
"$DIR/auto_record_data.py" 2>&1 | tee -a "$DIR/Logs/auto_record.log"
