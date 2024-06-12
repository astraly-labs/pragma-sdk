# task_runner.sh
#!/bin/bash
INTERVAL=${TASK_INTERVAL:-10}  # Default to 10 seconds if not set
while true
do
    python /app.py
    sleep $INTERVAL
done
