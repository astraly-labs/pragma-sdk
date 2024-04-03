#!/bin/bash
# Export the environment variables to a file
printenv > /etc/environment
# Set up the cron job
echo "* * * * * /bin/bash -c '. /etc/environment; /usr/local/bin/python /app.py > /proc/1/fd/1 2>/proc/1/fd/2" > /etc/cron.d/cronjob
echo "* * * * * root (sleep 30 ; /bin/bash -c '. /etc/environment; /usr/local/bin/python /app.py  > /proc/1/fd/1 2>/proc/1/fd/2)" >> /etc/cron.d/cronjob
chmod 0644 /etc/cron.d/cronjob

# Start cron in the foreground
cron -f
