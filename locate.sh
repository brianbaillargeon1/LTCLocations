#!/usr/bin/env bash

ltc_dir=`dirname $0`
if [ ! -d $ltc_dir/venv ]; then
	python3 -m venv $ltc_dir/venv
	source $ltc_dir/venv/bin/activate
	pip install -r $ltc_dir/requirements.txt
else
	source $ltc_dir/venv/bin/activate
fi
python $ltc_dir/ltc.py
