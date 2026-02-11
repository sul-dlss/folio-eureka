#!/bin/sh

python3 bootstrap_admin_user.py --create_user --email $LIBSYS_ADMIN_EMAIL --first_name Libsys --last_name Admin --password $LIBSYS_PASSWORD --username $LIBSYS_USER
