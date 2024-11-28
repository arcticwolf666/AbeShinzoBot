#!/bin/bash
set -u

script_name="discordbot.py"
dist_path=$(cd $(dirname $0); pwd)
script_file="${dist_path}/${script_name}"
log_path="${dist_path}/log"
log_file="${log_path}/discordbot.log"

# check script exits.
if [ ! -e "${script_file}" ]; then
    echo "${script_file} not found."
    exit -1
fi

# check log output directory.
if [ ! -d "${log_path}" ]; then
    mkdir "${log_path}"
    if [ $? -ne 0 ]; then
        echo "${log_path} create failed."
        exit -1
    fi
fi

# open log file.
exec 3>> "${log_file}"
# redirect stdout and stderr to file descriptor 3
exec 1>&3
exec 2>&3
source "${dist_path}/venv/bin/activate"
result=$(python "${script_file}")
exec 3>&-

exit $result
