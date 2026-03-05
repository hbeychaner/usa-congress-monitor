import subprocess
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def run(cmd):
    logger.info(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)


# Step 1: Generate chunk records
run("python tools/daily_chunk_generator.py")

# Step 2: Queue incomplete chunks
run("python -m tools.queue_progress_manager")

# Step 3: Start consumers (example for 'member')
run("python orchestrators/sync/rabbitmq_consumer.py member")
# Add more consumer calls as needed

logger.info("Ingest workflow complete.")
